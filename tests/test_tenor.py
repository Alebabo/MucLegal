from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from muclegal.live import LiveMonitorWorkflow
from muclegal.llm.tenor import (
    DeterministicTenorAnalyzer,
    OpenAITenorAnalyzer,
    TENOR_PROMPT_SHA256,
    TENOR_PROMPT_VERSION,
    TenorDraftValidationError,
    build_tenor_input,
    create_tenor_draft,
    create_tenor_proposals,
    validate_tenor_draft,
)
from muclegal.ui import create_app


ROOT = Path(__file__).resolve().parents[1]


def tenor_payload() -> dict:
    return {
        "fall_id": "VZ-TEST-001",
        "schuldner": "Synthetische Beispiel GmbH",
        "fundstelle": "https://example.org/angebot",
        "beschreibung": "mit einer nicht bestehenden Befristung zu werben",
        "rechtsgrundlagen": ["§ 5 UWG", "§ 8 Abs. 1 UWG"],
    }


class StrategyTenorAnalyzer(DeterministicTenorAnalyzer):
    mode = "test_openai"
    model = "test-model"

    def analyze(self, model_input: dict) -> dict:
        value = super().analyze(model_input)
        strategy = model_input["strategie"]["id"]
        value["entwurf"] = f"{value['entwurf']} Strategie: {strategy}."
        return value


