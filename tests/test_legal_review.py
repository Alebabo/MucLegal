from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from muclegal.legal_review import prepare_blind_review


ROOT = Path(__file__).resolve().parents[1]


class BlindReviewTests(unittest.TestCase):
    def test_two_blind_sheets_hide_expected_results_and_randomize_order(self) -> None:
        with tempfile.TemporaryDirectory() as output:
            paths = prepare_blind_review(ROOT / "fixtures" / "eval-suite.json", output)
            first = json.loads(Path(paths[0]).read_text(encoding="utf-8"))
            second = json.loads(Path(paths[1]).read_text(encoding="utf-8"))
            status = json.loads(
                (Path(output) / "blind-review-status.json").read_text(encoding="utf-8")
            )
        self.assertEqual(12, len(first["cases"]))
        self.assertNotEqual(
            [case["id"] for case in first["cases"]],
            [case["id"] for case in second["cases"]],
        )
        self.assertNotIn("expected_result", json.dumps(first))
        self.assertTrue(all(case["bewertung"] is None for case in first["cases"]))
        self.assertEqual("pending_human_review", status["status"])


if __name__ == "__main__":
    unittest.main()
