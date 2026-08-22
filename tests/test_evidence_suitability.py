from muclegal.evidence.suitability import classify_technical_evidence


def test_complete_capture_is_only_described_as_technical_evidence() -> None:
    result = classify_technical_evidence(
        capture_completeness="vollstaendig_erfasst",
        has_screenshot=True,
        has_normalized_text=True,
        has_raw_capture=True,
        robots_status="geprueft_abruf_erlaubt",
    )

    assert result.code == "technisch_verwendbar"
    assert result.label == "Als technischer Beleg verwendbar"
    assert "rechtliche Verwertbarkeit" in result.meaning


def test_unchecked_robots_downgrades_to_limited() -> None:
    result = classify_technical_evidence(
        capture_completeness="vollstaendig_erfasst",
        has_screenshot=True,
        has_normalized_text=True,
        has_raw_capture=True,
        robots_status="ungeprueft",
    )

    assert result.code == "eingeschraenkt"
    assert result.label == "Nur eingeschränkt verwendbar"


def test_saved_empty_browser_state_is_a_hint_not_an_exception() -> None:
    result = classify_technical_evidence(
        capture_completeness="technisch_fehlgeschlagen",
        has_screenshot=True,
        has_normalized_text=False,
        has_raw_capture=True,
        robots_status="ungeprueft",
        failure_code="normalization_error",
        failure_kind="leerer_browserzustand",
    )

    assert result.code == "hinweis"
    assert result.label == "Nicht als Beleg verwendbar – nur Hinweis"
    assert "manuell sichern" in result.next_action


def test_private_target_has_terminal_not_capturable_result() -> None:
    result = classify_technical_evidence(
        capture_completeness="technisch_fehlgeschlagen",
        has_screenshot=False,
        has_normalized_text=False,
        has_raw_capture=False,
        robots_status=None,
        failure_code="non_public_target",
    )

    assert result.code == "nicht_erfassbar"
    assert result.label == "URL nicht erfassbar"