class TenorDraftTests(unittest.TestCase):
    def test_tenor_prompt_is_separately_versioned(self) -> None:
        self.assertEqual("2026-08-19-tenor-draft-1", TENOR_PROMPT_VERSION)
        self.assertEqual(64, len(TENOR_PROMPT_SHA256))

    def test_deterministic_draft_is_valid_and_not_human_approved(self) -> None:
        model_input = build_tenor_input(**tenor_payload())
        draft, mode, _ = create_tenor_draft(model_input, DeterministicTenorAnalyzer())
        self.assertEqual("deterministic_demo", mode)
        self.assertIsNone(draft.freigabe_durch_mensch)
        self.assertTrue(draft.nicht_umfasst)
        self.assertEqual(tuple(model_input["rechtsgrundlagen"]), draft.rechtsgrundlagen)

    def test_unproven_legal_source_and_model_release_are_rejected(self) -> None:
        model_input = build_tenor_input(**tenor_payload())
        value = DeterministicTenorAnalyzer().analyze(model_input)
        value["rechtsgrundlagen"].append("§ 890 ZPO")
        with self.assertRaises(TenorDraftValidationError):
            validate_tenor_draft(value, allowed_legal_bases=model_input["rechtsgrundlagen"])
        value = DeterministicTenorAnalyzer().analyze(model_input)
        value["freigabe_durch_mensch"] = "freigegeben"
        with self.assertRaises(TenorDraftValidationError):
            validate_tenor_draft(value, allowed_legal_bases=model_input["rechtsgrundlagen"])

    def test_two_proposals_are_case_specific_and_require_human_review(self) -> None:
        model_input = build_tenor_input(**tenor_payload())
        result = create_tenor_proposals(
            model_input,
            StrategyTenorAnalyzer(),
            fallgruppe="irrefuehrende_werbung",
        )
        self.assertEqual("test_openai", result["mode"])
        self.assertEqual(["precise", "neutral"], [item["strategy"] for item in result["proposals"]])
        self.assertNotEqual(result["proposals"][0]["text"], result["proposals"][1]["text"])
        self.assertTrue(all(item["human_approval_required"] for item in result["proposals"]))
        self.assertTrue(all(item["freigabe_durch_mensch"] is None for item in result["proposals"]))

    def test_openai_analyzer_uses_frozen_prompt_and_structured_output(self) -> None:
        class FakeResponses:
            def __init__(self) -> None:
                self.request = None

            def create(self, **kwargs):
                self.request = kwargs
                value = DeterministicTenorAnalyzer().analyze(tenor_payload() | {
                    "beschreibung": tenor_payload()["beschreibung"],
                })
                return type(
                    "Response",
                    (),
                    {"status": "completed", "output_text": json.dumps(value)},
                )()

        responses = FakeResponses()
        client = type("Client", (), {"responses": responses})()
        analyzer = OpenAITenorAnalyzer(model="test-model", client=client)
        analyzer.analyze(build_tenor_input(**tenor_payload()))
        self.assertEqual("test-model", responses.request["model"])
        self.assertIn("prüfbedürftigen Entwurf", responses.request["instructions"])
        self.assertTrue(responses.request["text"]["format"]["strict"])
        self.assertFalse(responses.request["store"])

    def test_api_requires_human_review_before_workflow_uses_draft(self) -> None:
        with tempfile.TemporaryDirectory() as output:
            root = Path(output)
            workflow = LiveMonitorWorkflow(root, ROOT / "fixtures" / "tenor.json")
            original = workflow.tenor["fall_id"]
            app = create_app(
                workflow.latest_case_path,
                root / "reviews.sqlite3",
                workflow=workflow,
                anthropic_ready=True,
                asset_directory=ROOT / "assets",
            )
            with TestClient(app) as client:
                created = client.post("/api/tenor-drafts", json=tenor_payload())
                self.assertEqual(201, created.status_code, created.text)
                record = created.json()
                self.assertEqual(original, workflow.tenor["fall_id"])
                approved = client.post(
                    f"/api/tenor-drafts/{record['draft_id']}/review",
                    json={"decision": "freigegeben"},
                )
                self.assertEqual(200, approved.status_code, approved.text)
            self.assertEqual("VZ-TEST-001", workflow.tenor["fall_id"])
            saved = json.loads((root / "approved-tenor.json").read_text(encoding="utf-8"))
            self.assertEqual("VZ-TEST-001", saved["fall_id"])
            restarted = LiveMonitorWorkflow(root, ROOT / "fixtures" / "tenor.json")
            self.assertEqual("VZ-TEST-001", restarted.tenor["fall_id"])

    def test_proposal_api_returns_two_validated_strategies(self) -> None:
        with tempfile.TemporaryDirectory() as output:
            root = Path(output)
            app = create_app(
                root / "latest-case.json",
                root / "reviews.sqlite3",
                tenor_proposal_analyzer_factory=StrategyTenorAnalyzer,
            )
            payload = {
                "fall_id": "VZ-TEST-001",
                "schuldner": "Synthetische Beispiel GmbH",
                "fundstelle": "https://example.org/angebot",
                "context": (
                    "Die Synthetische Beispiel GmbH soll es unterlassen, gegenüber "
                    "Verbrauchern auf ihrer Website mit einer nicht bestehenden "
                    "Befristung zu werben."
                ),
                "fallgruppe": "irrefuehrende_werbung",
                "rechtsgrundlagen": ["§ 5 UWG", "§ 8 Abs. 1 UWG"],
            }
            with TestClient(app) as client:
                response = client.post("/api/v1/tenor-proposals", json=payload)
            self.assertEqual(200, response.status_code, response.text)
            result = response.json()
            self.assertEqual(["precise", "neutral"], [
                item["strategy"] for item in result["proposals"]
            ])
            self.assertTrue(all(item["freigabe_durch_mensch"] is None for item in result["proposals"]))

    def test_proposal_api_explains_exhausted_openai_credit(self) -> None:
        class ExhaustedAnalyzer:
            mode = "live_openai"
            model = "test-model"

            def analyze(self, model_input: dict) -> dict:
                del model_input
                raise Exception("429 credit_balance_exhausted: no credits remaining")

        with tempfile.TemporaryDirectory() as output:
            root = Path(output)
            app = create_app(
                root / "latest-case.json",
                root / "reviews.sqlite3",
                tenor_proposal_analyzer_factory=ExhaustedAnalyzer,
            )
            payload = {
                "fall_id": "VZ-TEST-001",
                "schuldner": "Synthetische Beispiel GmbH",
                "fundstelle": "https://example.org/angebot",
                "context": (
                    "Die Synthetische Beispiel GmbH soll es unterlassen, gegenüber "
                    "Verbrauchern auf ihrer Website mit einer falschen Frist zu werben."
                ),
                "fallgruppe": "irrefuehrende_werbung",
                "rechtsgrundlagen": ["§ 5 UWG", "§ 8 Abs. 1 UWG"],
            }
            with TestClient(app) as client:
                response = client.post("/api/v1/tenor-proposals", json=payload)
            self.assertEqual(502, response.status_code, response.text)
            self.assertIn("API-Guthaben ist aufgebraucht", response.json()["detail"])

    def test_tenor_api_rejects_unknown_fields(self) -> None:
        with tempfile.TemporaryDirectory() as output:
            root = Path(output)
            workflow = LiveMonitorWorkflow(root, ROOT / "fixtures" / "tenor.json")
            app = create_app(
                workflow.latest_case_path,
                root / "reviews.sqlite3",
                workflow=workflow,
                anthropic_ready=True,
            )
            payload = {**tenor_payload(), "freigabe_durch_mensch": "freigegeben"}
            with TestClient(app) as client:
                response = client.post("/api/tenor-drafts", json=payload)
            self.assertEqual(422, response.status_code)


if __name__ == "__main__":
    unittest.main()
