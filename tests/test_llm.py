from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from muclegal.llm import OfflineAnalyzer, analyze_and_store, validate_assessment
from muclegal.llm.analyzer import AnthropicAnalyzer, MAX_OUTPUT_TOKENS, build_model_input
from muclegal.llm.prompt import PROMPT_SHA256, PROMPT_VERSION
from muclegal.llm.schema import ASSESSMENT_JSON_SCHEMA, AssessmentValidationError


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures"


class LlmAssessmentTests(unittest.TestCase):
    def test_frozen_prompt_version_and_hash_are_unchanged(self) -> None:
        self.assertEqual("2026-08-19-freeze-candidate-1", PROMPT_VERSION)
        self.assertEqual(
            "6c0e6c09e73faa18cc2c1ea196a7e18d1bdc01ec67708c463e8a3ca037be9289",
            PROMPT_SHA256,
        )

    def test_schema_describes_counterargument_as_nonempty(self) -> None:
        description = ASSESSMENT_JSON_SCHEMA["properties"]["staerkstes_gegenargument"][
            "description"
        ]
        self.assertIn("Nichtleeres", description)

    def test_live_analyzer_rejects_truncated_structured_output_before_parsing(self) -> None:
        class FakeMessages:
            def create(self, **kwargs):
                self.kwargs = kwargs
                return SimpleNamespace(
                    stop_reason="max_tokens",
                    content=[SimpleNamespace(type="text", text='{"unvollstaendig":')],
                )

        messages = FakeMessages()
        analyzer = AnthropicAnalyzer.__new__(AnthropicAnalyzer)
        analyzer.client = SimpleNamespace(messages=messages)

        with self.assertRaisesRegex(RuntimeError, "stop_reason='max_tokens'"):
            analyzer.analyze({"test": True})
        self.assertEqual(MAX_OUTPUT_TOKENS, messages.kwargs["max_tokens"])

    def _run_fixture(self, case_name: str):
        tenor = json.loads((FIXTURES / "tenor.json").read_text(encoding="utf-8"))
        case = json.loads((FIXTURES / f"llm-input-{case_name}.json").read_text(encoding="utf-8"))
        model_input = build_model_input(
            tenor,
            case["vorher"],
            case["nachher"],
            case["belegte_metadaten"],
        )
        with tempfile.TemporaryDirectory() as output:
            run = analyze_and_store(
                model_input,
                OfflineAnalyzer(FIXTURES / f"llm-output-{case_name}.json"),
                output,
            )
            saved_input = json.loads(Path(run.input_path).read_text(encoding="utf-8"))
            saved_output = json.loads(Path(run.output_path).read_text(encoding="utf-8"))
        return run, saved_input, saved_output

    def test_kerngleich_fixture_is_valid_and_requires_human_release(self) -> None:
        run, saved_input, saved_output = self._run_fixture("kerngleich")
        self.assertTrue(run.valid)
        self.assertEqual("offline_fixture", run.mode)
        self.assertEqual("kerngleich_umfasst", run.assessment.ergebnis)
        self.assertIsNone(run.assessment.freigabe_durch_mensch)
        self.assertEqual(saved_output, run.assessment.to_dict())
        self.assertNotIn("raw_html", saved_input["belegte_metadaten"])

    def test_not_covered_fixture_is_valid_and_explains_counterargument(self) -> None:
        run, _, _ = self._run_fixture("nicht-umfasst")
        self.assertTrue(run.valid)
        self.assertEqual("nicht_umfasst", run.assessment.ergebnis)
        self.assertTrue(run.assessment.staerkstes_gegenargument)
        self.assertTrue(run.assessment.unsicherheit)

    def test_invalid_output_is_saved_but_not_exposed_as_assessment(self) -> None:
        tenor = json.loads((FIXTURES / "tenor.json").read_text(encoding="utf-8"))
        model_input = build_model_input(tenor, "alt", "neu", {"fall_id": "VZ-2024-0417"})
        with tempfile.TemporaryDirectory() as output:
            invalid_path = Path(output) / "invalid.json"
            invalid_path.write_text('{"ergebnis":"kerngleich_umfasst"}', encoding="utf-8")
            run = analyze_and_store(model_input, OfflineAnalyzer(invalid_path), Path(output) / "run")
            self.assertTrue(Path(run.output_path).is_file())
        self.assertFalse(run.valid)
        self.assertIsNone(run.assessment)
        self.assertIn("Schemafelder", run.validation_error)

    def test_validator_rejects_model_created_human_release(self) -> None:
        value = json.loads((FIXTURES / "llm-output-kerngleich.json").read_text(encoding="utf-8"))
        value["freigabe_durch_mensch"] = "freigegeben"
        with self.assertRaises(AssessmentValidationError):
            validate_assessment(value)

    def test_missing_model_response_is_saved_as_error(self) -> None:
        class FailingAnalyzer:
            mode = "test"
            model = "test-model"

            def analyze(self, model_input):
                del model_input
                raise TimeoutError("Dienst nicht erreichbar")

        tenor = json.loads((FIXTURES / "tenor.json").read_text(encoding="utf-8"))
        model_input = build_model_input(tenor, "alt", "neu", {"fall_id": "VZ-2024-0417"})
        with tempfile.TemporaryDirectory() as output:
            run = analyze_and_store(model_input, FailingAnalyzer(), output)
            saved = json.loads(Path(run.output_path).read_text(encoding="utf-8"))
        self.assertFalse(run.valid)
        self.assertIsNone(run.assessment)
        self.assertIn("Modellantwort fehlt", run.validation_error)
        self.assertIn("_error", saved)


if __name__ == "__main__":
    unittest.main()
