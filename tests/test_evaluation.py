from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from muclegal.evaluation import run_evaluation
from muclegal.llm.prompt import PROMPT_SHA256, PROMPT_VERSION


ROOT = Path(__file__).resolve().parents[1]


class EvaluationTests(unittest.TestCase):
    def test_offline_suite_passes_all_gates_and_records_prompt_hash(self) -> None:
        with tempfile.TemporaryDirectory() as output:
            report = run_evaluation(ROOT / "fixtures/eval-suite.json", output)
            saved = json.loads(Path(report.json_path).read_text(encoding="utf-8"))
            markdown = Path(report.markdown_path).read_text(encoding="utf-8")
        self.assertTrue(report.passed)
        self.assertEqual(12, len(report.cases))
        self.assertTrue(all(value == 1.0 for value in report.metrics.values()))
        self.assertEqual(PROMPT_VERSION, saved["prompt_version"])
        self.assertEqual(PROMPT_SHA256, saved["prompt_sha256"])
        self.assertIn("BESTANDEN", markdown)
        self.assertIn("keine abschließende Rechtsentscheidung", markdown)

    def test_wrong_expected_result_fails_accuracy_gate(self) -> None:
        fixtures = ROOT / "fixtures"
        suite = json.loads((fixtures / "eval-suite.json").read_text(encoding="utf-8"))
        suite["cases"][0]["expected_result"] = "nicht_umfasst"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in (
                "tenor.json",
                "llm-input-kerngleich.json",
                "llm-input-nicht-umfasst.json",
                "llm-output-kerngleich.json",
                "llm-output-nicht-umfasst.json",
            ):
                (root / name).write_bytes((fixtures / name).read_bytes())
            suite_path = root / "suite.json"
            suite_path.write_text(json.dumps(suite), encoding="utf-8")
            report = run_evaluation(suite_path, root / "output")
        self.assertFalse(report.passed)
        self.assertAlmostEqual(11 / 12, report.metrics["result_accuracy"])
        self.assertFalse(report.gate_results["result_accuracy"])

    def test_suite_rejects_paths_outside_its_directory(self) -> None:
        suite = {
            "version": 1,
            "name": "invalid",
            "tenor_path": "../tenor.json",
            "gates": {name: 1.0 for name in (
                "schema_valid_rate",
                "result_accuracy",
                "human_release_null_rate",
                "reasoning_rate",
                "counterargument_rate",
            )},
            "cases": [{
                "id": "invalid-path",
                "input_path": "../input.json",
                "offline_response_path": "../output.json",
                "expected_result": "unklar",
            }],
        }
        with tempfile.TemporaryDirectory() as directory:
            suite_path = Path(directory) / "suite.json"
            suite_path.write_text(json.dumps(suite), encoding="utf-8")
            with self.assertRaises(ValueError):
                run_evaluation(suite_path, Path(directory) / "results")


if __name__ == "__main__":
    unittest.main()
