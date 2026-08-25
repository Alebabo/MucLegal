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
    build_tenor_strategy_input,
    create_tenor_draft,
    create_tenor_proposals,
    validate_tenor_draft,
)
from muclegal.llm.tenor_examples import (
    UEExampleValidationError,
    eligible_source_ids,
    load_ue_examples,
    select_ue_examples,
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
        "beschreibung": (
            "im Rahmen geschäftlicher Handlungen gegenüber Verbrauchern auf Websites "
            "mit einer angeblich nur heute bestehenden Rabattfrist zu werben, obwohl "
            "die Frist tatsächlich nicht besteht"
        ),
        "rechtsgrundlagen": ["§ 5 UWG", "§ 8 Abs. 1 UWG"],
    }


class StrategyTenorAnalyzer(DeterministicTenorAnalyzer):
    mode = "test_openai"
    model = "test-model"

    def analyze(self, model_input: dict) -> dict:
        value = super().analyze(model_input)
        value["entwurf"] = f"{value['entwurf']} Vollständiger UE-Entwurf."
        return value


class EmptyExclusionTenorAnalyzer(StrategyTenorAnalyzer):
    def analyze(self, model_input: dict) -> dict:
        value = super().analyze(model_input)
        value["nicht_umfasst"] = []
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
        self.assertEqual("2026-08-25-ue-draft-2", TENOR_PROMPT_VERSION)
        self.assertEqual(
            "0405cee6e7f7b3bf05c4eb9d991a36433b61400257af63cdf776b5e67efac511",
            TENOR_PROMPT_SHA256,
        )
        self.assertEqual("2026-08-25-ue-questions-3", TENOR_QUESTION_PROMPT_VERSION)

    def test_deterministic_draft_is_valid_and_not_human_approved(self) -> None:
        model_input = build_tenor_input(**tenor_payload())
        draft, mode, _ = create_tenor_draft(model_input, DeterministicTenorAnalyzer())
        self.assertEqual("deterministic_demo", mode)
        self.assertIsNone(draft.freigabe_durch_mensch)
        self.assertTrue(draft.nicht_umfasst)
        self.assertEqual(tuple(model_input["rechtsgrundlagen"]), draft.rechtsgrundlagen)

    def test_complete_generation_and_missing_information_for_each_branch(self) -> None:
        cases = {
            "A": (
                "Gegenüber Verbrauchern auf Websites mit einer angeblich nur heute "
                "geltenden Rabattfrist zu werben, obwohl diese tatsächlich nicht besteht.",
                "Nur heute",
            ),
            "B": (
                "Gegenüber Verbrauchern auf https://example.org nach Klick auf den Button "
                "„Weiter zur Kasse“ danach das Fenster „Versicherung wählen“ einzublenden, "
                "wie in Anlage K 4 abgebildet.",
                "Weiter zur Kasse",
            ),
            "C": (
                "Gegenüber Verbrauchern die Klausel: „Eine Kündigung ist ausschließlich "
                "schriftlich möglich.“ zu verwenden.",
                "Eine Kündigung ist ausschließlich schriftlich möglich.",
            ),
        }
        for branch, (description, expected) in cases.items():
            with self.subTest(branch=branch):
                model_input = build_tenor_input(
                    fall_id=f"VZ-{branch}",
                    schuldner="Synthetische Beispiel GmbH",
                    fundstelle=None,
                    beschreibung=description,
                    rechtsgrundlagen=[],
                    violation_branch=branch,
                )
                result = create_tenor_proposals(
                    model_input,
                    DeterministicTenorAnalyzer(),
                    fallgruppe="agb_klausel" if branch == "C" else "irrefuehrende_werbung",
                )
                self.assertEqual("ready", result["status"])
                self.assertEqual(branch, result["violation_branch"])
                self.assertTrue(result["proposal"]["text"].startswith("…es zu unterlassen,"))
                if branch in {"B", "C"}:
                    self.assertIn(expected, result["proposal"]["text"])

        missing_contexts = {
            "A": "Eine Rabattfrist ist falsch.",
            "B": "Verbraucher sehen nach einem Klick auf einer Website einen Dialog.",
            "C": "Die Beispiel GmbH verwendet gegenüber Verbrauchern eine unwirksame Klausel.",
        }
        for branch, description in missing_contexts.items():
            with self.subTest(missing_branch=branch):
                model_input = build_tenor_input(
                    fall_id=f"MISS-{branch}",
                    schuldner="Synthetische Beispiel GmbH",
                    fundstelle=None,
                    beschreibung=description,
                    rechtsgrundlagen=[],
                    violation_branch=branch,
                )
                result = create_tenor_proposals(
                    model_input,
                    DeterministicTenorAnalyzer(),
                    fallgruppe="agb_klausel" if branch == "C" else "irrefuehrende_werbung",
                )
                self.assertEqual("needs_information", result["status"])
                self.assertIsNone(result["proposal"])
                self.assertTrue(result["missing_information"])

    def test_optional_metadata_does_not_block_a_complete_violation_description(self) -> None:
        model_input = build_tenor_input(
            fall_id="OPTIONAL-001",
            schuldner=None,
            fundstelle=None,
            beschreibung=(
                "Mit einer angeblich nur heute geltenden Rabattfrist zu werben, obwohl "
                "diese Frist tatsächlich nicht besteht."
            ),
            rechtsgrundlagen=[],
            violation_branch="A",
        )

        result = create_tenor_proposals(
            model_input,
            DeterministicTenorAnalyzer(),
            fallgruppe="irrefuehrende_werbung",
        )

        self.assertEqual("ready", result["status"])
        self.assertEqual([], result["missing_information"])
        self.assertEqual("Nicht angegeben", model_input["schuldner"])
        optional_hint = next(
            warning
            for warning in result["proposal"]["warnings"]
            if warning.startswith("Optional:")
        )
        for field in (
            "Schuldnerbezeichnung",
            "Adressatenkreis",
            "Fundstelle",
            "Rechtsgrundlagen",
            "Anwendungsbereich",
        ):
            self.assertIn(field, optional_hint)

    def test_numbered_agb_clause_is_recognized_without_quotes_or_label(self) -> None:
        clause_wording = (
            "Jegliche Ansprüche auf Gewährleistung erlöschen, sollte nachweislich "
            "eine Inbetriebnahme der Anlage durch Privatpersonen und ohne Zuhilfenahme "
            "eines zertifizierten Fachbetriebes erfolgen."
        )
        numbered_clause = f"Abs. 14.5 {clause_wording}"
        model_input = build_tenor_input(
            fall_id="VZ-2026-01",
            schuldner="RT-Specht GmbH",
            fundstelle="https://rt-specht.de/agb.html",
            beschreibung=(
                f"{numbered_clause}\n\n"
                "Adressatenkreis: gegenüber Verbraucherinnen und Verbrauchern"
            ),
            rechtsgrundlagen=["§ 309 Nr. 8 lit. b BGB"],
            violation_branch="C",
        )

        result = create_tenor_proposals(
            model_input,
            DeterministicTenorAnalyzer(),
            fallgruppe="agb_klausel",
        )

        self.assertEqual("ready", result["status"])
        self.assertIn(clause_wording, result["proposal"]["text"])
        self.assertNotIn("Adressatenkreis:", result["proposal"]["text"])

    def test_uploaded_contract_requires_explicit_clause_selection(self) -> None:
        document_context = (
            "Hochgeladenes Vertragsdokument: vertrag.pdf\n"
            "Umfang: 11 Seiten; Text aus 8 Seiten extrahiert.\n"
            "Hinweis: Der extrahierte Dokumenttext wurde wegen der Längenbegrenzung gekürzt.\n"
            "Dokumentinhalt:\n"
            "[Seite 1]\n"
            "Mitgliedsvertrag der Synthetische Beispiel GmbH mit Verbrauchern. "
            "Die Marke „Fit“ wird im Tarif „Flex Deal 2026“ genannt.\n\n"
            "[Seite 2]\n"
            "1. Allgemeine Bedingungen. Weitere Informationen stehen unter einem Link.\n\n"
            "[Seite 8]\n"
            "Datenschutzerklärung mit Schaltfläche und weiteren nummerierten Abschnitten"
        )

        model_input = build_tenor_question_input(
            context=document_context,
            fallgruppe="agb_klausel",
            answered_questions=[],
        )

        self.assertEqual("C", model_input["violation_branch"])
        self.assertIn("klauselwortlaut", model_input["erforderliche_offene_topic_ids"])
        self.assertNotIn(
            "klauselwortlaut",
            model_input["bereits_im_sachverhalt_abgedeckte_topic_ids"],
        )
        self.assertNotIn(
            "verletzungsast",
            model_input["erforderliche_offene_topic_ids"],
        )

        result = create_tenor_question(model_input, SequenceQuestionAnalyzer())
        self.assertFalse(result["ready_to_generate"])
        self.assertEqual("deterministic_required_fact", result["mode"])
        self.assertEqual("klauselwortlaut", result["question"]["topic_id"])
        self.assertEqual("text", result["question"]["answer_type"])
        self.assertIn("vollständig und wortwörtlich", result["question"]["text"])

        selected_clause = "Eine Kündigung ist ausschließlich schriftlich möglich."
        selected_context = (
            "Nutzerangaben:\n"
            "Der Tarif heißt „Flex Deal 2026“. Beanstandete Klausel: "
            f"„{selected_clause}“\n\n"
            "Hochgeladenes Vertragsdokument: vertrag.pdf\n"
            "Umfang: 11 Seiten; Text aus 8 Seiten extrahiert.\n"
            "Dokumentinhalt:\n"
            "[Seite 1]\nWeitere Vertragsbedingungen mit Produktbezeichnungen."
        )
        selected_input = build_tenor_question_input(
            context=selected_context,
            fallgruppe="agb_klausel",
            answered_questions=[],
        )
        self.assertNotIn(
            "klauselwortlaut", selected_input["erforderliche_offene_topic_ids"]
        )
        self.assertIn(
            "klauselwortlaut",
            selected_input["bereits_im_sachverhalt_abgedeckte_topic_ids"],
        )

    def test_explicit_clause_answer_overrides_uploaded_contract_text(self) -> None:
        clause_wording = (
            "Das Mitglied kann den Vertrag jederzeit mit einer Frist von vier Wochen kündigen."
        )
        clarified_context = (
            "Hochgeladenes Vertragsdokument: vertrag.pdf\n"
            "Umfang: 11 Seiten; Text aus 8 Seiten extrahiert.\n"
            "Dokumentinhalt:\n"
            "[Seite 1]\nVertrag der Synthetische Beispiel GmbH gegenüber Verbrauchern. "
            "Die Marke „Fit“ gehört zum Tarif „Flex Deal 2026“.\n\n"
            "[Seite 2]\n1. Allgemeine Vertragsbedingungen und weitere Klauseln.\n\n"
            "Ergänzende Angaben:\n"
            "Thema: klauselwortlaut\n"
            "Rückfrage: Wie lautet die konkret beanstandete Klausel vollständig und wortwörtlich?\n"
            f"Antwort: {clause_wording}"
        )
        model_input = build_tenor_input(
            fall_id="VZ-PDF-C",
            schuldner="Synthetische Beispiel GmbH",
            fundstelle=None,
            beschreibung=clarified_context,
            rechtsgrundlagen=[],
            violation_branch="C",
        )

        result = create_tenor_proposals(
            model_input,
            DeterministicTenorAnalyzer(),
            fallgruppe="agb_klausel",
        )

        self.assertEqual("ready", result["status"])
        self.assertIn(clause_wording, result["proposal"]["text"])
        self.assertNotIn("Flex Deal 2026", result["proposal"]["text"])

    def test_empty_exclusion_is_valid_and_reported_without_inventing_one(self) -> None:
        model_input = build_tenor_input(**tenor_payload())
        draft, _, _ = create_tenor_draft(model_input, EmptyExclusionTenorAnalyzer())
        self.assertEqual((), draft.nicht_umfasst)

        result = create_tenor_proposals(
            model_input,
            EmptyExclusionTenorAnalyzer(),
            fallgruppe="irrefuehrende_werbung",
        )
        self.assertEqual("ready", result["status"])
        self.assertIn(
            "Keine Abgrenzung zu nicht erfassten Verhaltensweisen belegt.",
            result["proposal"]["warnings"],
        )

    def test_validator_rejects_judgment_formulas_and_incomplete_branch_content(self) -> None:
        branch_b = build_tenor_input(
            fall_id="VZ-B",
            schuldner="Beispiel GmbH",
            fundstelle="https://example.org",
            beschreibung=(
                "Gegenüber Verbrauchern nach Rechtsklick auf „Video“ und danach Klick auf "
                "„Feeds verwalten“ ein Menü zu zeigen, wie in Anlage K 2 abgebildet."
            ),
            rechtsgrundlagen=[],
            violation_branch="B",
        )
        base = DeterministicTenorAnalyzer().analyze(branch_b)
        forbidden = [
            "Die Beklagte wird verurteilt, es zu unterlassen, etwas zu tun.",
            "Es wird untersagt, etwas zu tun.",
            "…es zu unterlassen, etwas bei Meidung eines Ordnungsgeldes zu tun.",
        ]
        for text in forbidden:
            with self.subTest(text=text):
                value = {**base, "entwurf": text}
                with self.assertRaises(TenorDraftValidationError):
                    validate_tenor_draft(value, allowed_legal_bases=[], model_input=branch_b)
        incomplete_b = {
            **base,
            "entwurf": "…es zu unterlassen, gegenüber Verbrauchern ein Menü zu zeigen, wie in Anlage K 2.",
        }
        with self.assertRaises(TenorDraftValidationError):
            validate_tenor_draft(incomplete_b, allowed_legal_bases=[], model_input=branch_b)

        branch_c = build_tenor_input(
            fall_id="VZ-C",
            schuldner="Beispiel GmbH",
            fundstelle=None,
            beschreibung="Gegenüber Verbrauchern die Klausel: „Nur schriftliche Kündigung.“ zu verwenden.",
            rechtsgrundlagen=[],
            violation_branch="C",
        )
        paraphrased = DeterministicTenorAnalyzer().analyze(branch_c)
        paraphrased["entwurf"] = "…es zu unterlassen, eine Klausel über die Schriftform zu verwenden."
        with self.assertRaisesRegex(TenorDraftValidationError, "wörtlich"):
            validate_tenor_draft(paraphrased, allowed_legal_bases=[], model_input=branch_c)

    def test_reference_inventory_and_prompt_eligibility_are_strict(self) -> None:
        records = load_ue_examples()
        source_urls = {item["source_url"] for item in records}
        self.assertEqual(51, len(records))
        self.assertEqual(49, len(source_urls))
        eligible = set(eligible_source_ids())
        self.assertTrue(eligible)
        self.assertTrue(all(item.get("primary_verification_url") for item in records if item["prompt_eligible"]))
        selected = select_ue_examples(
            branch="B",
            fallgruppe="kuendigungsbutton",
            text="Klick auf Kündigen und Anlage",
        )
        self.assertLessEqual(len(selected), 3)
        self.assertTrue({item["source_id"] for item in selected}.issubset(eligible))

        source_payload = json.loads(
            (ROOT / "reference" / "ue_examples.json").read_text(encoding="utf-8")
        )
        mutations = []
        mismatch = json.loads(json.dumps(source_payload))
        mismatch["examples"][8]["prompt_eligible"] = True
        mismatch["examples"][8]["quarantine_reason"] = ""
        mutations.append(mismatch)
        truncated = json.loads(json.dumps(source_payload))
        truncated["examples"] = truncated["examples"][:50]
        mutations.append(truncated)
        duplicate = json.loads(json.dumps(source_payload))
        duplicate["examples"][1]["id"] = duplicate["examples"][0]["id"]
        mutations.append(duplicate)
        scan_only = json.loads(json.dumps(source_payload))
        scan_only["examples"][6]["primary_verification_url"] = "https://example.org/scan.pdf"
        mutations.append(scan_only)
        with tempfile.TemporaryDirectory() as output:
            for index, mutation in enumerate(mutations):
                path = Path(output) / f"invalid-{index}.json"
                path.write_text(json.dumps(mutation), encoding="utf-8")
                with self.assertRaises(UEExampleValidationError):
                    load_ue_examples(path)

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

    def test_one_complete_proposal_is_case_specific_and_requires_human_review(self) -> None:
        model_input = build_tenor_input(**tenor_payload())
        result = create_tenor_proposals(
            model_input,
            StrategyTenorAnalyzer(),
            fallgruppe="irrefuehrende_werbung",
        )
        self.assertEqual("test_openai", result["mode"])
        self.assertEqual("ready", result["status"])
        self.assertEqual("A", result["violation_branch"])
        self.assertEqual("complete", result["proposal"]["strategy"])
        self.assertTrue(result["proposal"]["human_approval_required"])
        self.assertIsNone(result["proposal"]["freigabe_durch_mensch"])
        self.assertEqual("ue-examples-2026-08-25-v1", result["reference_version"])
        self.assertNotIn("KW-002", result["proposal"]["source_ids"])

    def test_mask_input_uses_the_same_complete_generator_and_verified_examples(self) -> None:
        model_input = build_tenor_input(**tenor_payload())
        enriched, source_ids, reference_version = build_tenor_strategy_input(
            model_input,
            fallgruppe="irrefuehrende_werbung",
            strategy="neutral",
        )
        self.assertEqual("A", enriched["violation_branch"])
        self.assertEqual("irrefuehrende_werbung", enriched["fallgruppe"])
        self.assertEqual(source_ids, [item["source_id"] for item in enriched["referenzbeispiele"]])
        self.assertEqual("ue-examples-2026-08-25-v1", reference_version)
        self.assertNotIn("wissensbasis", enriched)

    def test_mask_api_enriches_a_selected_fallgruppe(self) -> None:
        with tempfile.TemporaryDirectory() as output:
            root = Path(output)
            app = create_app(
                root / "latest-case.json",
                root / "reviews.sqlite3",
                tenor_analyzer_factory=StrategyTenorAnalyzer,
            )
            payload = tenor_payload() | {"fallgruppe": "irrefuehrende_werbung"}
            with TestClient(app) as client:
                response = client.post("/api/v1/tenor-drafts", json=payload)
            self.assertEqual(201, response.status_code, response.text)
            record = response.json()
            self.assertEqual("A", record["input"]["violation_branch"])
            self.assertEqual("irrefuehrende_werbung", record["input"]["fallgruppe"])
            self.assertIn("referenzbeispiele", record["input"])

    def test_mask_api_accepts_numbered_agb_clause_from_form(self) -> None:
        clause_wording = (
            "Jegliche Ansprüche auf Gewährleistung erlöschen, sollte nachweislich "
            "eine Inbetriebnahme der Anlage durch Privatpersonen und ohne Zuhilfenahme "
            "eines zertifizierten Fachbetriebes erfolgen."
        )
        numbered_clause = f"Abs. 14.5 {clause_wording}"
        with tempfile.TemporaryDirectory() as output:
            root = Path(output)
            app = create_app(
                root / "latest-case.json",
                root / "reviews.sqlite3",
                tenor_analyzer_factory=StrategyTenorAnalyzer,
            )
            payload = {
                "fall_id": "VZ-2026-01",
                "schuldner": "RT-Specht GmbH",
                "fundstelle": "https://rt-specht.de/agb.html",
                "beschreibung": (
                    f"{numbered_clause}\n\n"
                    "Adressatenkreis: gegenüber Verbraucherinnen und Verbrauchern"
                ),
                "rechtsgrundlagen": ["§ 309 Nr. 8 lit. b BGB"],
                "fallgruppe": "agb_klausel",
            }
            with TestClient(app) as client:
                response = client.post("/api/v1/tenor-drafts", json=payload)

        self.assertEqual(201, response.status_code, response.text)
        record = response.json()
        self.assertIn(clause_wording, record["draft"]["entwurf"])
        self.assertNotIn("Adressatenkreis:", record["draft"]["entwurf"])

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
        self.assertIn("AUSSCHLIESSLICH der Text für eine Unterlassungserklärung", responses.request["instructions"])
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

    def test_proposal_api_returns_one_validated_complete_draft(self) -> None:
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
            self.assertEqual("ready", result["status"])
            self.assertEqual("complete", result["proposal"]["strategy"])
            self.assertIsNone(result["proposal"]["freigabe_durch_mensch"])
            self.assertEqual([], result["missing_information"])

    def test_proposal_api_accepts_missing_optional_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as output:
            root = Path(output)
            app = create_app(
                root / "latest-case.json",
                root / "reviews.sqlite3",
                tenor_proposal_analyzer_factory=StrategyTenorAnalyzer,
            )
            payload = {
                "fall_id": "OPTIONAL-API-001",
                "context": (
                    "Mit einer angeblich nur heute geltenden Rabattfrist zu werben, "
                    "obwohl diese Frist tatsächlich nicht besteht."
                ),
                "fallgruppe": "irrefuehrende_werbung",
                "rechtsgrundlagen": [],
                "violation_branch": "A",
            }
            with TestClient(app) as client:
                response = client.post("/api/v1/tenor-proposals", json=payload)

        self.assertEqual(200, response.status_code, response.text)
        result = response.json()
        self.assertEqual("ready", result["status"])
        self.assertTrue(
            any(
                warning.startswith("Optional:")
                for warning in result["proposal"]["warnings"]
            )
        )

    def test_mask_api_accepts_missing_debtor(self) -> None:
        with tempfile.TemporaryDirectory() as output:
            root = Path(output)
            app = create_app(
                root / "latest-case.json",
                root / "reviews.sqlite3",
                tenor_analyzer_factory=StrategyTenorAnalyzer,
            )
            payload = {
                "fall_id": "TENOR-ENTWURF",
                "beschreibung": (
                    "Mit einer angeblich nur heute geltenden Rabattfrist zu werben, "
                    "obwohl diese Frist tatsächlich nicht besteht."
                ),
                "fallgruppe": "irrefuehrende_werbung",
                "rechtsgrundlagen": [],
                "violation_branch": "A",
            }
            with TestClient(app) as client:
                response = client.post("/api/v1/tenor-drafts", json=payload)

        self.assertEqual(201, response.status_code, response.text)
        self.assertEqual("Nicht angegeben", response.json()["draft"]["schuldner"])

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

    def test_branch_choice_appears_only_for_genuine_ambiguity(self) -> None:
        ambiguous = build_tenor_question_input(
            context=(
                "Die Beispiel GmbH bietet gegenüber Verbrauchern online einen "
                "Kündigungsbutton an; die konkrete Beanstandung ist noch nicht beschrieben."
            ),
            fallgruppe="kuendigungsbutton",
            answered_questions=[],
        )
        result = create_tenor_question(ambiguous, ContextualQuestionAnalyzer())
        self.assertEqual("verletzungsast", result["question"]["topic_id"])
        self.assertEqual("single_choice", result["question"]["answer_type"])
        self.assertEqual(
            [
                "vollständig textlich beschreibbar",
                "nur mit Screenshot/Klickpfad verständlich",
                "wörtliche Vertrags-/AGB-Klausel",
            ],
            [item["label"] for item in result["question"]["options"]],
        )

        answered = build_tenor_question_input(
            context=ambiguous["sachverhalt"],
            fallgruppe="kuendigungsbutton",
            answered_questions=[{
                "topic_id": "verletzungsast",
                "question": result["question"]["text"],
                "answer": "nur mit Screenshot/Klickpfad verständlich",
                "answer_type": "single_choice",
            }],
        )
        self.assertEqual("B", answered["violation_branch"])
        self.assertNotIn("verletzungsast", answered["erforderliche_offene_topic_ids"])

        clear = build_tenor_question_input(
            context=(
                "Die Beispiel GmbH wirbt gegenüber Verbrauchern auf ihrer Website mit "
                "einer falschen Rabattfrist, die tatsächlich nicht besteht."
            ),
            fallgruppe="irrefuehrende_werbung",
            answered_questions=[],
        )
        self.assertNotIn(
            "verletzungsast",
            {item["topic_id"] for item in clear["erlaubte_offene_themen"]},
        )

    def test_slider_question_is_not_part_of_the_new_catalog(self) -> None:
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
        with self.assertRaisesRegex(TenorQuestionValidationError, "Faktenkatalog"):
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
        self.assertEqual({"sachlicher_anwendungsbereich"}, open_topic_ids)
        self.assertEqual(
            {"schuldner", "adressatenkreis", "klauselwortlaut"},
            set(model_input["bereits_im_sachverhalt_abgedeckte_topic_ids"]),
        )
        self.assertNotIn("fundstelle_werbung", open_topic_ids)
        analyzer = SequenceQuestionAnalyzer(
            question_value(
                topic_id="fundstelle_werbung",
                text="Auf welcher Website wird die Klausel verwendet?",
            ),
            question_value(
                topic_id="sachlicher_anwendungsbereich",
                text="Auf welcher Website wird die Klausel verwendet?",
            ),
            {"ready_to_generate": True, "question": None},
        )
        result = create_tenor_question(model_input, analyzer)
        self.assertTrue(result["ready_to_generate"])
        self.assertEqual(3, len(analyzer.inputs))
        self.assertIn("Fallgruppe", analyzer.inputs[1]["abgelehnte_vorschlaege"][0]["grund"])
        self.assertIn("Verwendungskontext", analyzer.inputs[2]["abgelehnte_vorschlaege"][1]["grund"])

    def test_optional_debtor_and_addressee_are_not_follow_up_questions(self) -> None:
        model_input = build_tenor_question_input(
            context="Beanstandete Klausel: ‚Eine Kündigung ist ausschließlich schriftlich möglich.‘",
            fallgruppe="agb_klausel",
            answered_questions=[],
        )
        open_topic_ids = {
            item["topic_id"] for item in model_input["erlaubte_offene_themen"]
        }
        self.assertNotIn("schuldner", open_topic_ids)
        self.assertNotIn("adressatenkreis", open_topic_ids)
        self.assertEqual([], model_input["erforderliche_offene_topic_ids"])

        analyzer = SequenceQuestionAnalyzer({"ready_to_generate": True, "question": None})
        result = create_tenor_question(model_input, analyzer)
        self.assertTrue(result["ready_to_generate"])

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
            context="Die Beispiel GmbH wirbt mit einer unklaren Rabattfrist.",
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
            context="Die Beispiel GmbH wirbt mit einer unklaren Rabattfrist.",
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
            context=(
                "Die Beispiel GmbH verwendet gegenüber Verbrauchern die Klausel: "
                "‚Eine Kündigung ist ausschließlich schriftlich möglich.‘"
            ),
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
