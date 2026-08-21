from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from muclegal.fetch.consent import classify_privacy_action
from muclegal.fetch.playwright import (
    CaptureRunController,
    ScreenshotCapture,
    _capture_validated_screenshots,
)
from muclegal.live import _legal_capture_warning, _legal_role_for_url


class _CaptureHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/cookie-one":
            body = b"<main>first context</main>"
            self.send_response(200)
            self.send_header("Set-Cookie", "capture-session=must-not-leak; Path=/")
        elif self.path == "/cookie-two":
            body = b"<main id='cookie'></main><script>cookie.textContent=document.cookie||'empty'</script>"
            self.send_response(200)
        elif self.path == "/consent":
            body = b"""<!doctype html><main><h1>AGB</h1><details><summary>Klausel</summary>
              <p>Vollstaendige Testklausel.</p></details></main>
              <div role='dialog' aria-label='Cookie-Einstellungen'>Cookies
              <button id='accept'>Alle akzeptieren</button><button id='reject'>Alle ablehnen</button>
              </div><script>reject.onclick=()=>reject.parentElement.remove()</script>"""
            self.send_response(200)
        elif self.path == "/accordion":
            body = b"""<!doctype html><main><h1>Datenschutzhinweise</h1>
              <button id='print'>Drucken / Speichern</button>
              <section><button aria-expanded='false' aria-controls='part-1'>Verantwortlicher</button>
              <div id='part-1' hidden>MMS E-Commerce GmbH, Ingolstadt.</div></section>
              <section><button aria-expanded='false' aria-controls='part-2'>Ihre Rechte</button>
              <div id='part-2' hidden>Auskunft, Berichtigung und Loeschung nach DSGVO.</div></section>
              <script>document.querySelectorAll('[aria-controls]').forEach(button=>button.onclick=()=>{
                document.getElementById(button.getAttribute('aria-controls')).hidden=false;
                button.setAttribute('aria-expanded','true');
              }); print.onclick=()=>location.href='/must-not-open';</script></main>"""
            self.send_response(200)
        else:
            height = int(self.path.removeprefix("/height/").split("?")[0])
            body = (
                "<!doctype html><style>html,body{margin:0}#page{height:%dpx;background:#eef}"
                "#footer{position:absolute;top:%dpx;height:40px;background:#111;color:white}</style>"
                "<main id='page'>height %d<div id='footer'>FOOTER-MARKER</div></main>"
                % (height, max(0, height - 40), height)
            ).encode()
            self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, _format: str, *_args) -> None:
        return


