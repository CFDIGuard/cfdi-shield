from app.services.risk_engine import calcular_riesgo, has_provider_high_cancellation_risk


def test_cancelado_es_riesgo_medio():
    assert calcular_riesgo("Cancelado", 100) == "MEDIO"


def test_sin_validacion_es_riesgo_bajo():
    assert calcular_riesgo("SIN_VALIDACION", 50001) == "BAJO"


def test_total_bajo_es_riesgo_bajo():
    assert calcular_riesgo("Vigente", 100) == "BAJO"


def test_cancelaciones_frecuentes_si_activan_riesgo_alto():
    assert has_provider_high_cancellation_risk(cancelled_count=3, invoice_count=9) is True


def test_cancelaciones_normales_no_activan_riesgo_alto():
    assert has_provider_high_cancellation_risk(cancelled_count=3, invoice_count=20) is False
