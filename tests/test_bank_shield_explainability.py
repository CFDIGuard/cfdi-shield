from app.modules.bank_shield.services.reconciliation_service import (
    MAX_BREAKDOWN_CHIPS,
    STRONG_EVIDENCE_MIN_CHIPS,
    WEAK_EVIDENCE_MAX_CHIPS,
    _score_breakdown_for_ui,
    invoice_unavailable_for_ui,
)


def _chip_keys(breakdown: dict[str, object]) -> list[str]:
    chips = breakdown["chips"]
    return [chip["key"] for chip in chips]


def test_score_breakdown_returns_expected_structure_for_uuid_evidence():
    breakdown = _score_breakdown_for_ui(
        match_reason="UUID detectado en referencia o descripcion",
        invoice_unavailable=False,
    )

    assert set(breakdown.keys()) == {"chips", "summary", "confidence_hint"}
    assert breakdown["summary"] == "UUID detectado en referencia o descripcion"
    assert breakdown["confidence_hint"] == "evidence_strong"
    assert breakdown["chips"] == [{"key": "uuid", "label": "UUID", "tone": "positive"}]


def test_score_breakdown_maps_amount_evidence_with_current_weak_hint():
    breakdown = _score_breakdown_for_ui(
        match_reason="Monto exacto",
        invoice_unavailable=False,
    )

    assert _chip_keys(breakdown) == ["amount"]
    assert breakdown["chips"][0]["label"] == "Monto"
    assert breakdown["confidence_hint"] == "evidence_weak"
    assert len(breakdown["chips"]) <= WEAK_EVIDENCE_MAX_CHIPS


def test_score_breakdown_maps_rfc_and_supplier_evidence():
    breakdown = _score_breakdown_for_ui(
        match_reason="RFC detectado en descripcion; Proveedor detectado en descripcion",
        invoice_unavailable=False,
    )

    assert _chip_keys(breakdown) == ["rfc", "supplier"]
    assert [chip["label"] for chip in breakdown["chips"]] == ["RFC", "Proveedor"]
    assert breakdown["confidence_hint"] == "evidence_partial"


def test_score_breakdown_marks_three_chips_as_strong_evidence():
    breakdown = _score_breakdown_for_ui(
        match_reason="Monto exacto; Fecha dentro de 2 dias; Moneda coincide",
        invoice_unavailable=False,
    )

    assert len(breakdown["chips"]) == STRONG_EVIDENCE_MIN_CHIPS
    assert _chip_keys(breakdown) == ["amount", "date", "currency"]
    assert breakdown["confidence_hint"] == "evidence_strong"


def test_score_breakdown_handles_missing_or_insufficient_evidence():
    none_breakdown = _score_breakdown_for_ui(match_reason=None, invoice_unavailable=False)
    insufficient_breakdown = _score_breakdown_for_ui(
        match_reason="Sin coincidencia suficiente",
        invoice_unavailable=False,
    )

    for breakdown in (none_breakdown, insufficient_breakdown):
        assert breakdown["chips"] == [
            {"key": "insufficient_match", "label": "Sin coincidencia", "tone": "warning"}
        ]
        assert breakdown["summary"] == "No hay evidencia suficiente para sugerir un CFDI."
        assert breakdown["confidence_hint"] == "evidence_weak"


def test_score_breakdown_handles_invoice_unavailable_case():
    breakdown = _score_breakdown_for_ui(
        match_reason="Factura relacionada eliminada",
        invoice_unavailable=True,
    )

    assert breakdown["chips"] == [
        {"key": "invoice_unavailable", "label": "CFDI no disponible", "tone": "warning"}
    ]
    assert breakdown["summary"] == "La factura sugerida ya no esta disponible para conciliacion."
    assert breakdown["confidence_hint"] == "evidence_weak"


def test_score_breakdown_limits_chip_count_to_backend_maximum():
    breakdown = _score_breakdown_for_ui(
        match_reason=(
            "UUID detectado en referencia o descripcion; "
            "Monto exacto; "
            "Fecha dentro de 2 dias; "
            "RFC detectado en descripcion; "
            "Proveedor detectado en descripcion; "
            "Moneda coincide; "
            "Coincidencia por proveedor/nombre"
        ),
        invoice_unavailable=False,
    )

    assert len(breakdown["chips"]) == MAX_BREAKDOWN_CHIPS
    assert all(set(chip.keys()) == {"key", "label", "tone"} for chip in breakdown["chips"])


def test_invoice_unavailable_for_ui_returns_false_when_cfdi_is_still_available():
    assert invoice_unavailable_for_ui(
        "UUID detectado en referencia o descripcion",
        matched_invoice_id=101,
        matched_invoice_uuid="AAAAAAAA-1111-4111-8111-AAAAAAAAAAAA",
    ) is False


def test_invoice_unavailable_for_ui_prefers_existing_uuid_over_unavailable_reason():
    assert invoice_unavailable_for_ui(
        "Factura relacionada eliminada",
        matched_invoice_id=102,
        matched_invoice_uuid="BBBBBBBB-2222-4222-8222-BBBBBBBBBBBB",
    ) is False


def test_invoice_unavailable_for_ui_returns_true_when_reason_marks_deleted_invoice():
    assert invoice_unavailable_for_ui(
        "Factura relacionada eliminada",
        matched_invoice_id=None,
        matched_invoice_uuid=None,
    ) is True


def test_invoice_unavailable_for_ui_returns_true_when_invoice_id_exists_but_uuid_is_missing():
    assert invoice_unavailable_for_ui(
        "UUID detectado en referencia o descripcion",
        matched_invoice_id=202,
        matched_invoice_uuid=None,
    ) is True


def test_invoice_unavailable_for_ui_returns_false_without_reason_or_invoice_link():
    assert invoice_unavailable_for_ui(
        None,
        matched_invoice_id=None,
        matched_invoice_uuid=None,
    ) is False


def test_invoice_unavailable_breakdown_preserves_ui_expected_fields_and_fallback_message():
    invoice_unavailable = invoice_unavailable_for_ui(
        "UUID detectado en referencia o descripcion",
        matched_invoice_id=303,
        matched_invoice_uuid=None,
    )
    breakdown = _score_breakdown_for_ui(
        match_reason="UUID detectado en referencia o descripcion",
        invoice_unavailable=invoice_unavailable,
    )

    assert invoice_unavailable is True
    assert set(breakdown.keys()) == {"chips", "summary", "confidence_hint"}
    assert breakdown["chips"] == [
        {"key": "invoice_unavailable", "label": "CFDI no disponible", "tone": "warning"}
    ]
    assert breakdown["summary"] == "La factura sugerida ya no esta disponible para conciliacion."
    assert breakdown["confidence_hint"] == "evidence_weak"