@pytest.fixture()
def capture_server():
    server = ThreadingHTTPServer(("127.0.0.1", 0), _CaptureHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        thread.join(timeout=2)


def test_controller_uses_one_browser_fresh_contexts_and_project_user_agent(
    tmp_path: Path, capture_server: str
) -> None:
    user_agent = "MucLegal-Monitor/test (+contact)"
    with CaptureRunController(tmp_path, user_agent=user_agent) as controller:
        first = controller.capture_target(f"{capture_server}/cookie-one")
        second = controller.capture_target(f"{capture_server}/cookie-two")

    assert controller.browser_starts == 1
    assert controller.contexts == 2
    assert first.fetch_result.browser_metadata["navigator_webdriver"] is True
    assert first.fetch_result.browser_metadata["user_agent"] == user_agent
    visible = Path(second.artifact_directory, "visible-text-initial.txt").read_text("utf-8")
    assert visible.strip() == "empty"
    assert Path(first.artifact_directory, "dom-initial.html").is_file()


def test_closed_page_after_initial_state_returns_reviewable_partial_capture(
    tmp_path: Path, capture_server: str
) -> None:
    with CaptureRunController(
        tmp_path,
        after_initial_hook=lambda page, _root: page.close(),
    ) as controller:
        captured = controller.capture_target(f"{capture_server}/height/1000")

    assert captured.capture_completeness == "teilweise_erfasst"
    assert captured.screenshot is None
    assert captured.failure_phase == "consent"
    assert "FOOTER-MARKER" in Path(
        captured.artifact_directory, "dom-initial.html"
    ).read_text("utf-8")
    assert "FOOTER-MARKER" in Path(
        captured.artifact_directory, "normalized-text.txt"
    ).read_text("utf-8")


@pytest.mark.parametrize("height", [1000, 7999, 8001, 30000])
def test_full_page_capture_is_not_silently_limited_at_8000_pixels(
    tmp_path: Path, capture_server: str, height: int
) -> None:
    with CaptureRunController(tmp_path / str(height)) as controller:
        captured = controller.capture_target(f"{capture_server}/height/{height}")

    index = json.loads(Path(captured.screenshot.index_path).read_text("utf-8"))
    assert index["document_height_css_px"] >= height
    assert index["capture_completeness"] == "vollstaendig_erfasst"
    assert index["continuous_coverage"] is True
    assert "FOOTER-MARKER" in Path(
        captured.artifact_directory, "visible-text-final.txt"
    ).read_text("utf-8")


def test_consent_clicks_reject_and_legal_expansion_is_recorded(
    tmp_path: Path, capture_server: str
) -> None:
    with CaptureRunController(tmp_path) as controller:
        captured = controller.capture_target(f"{capture_server}/consent", role="agb")

    interactions = json.loads(
        Path(captured.artifact_directory, "interactions.json").read_text("utf-8")
    )["interactions"]
    consent = interactions[0]
    assert consent["action"]["button_text"] == "Alle ablehnen"
    assert all("akzept" not in (item.get("action") or {}).get("button_text", "").casefold()
               for item in interactions)
    assert any(item.get("type") == "legal_expansion" and item["changed"] for item in interactions)
    assert "Vollstaendige Testklausel" in Path(
        captured.artifact_directory, "normalized-text.txt"
    ).read_text("utf-8")


def test_aria_legal_accordions_are_expanded_and_print_pdf_is_stored(
    tmp_path: Path, capture_server: str
) -> None:
    with CaptureRunController(tmp_path) as controller:
        captured = controller.capture_target(f"{capture_server}/accordion", role="privacy")

    root = Path(captured.artifact_directory)
    normalized = (root / "normalized-text.txt").read_text("utf-8")
    interactions = json.loads((root / "interactions.json").read_text("utf-8"))[
        "interactions"
    ]
    expansions = [item for item in interactions if item.get("type") == "legal_expansion"]
    coverage = json.loads((root / "content-coverage.json").read_text("utf-8"))
    print_metadata = json.loads((root / "expanded-legal-print.json").read_text("utf-8"))

    assert "MMS E-Commerce GmbH" in normalized
    assert "Auskunft, Berichtigung" in normalized
    assert len(expansions) == 2
    assert all(item["changed"] for item in expansions)
    assert coverage["legal_expansion"]["complete"] is True
    assert coverage["legal_expansion"]["remaining_collapsed_controls"] == 0
    assert print_metadata["website_original"] is False
    assert (root / "expanded-legal-print.pdf").stat().st_size > 1_000
    assert captured.fetch_result.final_url.endswith("/accordion")


def test_generic_reject_requires_dialog_and_visible_accept_alternative() -> None:
    assert classify_privacy_action("Ablehnen", "Cookie-Einstellungen") is None
    assert classify_privacy_action(
        "Ablehnen",
        "Cookie-Einstellungen",
        visible_alternatives=("Alle akzeptieren", "Ablehnen"),
        dialog_role="dialog",
    ) == "optionale_cookies_abgelehnt"
    assert classify_privacy_action("Alle akzeptieren", "Cookie") is None


def test_protected_legal_replacement_role_and_thin_text_are_not_full(tmp_path: Path) -> None:
    (tmp_path / "normalized-text.txt").write_text("kurzer Datenschutztext", encoding="utf-8")
    (tmp_path / "clauses.json").write_text(
        json.dumps({"clauses": [{"text": "kurz"}]}), encoding="utf-8"
    )
    capture = ScreenshotCapture(
        path=str(tmp_path / "preview.webp"),
        sha256="0" * 64,
        size_bytes=0,
        artifact_directory=str(tmp_path),
    )

    assert _legal_role_for_url("https://example.test/de/terms-of-use.html") == "agb"
    assert _legal_role_for_url("https://example.test/privacy-policy") == "privacy"
    assert _legal_capture_warning("datenschutz", "direkter_rechtstext", capture)
    assert _legal_capture_warning(
        "agb", "übersicht_ohne_auflösbare_klauselseite", capture
    )


class _TileFallbackPage:
    def __init__(self, height: int) -> None:
        self.height = height

    def evaluate(self, script: str):
        if "scrollHeight" in script:
            return self.height
        if "scrollWidth" in script:
            return 1440
        return None

    def wait_for_timeout(self, _milliseconds: int) -> None:
        return

    def screenshot(self, *, path: str, full_page: bool, type: str, clip=None) -> None:
        assert type == "png"
        if full_page:
            Image.new("RGB", (1440, 100), "white").save(path)
            return
        image = Image.new("RGB", (int(clip["width"]), int(clip["height"])), "#ddeeff")
        if int(clip["y"] + clip["height"]) >= self.height:
            ImageDraw.Draw(image).rectangle((0, image.height - 20, image.width, image.height), fill="black")
        image.save(path)


def test_30000_pixel_tile_fallback_is_continuous_and_contains_footer(tmp_path: Path) -> None:
    capture = _capture_validated_screenshots(_TileFallbackPage(30000), tmp_path, [])
    index = json.loads(Path(capture.index_path).read_text("utf-8"))

    assert index["mode"] == "tiles"
    assert index["continuous_coverage"] is True
    assert index["reached_height_css_px"] == 30000
    assert len(index["tiles"]) > 1
    with Image.open(capture.tile_paths[-1]) as image:
        assert image.convert("RGB").getpixel((10, image.height - 5)) == (0, 0, 0)
