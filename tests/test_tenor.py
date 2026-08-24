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
from muclegal.llm.tenor_questions import (
    QUESTION_TOPICS,
    TENOR_QUESTION_PROMPT_VERSION,
    OpenAITenorQuestionAnalyzer,
    TenorQuestionValidationError,
    build_tenor_question_input,
    create_tenor_question,
    questions_are_similar,
    validate_tenor_question,
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


class ContextualQuestionAnalyzer:
    mode = "test_openai"
    model = "test-question-model"

    def analyze(self, model_input: dict) -> dict:
        if model_input["beantwortete_rueckfragen"]:
            return {"ready_to_generate": True, "question": None}
        return {
            "ready_to_generate": False,
            "question": {
                "topic_id": "taeuschungstatsache",
                "text": "Bestand die genannte Rabattfrist tatsächlich?",
                "answer_type": "yes_no",
                "placeholder": None,
                "slider": None,
                "options": [],
            },
        }


class SequenceQuestionAnalyzer:
    mode = "test_openai"
    model = "test-question-model"

    def __init__(self, *responses: dict) -> None:
        self.responses = list(responses)
        self.inputs: list[dict] = []

    def analyze(self, model_input: dict) -> dict:
        self.inputs.append(model_input)
        if not self.responses:
            raise AssertionError("Kein weiterer Test-Output vorbereitet.")
        return self.responses.pop(0)


def question_value(
    *,
    topic_id: str,
    text: str,
    answer_type: str = "text",
    options: list[dict[str, str]] | None = None,
    slider: dict | None = None,
    placeholder: str | None = None,
) -> dict:
    return {
        "ready_to_generate": False,
        "question": {
            "topic_id": topic_id,
            "text": text,
            "answer_type": answer_type,
            "placeholder": placeholder,
            "slider": slider,
            "options": options or [],
        },
    }


class TenorDraftTests(unittest.TestCase):
    def test_tenor_prompt_is_separately_versioned(self) -> None:
        self.assertEqual("2026-08-19-tenor-draft-1", TENOR_PROMPT_VERSION)
        self.assertEqual(64, len(TENOR_PROMPT_SHA256))
        self.assertEqual("2026-08-24-tenor-questions-2", TENOR_QUESTION_PROMPT_VERSION)

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
        self.assertIn("Unterlassungsmonitor-Wissensdokument", result["reference_version"])
        self.assertTrue(all("KW-002" in item["source_ids"] for item in result["proposals"]))

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

    def test_contextual_question_api_uses_prior_answers(self) -> None:
        with tempfile.TemporaryDirectory() as output:
            root = Path(output)
            app = create_app(
                root / "latest-case.json",
                root / "reviews.sqlite3",
                tenor_question_analyzer_factory=ContextualQuestionAnalyzer,
            )
            payload = {
                "context": (
                    "Die Beispiel GmbH wirbt auf ihrer Website gegenüber Verbrauchern "
                    "mit einer angeblich nur heute geltenden Frist."
                ),
                "fallgruppe": "irrefuehrende_werbung",
                "answered_questions": [],
            }
            with TestClient(app) as client:
                question = client.post("/api/v1/tenor-questions", json=payload)
                self.assertEqual(200, question.status_code, question.text)
                self.assertEqual("yes_no", question.json()["question"]["answer_type"])
                payload["answered_questions"] = [{
                    "topic_id": question.json()["question"]["topic_id"],
                    "question": question.json()["question"]["text"],
                    "answer": "Nein",
                    "answer_type": "yes_no",
                }]
                ready = client.post("/api/v1/tenor-questions", json=payload)
            self.assertEqual(200, ready.status_code, ready.text)
            self.assertTrue(ready.json()["ready_to_generate"])
            self.assertIsNone(ready.json()["question"])

    def test_slider_question_is_strictly_validated(self) -> None:
        model_input = build_tenor_question_input(
            context="Die Aktion lief mit einem sichtbaren Countdown auf der Website.",
            fallgruppe="irrefuehrende_werbung",
            answered_questions=[],
        )
        raw = question_value(
            topic_id="quantifizierbare_dauer_oder_anzahl",
            text="Wie viele Tage lief der Countdown?",
            answer_type="slider",
            slider={
                "minimum": 0,
                "maximum": 30,
                "step": 1,
                "minimum_label": "am selben Tag",
                "maximum_label": "30 Tage",
                "unit": "Tage",
            },
        )
        result = create_tenor_question(
            model_input,
            type(
                "SliderAnalyzer",
                (),
                {"mode": "test", "model": "test", "analyze": lambda self, _: raw},
            )(),
        )
        self.assertEqual(15, result["question"]["slider"]["maximum"] // 2)
        raw["question"]["slider"]["maximum"] = 0
        with self.assertRaises(TenorQuestionValidationError):
            validate_tenor_question(raw, model_input=model_input)

    def test_agb_catalog_excludes_usage_context_and_accepts_immediate_ready(self) -> None:
        model_input = build_tenor_question_input(
            context=(
                "Die Beispiel GmbH verwendet gegenüber Verbrauchern die Klausel: "
                "‚Eine Kündigung ist ausschließlich schriftlich möglich.‘"
            ),
            fallgruppe="agb_klausel",
            answered_questions=[],
        )
        open_topic_ids = {
            item["topic_id"] for item in model_input["erlaubte_offene_themen"]
        }
        self.assertEqual(
            {"schuldner", "adressatenkreis", "klauselwortlaut", "sachlicher_anwendungsbereich"},
            open_topic_ids,
        )
        self.assertNotIn("fundstelle_werbung", open_topic_ids)
        analyzer = SequenceQuestionAnalyzer(
            question_value(
                topic_id="fundstelle_werbung",
                text="Auf welcher Website wird die Klausel verwendet?",
            ),
            {"ready_to_generate": True, "question": None},
        )
        result = create_tenor_question(model_input, analyzer)
        self.assertTrue(result["ready_to_generate"])
        self.assertEqual(2, len(analyzer.inputs))
        self.assertIn("Fallgruppe", analyzer.inputs[1]["abgelehnte_vorschlaege"][0]["grund"])

    def test_duplicate_topic_is_rejected_and_retried(self) -> None:
        model_input = build_tenor_question_input(
            context="Die Beispiel GmbH wirbt gegenüber Verbrauchern mit einer falschen Rabattfrist.",
            fallgruppe="irrefuehrende_werbung",
            answered_questions=[{
                "topic_id": "taeuschungstatsache",
                "question": "Bestand die Rabattfrist tatsächlich?",
                "answer": "Nein",
                "answer_type": "yes_no",
            }],
        )
        analyzer = SequenceQuestionAnalyzer(
            question_value(
                topic_id="taeuschungstatsache",
                text="War die Rabattfrist echt?",
                answer_type="yes_no",
            ),
            question_value(
                topic_id="nicht_umfasster_gegenfall",
                text="Wann wäre die Fristangabe tatsächlich zutreffend?",
            ),
        )
        result = create_tenor_question(model_input, analyzer)
        self.assertEqual("nicht_umfasster_gegenfall", result["question"]["topic_id"])
        self.assertEqual(2, len(analyzer.inputs))
        self.assertIn("bereits", analyzer.inputs[1]["abgelehnte_vorschlaege"][0]["grund"])

    def test_paraphrased_question_is_rejected_even_under_another_topic(self) -> None:
        previous = "An welcher Stelle erscheint die beanstandete Werbung?"
        paraphrase = "Wo genau erscheint die beanstandete Werbung?"
        self.assertTrue(questions_are_similar(previous, paraphrase))
        model_input = build_tenor_question_input(
            context="Die Beispiel GmbH wirbt gegenüber Verbrauchern mit einer falschen Rabattfrist.",
            fallgruppe="irrefuehrende_werbung",
            answered_questions=[{
                "topic_id": "fundstelle_werbung",
                "question": previous,
                "answer": "Auf der Produktdetailseite",
                "answer_type": "text",
            }],
        )
        analyzer = SequenceQuestionAnalyzer(
            question_value(
                topic_id="beanstandete_werbeaussage",
                text=paraphrase,
            ),
            question_value(
                topic_id="beanstandete_werbeaussage",
                text="Wie lautet die konkrete Rabattbehauptung?",
            ),
        )
        result = create_tenor_question(model_input, analyzer)
        self.assertEqual("Wie lautet die konkrete Rabattbehauptung?", result["question"]["text"])
        self.assertEqual(2, len(analyzer.inputs))

    def test_either_or_question_requires_choices_instead_of_yes_no(self) -> None:
        model_input = build_tenor_question_input(
            context="Die Beispiel GmbH wirbt gegenüber Verbrauchern mit einer unklaren Rabattfrist.",
            fallgruppe="irrefuehrende_werbung",
            answered_questions=[],
        )
        analyzer = SequenceQuestionAnalyzer(
            question_value(
                topic_id="taeuschungstatsache",
                text="War die Frist echt oder nur vorgetäuscht?",
                answer_type="yes_no",
            ),
            question_value(
                topic_id="taeuschungstatsache",
                text="Welche tatsächliche Situation lag vor?",
                answer_type="single_choice",
                options=[
                    {"value": "echte_frist", "label": "Die Frist bestand tatsächlich"},
                    {"value": "keine_frist", "label": "Die Frist bestand nicht"},
                ],
                placeholder="Andere tatsächliche Situation",
            ),
        )
        result = create_tenor_question(model_input, analyzer)
        self.assertEqual("single_choice", result["question"]["answer_type"])
        self.assertEqual(2, len(result["question"]["options"]))
        self.assertIn("Entweder-oder", analyzer.inputs[1]["abgelehnte_vorschlaege"][0]["grund"])

    def test_slider_is_rejected_for_non_numeric_topic(self) -> None:
        model_input = build_tenor_question_input(
            context="Die Beispiel GmbH wirbt gegenüber Verbrauchern mit einer unklaren Rabattfrist.",
            fallgruppe="irrefuehrende_werbung",
            answered_questions=[],
        )
        raw = question_value(
            topic_id="adressatenkreis",
            text="Wie stark ist der Verbraucherbezug?",
            answer_type="slider",
            slider={
                "minimum": 0,
                "maximum": 10,
                "step": 1,
                "minimum_label": "gering",
                "maximum_label": "hoch",
                "unit": None,
            },
        )
        with self.assertRaisesRegex(TenorQuestionValidationError, "fachlich nicht zulässig"):
            validate_tenor_question(raw, model_input=model_input)

    def test_three_invalid_questions_fail_instead_of_marking_ready(self) -> None:
        model_input = build_tenor_question_input(
            context="Die Beispiel GmbH verwendet gegenüber Verbrauchern eine unwirksame AGB-Klausel.",
            fallgruppe="agb_klausel",
            answered_questions=[],
        )
        invalid = question_value(
            topic_id="fundstelle_werbung",
            text="Auf welcher Website wurde die Klausel verwendet?",
        )
        analyzer = SequenceQuestionAnalyzer(invalid, invalid, invalid)
        with self.assertRaisesRegex(RuntimeError, "nach drei Versuchen"):
            create_tenor_question(model_input, analyzer)
        self.assertEqual(3, len(analyzer.inputs))
        self.assertEqual(2, len(analyzer.inputs[2]["abgelehnte_vorschlaege"]))

    def test_openai_question_analyzer_uses_separate_structured_prompt(self) -> None:
        class FakeResponses:
            def __init__(self) -> None:
                self.request = None

            def create(self, **kwargs):
                self.request = kwargs
                return type(
                    "Response",
                    (),
                    {
                        "status": "completed",
                        "output_text": json.dumps(
                            {"ready_to_generate": True, "question": None}
                        ),
                    },
                )()

        responses = FakeResponses()
        analyzer = OpenAITenorQuestionAnalyzer(
            model="test-model",
            client=type("Client", (), {"responses": responses})(),
        )
        analyzer.analyze({"sachverhalt": "Test", "beantwortete_rueckfragen": []})
        self.assertEqual("tenor_clarification_question", responses.request["text"]["format"]["name"])
        self.assertIn("genau eine kurze", responses.request["instructions"])
        self.assertTrue(responses.request["text"]["format"]["strict"])
        self.assertFalse(responses.request["store"])

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

    def test_tenor_archive_persists_minimal_and_mask_drafts(self) -> None:
        with tempfile.TemporaryDirectory() as output:
            root = Path(output)
            database = root / "reviews.sqlite3"
            app = create_app(root / "latest-case.json", database)
            archived_payload = {
                "fall_id": "VZ-ARCHIV-001",
                "schuldner": "Synthetische Beispiel GmbH",
                "title": "Rabattfrist auf der Angebotsseite",
                "text": "Der Antragsgegnerin wird untersagt, mit einer falschen Frist zu werben.",
                "context": "Die Rabattfrist auf der Website bestand tatsächlich nicht.",
                "strategy": "precise",
                "model": "test-model",
                "reference_version": "test-reference",
                "source_ids": ["KW-002"],
            }
            with TestClient(app) as client:
                archived = client.post("/api/v1/tenor-archive", json=archived_payload)
                self.assertEqual(201, archived.status_code, archived.text)
                mask = client.post("/api/v1/tenor-drafts", json=tenor_payload())
                self.assertEqual(201, mask.status_code, mask.text)
                listed = client.get("/api/v1/tenor-archive")
            self.assertEqual(200, listed.status_code, listed.text)
            records = listed.json()["tenors"]
            self.assertEqual({"minimal", "maske"}, {item["source"] for item in records})
            minimal = next(item for item in records if item["source"] == "minimal")
            self.assertEqual("VZ-ARCHIV-001", minimal["fall_id"])
            self.assertEqual(["KW-002"], minimal["source_ids"])

            restarted = create_app(root / "latest-case.json", database)
            with TestClient(restarted) as client:
                persisted = client.get("/api/v1/tenor-archive")
            self.assertEqual(2, len(persisted.json()["tenors"]))

    def test_tenor_archive_rejects_unknown_fields(self) -> None:
        with tempfile.TemporaryDirectory() as output:
            root = Path(output)
            app = create_app(root / "latest-case.json", root / "reviews.sqlite3")
            payload = {
                "fall_id": "VZ-ARCHIV-002",
                "schuldner": "Synthetische Beispiel GmbH",
                "title": "Test",
                "text": "Ein gespeicherter Tenor.",
                "context": "Ein synthetischer Sachverhalt.",
                "strategy": "neutral",
                "model": "test-model",
                "reference_version": "test-reference",
                "source_ids": [],
                "freigabe_durch_mensch": "freigegeben",
            }
            with TestClient(app) as client:
                response = client.post("/api/v1/tenor-archive", json=payload)
            self.assertEqual(422, response.status_code)

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
