from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from muclegal.demo import run_demo
from muclegal.evidence import OpenSslTsaClient, verify_manifest
from muclegal.ui import create_app


class GoldenPathTests(unittest.TestCase):
    def test_offline_golden_path_and_human_review(self) -> None:
        with tempfile.TemporaryDirectory() as output:
            tsa = OpenSslTsaClient(
                tsa_url="http://127.0.0.1:1/tsr", timeout_seconds=0.1, max_attempts=1
            )
            result = run_demo("kerngleich", output, tsa_client=tsa)
            case = json.loads(Path(result.case_path).read_text(encoding="utf-8"))
            self.assertEqual("pending", result.timestamp_status)
            self.assertEqual("kerngleich_umfasst", case["assessment"]["ergebnis"])
            self.assertEqual("kerngleich", case["clause_findings"][0]["classification"])
            self.assertTrue(case["clause_schema_valid"])
            self.assertTrue(Path(case["artifacts"]["clause_model_input"]).is_file())
            self.assertTrue(Path(case["artifacts"]["clause_model_output"]).is_file())
            self.assertIsNone(case["assessment"]["freigabe_durch_mensch"])
            self.assertIsNone(case["freigabe_durch_mensch"])
            self.assertTrue(verify_manifest(case["artifacts"]["manifest"]).valid)
            self.assertTrue(Path(result.report_path).is_file())

            app = create_app(result.case_path, Path(output) / "reviews.sqlite3")
            client = TestClient(app)
            page = client.get("/")
            self.assertEqual(200, page.status_code)
            self.assertIn("MENSCHLICHE PRÜFUNG OFFEN", page.text)
            self.assertIn("freigabe_durch_mensch: null", page.text)
            review = client.post(
                "/review",
                content="decision=freigegeben",
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                follow_redirects=True,
            )
            self.assertEqual(200, review.status_code)
            self.assertIn("MENSCHLICH: FREIGEGEBEN", review.text)
            unchanged_case = json.loads(Path(result.case_path).read_text(encoding="utf-8"))
            self.assertIsNone(unchanged_case["assessment"]["freigabe_durch_mensch"])

    def test_both_legal_demo_cases_are_schema_valid(self) -> None:
        with tempfile.TemporaryDirectory() as output:
            tsa = OpenSslTsaClient(
                tsa_url="http://127.0.0.1:1/tsr", timeout_seconds=0.1, max_attempts=1
            )
            covered = run_demo("kerngleich", Path(output) / "covered", tsa_client=tsa)
            not_covered = run_demo("nicht-umfasst", Path(output) / "not-covered", tsa_client=tsa)
            covered_case = json.loads(Path(covered.case_path).read_text(encoding="utf-8"))
            not_covered_case = json.loads(Path(not_covered.case_path).read_text(encoding="utf-8"))
        self.assertEqual("kerngleich_umfasst", covered_case["assessment"]["ergebnis"])
        self.assertEqual("nicht_umfasst", not_covered_case["assessment"]["ergebnis"])
        self.assertEqual("kerngleich", covered_case["clause_findings"][0]["classification"])
        self.assertEqual(
            "neuer_sachverhalt",
            not_covered_case["clause_findings"][0]["classification"],
        )


if __name__ == "__main__":
    unittest.main()
