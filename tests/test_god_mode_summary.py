from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from muclegal.llm.god_mode_summary import (
    GOD_MODE_AI_NOTICE,
    EditorialFact,
    EditorialPage,
    GodModeEditorialSummarizer,
    RelatedProduct,
    create_god_mode_editorial_analysis,
)


class FakeResponses:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def parse(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(
            output_parsed=EditorialPage(
                title="Jabbar Schuh",
                page_type="produkt",
                summary="Produktseite eines weißen Schuhs mit ausgewiesenem Rabatt.",
                facts=[
                    EditorialFact(label="Artikelnummer", value="KI8573"),
                    EditorialFact(label="Farbe", value="Cloud White"),
                ],
                prices=["120 €", "84 €"],
                available_sizes=["42", "43"],
                unavailable_sizes=["44"],
                details=["Obermaterial Leder"],
                ratings_summary="Bewertungen wurden verdichtet.",
                related_products=[
                    RelatedProduct(
                        name="Weiterer Schuh",
                        price="90 €",
                        url="https://shop.test/weiterer-schuh",
                    )
                ],
                omitted_dynamic_content=["Doppelte Empfehlungen"],
            ),
            usage=SimpleNamespace(input_tokens=100, output_tokens=50),
        )


class FakeClient:
    def __init__(self) -> None:
        self.responses = FakeResponses()


def _page_bundle(root: Path, text: str) -> tuple[Path, Path]:
    bundle = root / "bundle"
    role_root = bundle / "artifacts" / "roles" / "main"
    role_root.mkdir(parents=True)
    normalized = role_root / "normalized-text.txt"
    normalized.write_text(text, encoding="utf-8")
    (role_root / "request.json").write_text(
        json.dumps(
            {
                "final_url": "https://www.adidas.de/jabbar-schuh/KI8573.html",
                "captured_at": "2026-08-21T10:00:00+00:00",
            }
        ),
        encoding="utf-8",
    )
    index = bundle / "artifacts" / "page-artifacts-index.json"
    index.write_text(
        json.dumps(
            {
                "pages": {
                    "main": {
                        "captured_url": "https://www.adidas.de/jabbar-schuh/KI8573.html",
                        "primary_normalized_text": (
                            "artifacts/roles/main/normalized-text.txt"
                        ),
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    return bundle, index


def test_openai_editorial_summary_is_text_only_bounded_cached_and_costed(tmp_path: Path) -> None:
    source = "Jabbar Schuh KI8573 Cloud White 120 € 84 € Größe 42 " * 2_000
    bundle, index = _page_bundle(tmp_path, source)
    client = FakeClient()
    summarizer = GodModeEditorialSummarizer(
        client=client,
        model="gpt-5.6-luna",
        max_input_chars=24_000,
        max_output_tokens=900,
    )
    first = create_god_mode_editorial_analysis(
        bundle=bundle,
        page_artifacts_index=index,
        cache_directory=tmp_path / "cache",
        output_directory=bundle / "analysis" / "editorial",
        summarizer=summarizer,
    )
    second = create_god_mode_editorial_analysis(
        bundle=bundle,
        page_artifacts_index=index,
        cache_directory=tmp_path / "cache",
        output_directory=bundle / "analysis-second" / "editorial",
        summarizer=summarizer,
    )
    normalized = bundle / "artifacts" / "roles" / "main" / "normalized-text.txt"
    normalized.write_text(source + " geänderter Wochenstand", encoding="utf-8")
    third = create_god_mode_editorial_analysis(
        bundle=bundle,
        page_artifacts_index=index,
        cache_directory=tmp_path / "cache",
        output_directory=bundle / "analysis-third" / "editorial",
        summarizer=summarizer,
    )

    assert len(client.responses.calls) == 1
    request = client.responses.calls[0]
    assert request["store"] is False
    assert request["reasoning"] == {"effort": "none"}
    assert request["max_output_tokens"] == 900
    assert "tools" not in request
    assert "screenshot" not in request["input"].casefold()
    assert "raw_html" not in request["input"]
    assert first.page_results[0]["sent_characters"] == 24_000
    assert first.page_results[0]["input_truncated"] is True
    assert first.total_estimated_cost_usd == 0.00008
    assert second.page_results[0]["status"] == "cache_hit"
    assert second.total_estimated_cost_usd == 0.0
    assert third.status == "skipped_weekly_sample_window"
    assert third.page_results[0]["status"] == "skipped_weekly_sample_window"
    assert third.page_results[0]["monitoring_category"] == "stichprobenartig"
    assert third.page_results[0]["minimum_sample_interval_days"] == 7
    assert third.total_estimated_cost_usd == 0.0
    summary = first.artifacts["god_mode_editorial_summary"].read_text(encoding="utf-8")
    usage = json.loads(first.artifacts["god_mode_ai_usage"].read_text(encoding="utf-8"))
    assert summary.startswith(GOD_MODE_AI_NOTICE)
    assert "KI8573" in summary
    assert usage["total_api_calls"] == 1
    assert usage["monitoring_category"] == "stichprobenartig"
    assert usage["minimum_sample_interval_days"] == 7
    assert "API_KEY" not in json.dumps(usage)


def test_missing_key_skips_openai_without_losing_usage_record(tmp_path: Path) -> None:
    bundle, index = _page_bundle(tmp_path, "Öffentlich sichtbarer Produkttext")
    run = create_god_mode_editorial_analysis(
        bundle=bundle,
        page_artifacts_index=index,
        cache_directory=tmp_path / "cache",
        output_directory=bundle / "analysis" / "editorial",
        summarizer=GodModeEditorialSummarizer(api_key=""),
    )

    usage = json.loads(run.artifacts["god_mode_ai_usage"].read_text(encoding="utf-8"))
    assert run.status == "skipped_no_api_key"
    assert "god_mode_editorial_summary" not in run.artifacts
    assert usage["configured"] is False
    assert usage["total_api_calls"] == 0
    assert usage["pages"][0]["status"] == "skipped_no_api_key"
