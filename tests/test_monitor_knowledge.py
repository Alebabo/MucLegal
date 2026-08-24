from __future__ import annotations

from muclegal.clause_diff import ClausePair
from muclegal.llm.analyzer import build_model_input
from muclegal.llm.clause_analysis import build_clause_input, tenor_elements_from_tenor
from muclegal.llm.monitor_knowledge import (
    MONITOR_KNOWLEDGE_SOURCE_SHA256,
    MONITOR_KNOWLEDGE_STATUS,
    MONITOR_KNOWLEDGE_VERSION,
    build_monitor_knowledge,
)
from muclegal.normalize.clauses import Clause


def _ids(items: list[dict[str, str]]) -> set[str]:
    return {item["id"] for item in items}


def test_agb_bundle_contains_structure_limits_and_provenance() -> None:
    bundle = build_monitor_knowledge(
        fallgruppe="agb_klausel",
        text="Änderungen dieser AGB bedürfen der Schriftform im Fernabsatz.",
    )

    assert bundle["version"] == MONITOR_KNOWLEDGE_VERSION
    assert bundle["source_sha256"] == MONITOR_KNOWLEDGE_SOURCE_SHA256
    assert bundle["source_status"] == MONITOR_KNOWLEDGE_STATUS
    assert {"KW-002", "KW-004", "KW-005", "KW-006"} <= _ids(bundle["leitlinien"])
    assert "FALL-001" in _ids(bundle["fallreferenzen"])
    assert "schriftform" in _ids(bundle["erkannte_klauseltypen"])


def test_kuendigungsbutton_bundle_uses_sky_only_as_uncertainty_reference() -> None:
    bundle = build_monitor_knowledge(
        fallgruppe="kuendigungsbutton",
        text="Der Kündigungsbutton führt erst über einen Login zum Formular.",
    )

    assert "KW-008" in _ids(bundle["leitlinien"])
    sky = next(item for item in bundle["fallreferenzen"] if item["id"] == "FALL-011")
    assert "Unsicherheitsbeispiel" in sky["verwendung"]
    assert "datumskonflikt" in sky["status_im_wissensdokument"].casefold()


def test_frozen_assessment_prompt_receives_versioned_knowledge_as_input() -> None:
    tenor = {
        "fall_id": "VZ-TEST",
        "schuldner": "Synthetische Beispiel GmbH",
        "tenor": "Die Kündigungsbestätigungsseite muss unmittelbar erreichbar sein.",
        "verbotene_praxis": "Login-Hürde vor dem Kündigungsformular",
        "rechtsgrundlage": ["§ 312k BGB"],
    }

    model_input = build_model_input(
        tenor,
        "Kündigungsbutton führte direkt zum Formular.",
        "Kündigungsbutton führt zunächst zum Login.",
        {"fall_id": "VZ-TEST"},
    )

    assert model_input["wissensbasis"]["version"] == MONITOR_KNOWLEDGE_VERSION
    assert "FALL-011" in model_input["wissensbasis"]["source_ids"]


def test_clause_pair_input_receives_matching_clause_type() -> None:
    tenor = {
        "fall_id": "VZ-AGB",
        "tenor": "Die nachfolgenden oder inhaltsgleichen AGB-Klauseln sind untersagt.",
        "verbotene_praxis": "unzulässige Schriftformklausel",
        "fallgruppe": "agb_klausel",
        "kerngleich_umfasst": [],
        "nicht_umfasst": [],
    }
    previous = Clause(1, None, "Änderungen bedürfen der Schriftform.", "old")
    current = Clause(1, None, "Jede Ergänzung bedarf der Schriftform.", "new")
    pair = ClausePair(previous, current, 0.8)

    model_input = build_clause_input(tenor, pair, tenor_elements_from_tenor(tenor))

    assert "schriftform" in _ids(
        model_input["wissensbasis"]["erkannte_klauseltypen"]
    )
    assert "KW-005" in model_input["wissensbasis"]["source_ids"]
