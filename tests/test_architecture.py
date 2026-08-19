from __future__ import annotations

import sqlite3
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from muclegal.clause_diff import pair_clause_changes
from muclegal.fetch import FetchResult
from muclegal.llm import validate_clause_classification
from muclegal.normalize import NormalizationConfig, normalize_plain_text, split_clauses
from muclegal.pipeline import check_url
from muclegal.storage import SnapshotRepository


class _SequenceFetcher:
    def __init__(self, bodies: list[str]) -> None:
        self.bodies = iter(bodies)

    def fetch(self, url: str) -> FetchResult:
        body = next(self.bodies).encode("utf-8")
        return FetchResult(
            requested_url=url,
            final_url=url,
            fetched_at=datetime.now(timezone.utc).isoformat(),
            status_code=200,
            headers=(("content-type", "text/html; charset=utf-8"),),
            redirect_chain=(),
            body=body,
            decoded_html=body.decode("utf-8"),
        )


class ArchitectureTests(unittest.TestCase):
    def test_plain_text_normalization_is_nfkc_and_removes_invisible_noise(self) -> None:
        self.assertEqual('ABC - "Text"\n', normalize_plain_text("ＡＢＣ\u200b — “Text”"))

    def test_legal_clause_split_tracks_heading_and_is_hash_stable(self) -> None:
        text = "§ 5 Widerruf\n(1) Der Verbraucher trägt die Kosten.\n(2) Im Übrigen gilt das Gesetz."
        first = split_clauses(text)
        second = split_clauses(text)
        self.assertEqual(first, second)
        self.assertEqual(3, len(first))
        self.assertEqual("§ 5 > (1)", first[1].heading_path)
        self.assertEqual(64, len(first[1].clause_hash))

    def test_reworded_clause_is_paired_instead_of_delete_plus_insert(self) -> None:
        old = split_clauses("§ 5 Rücksendung\n(1) Die Rücksendekosten trägt der Verbraucher.")
        new = split_clauses("§ 5 Rücksendung\n(1) Der Kunde übernimmt die Kosten der Rücksendung.")
        pairs = pair_clause_changes(old, new)
        changed = [pair for pair in pairs if pair.previous and pair.current]
        self.assertTrue(any("Rücksendekosten" in pair.previous.text for pair in changed))

    def test_invented_evidence_quote_fails_closed_to_unsicher(self) -> None:
        result = validate_clause_classification(
            {
                "classification": "kerngleich",
                "tenor_element_id": "E1",
                "confidence": "hoch",
                "evidence_quote": "Dieses Zitat wurde erfunden.",
                "reasoning": "Die Wirkung besteht fort.",
            },
            [{"id": "E1"}],
            "Die Rücksendekosten trägt der Verbraucher.",
            "Die Kosten der Rücksendung trägt der Kunde.",
        )
        self.assertEqual("unsicher", result.classification)
        self.assertIn("nicht wörtlich", result.validation_error)

    def test_unknown_tenor_element_fails_closed_to_unsicher(self) -> None:
        result = validate_clause_classification(
            {
                "classification": "kerngleich",
                "tenor_element_id": "E99",
                "confidence": "mittel",
                "evidence_quote": "trägt der Kunde",
                "reasoning": "Begründung",
            },
            [{"id": "E1"}],
            None,
            "Die Kosten trägt der Kunde.",
        )
        self.assertEqual("unsicher", result.classification)
        self.assertIn("existiert nicht", result.validation_error)

    def test_suspiciously_short_extraction_creates_no_diff(self) -> None:
        long_paragraph = "Die gesetzlich relevante Klausel bleibt bestehen. " * 12
        fetcher = _SequenceFetcher(
            [f"<main><p>{long_paragraph}</p></main>", "<main><p>Fehlerseite</p></main>"]
        )
        with tempfile.TemporaryDirectory() as directory:
            repository = SnapshotRepository(directory)
            first = check_url("https://example.test/agb", NormalizationConfig(), repository, fetcher)
            second = check_url("https://example.test/agb", NormalizationConfig(), repository, fetcher)
            self.assertTrue(first.extraction_ok)
            self.assertEqual("extraction_failed", second.status)
            self.assertFalse(second.extraction_ok)
            self.assertIsNone(second.diff_path)
            connection = sqlite3.connect(repository.database_path)
            try:
                findings = connection.execute("SELECT COUNT(*) FROM findings").fetchone()[0]
            finally:
                connection.close()
            self.assertEqual(0, findings)

    def test_findings_are_append_only_except_human_decision_columns(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repository = SnapshotRepository(directory)
            connection = sqlite3.connect(repository.database_path)
            try:
                connection.execute("PRAGMA foreign_keys = OFF")
                connection.execute(
                    """
                    INSERT INTO findings(
                      id, created_at, snapshot_id, classification, confidence,
                      evidence_quote, reasoning
                    ) VALUES ('F1', '2026-08-19T00:00:00Z', 1, 'unsicher', 'niedrig', 'Zitat', 'Grund')
                    """
                )
                connection.execute(
                    "UPDATE findings SET juristin_kommentar = 'geprüft' WHERE id = 'F1'"
                )
                with self.assertRaises(sqlite3.IntegrityError):
                    connection.execute(
                        "UPDATE findings SET classification = 'kerngleich' WHERE id = 'F1'"
                    )
                with self.assertRaises(sqlite3.IntegrityError):
                    connection.execute("DELETE FROM findings WHERE id = 'F1'")
            finally:
                connection.close()

    def test_screenshot_metadata_is_linked_to_snapshot(self) -> None:
        fetcher = _SequenceFetcher(
            ["<main><h1>AGB</h1><p>Die Rücksendekosten trägt der Verbraucher.</p></main>"]
        )
        with tempfile.TemporaryDirectory() as directory:
            repository = SnapshotRepository(directory)
            outcome = check_url(
                "https://example.test/agb", NormalizationConfig(), repository, fetcher
            )
            screenshot = Path(directory) / "screenshot.png"
            screenshot.write_bytes(b"\x89PNG\r\n\x1a\nsynthetic-test-payload")
            record = repository.save_snapshot_screenshot(
                outcome.snapshot_id,
                path=str(screenshot),
                sha256="a" * 64,
                size_bytes=screenshot.stat().st_size,
            )
            self.assertEqual("captured", record.status)
            self.assertEqual(str(screenshot), record.path)
            self.assertEqual("a" * 64, record.sha256)


if __name__ == "__main__":
    unittest.main()
