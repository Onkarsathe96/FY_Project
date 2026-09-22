from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

from app.services.analytics import build_cost_series, detect_anomalies, forecast_series


def _record(day: int, amount: str):
    return SimpleNamespace(
        account_id=uuid4(),
        service_name="Compute",
        region="us-east-1",
        currency="USD",
        usage_date=date(2026, 9, day),
        amount=Decimal(amount),
    )


def test_cost_preprocessing_aggregates_same_day_and_fills_gaps():
    account_id = uuid4()
    records = [
        SimpleNamespace(account_id=account_id, service_name="Compute", region=None, currency="USD", usage_date=date(2026, 9, 1), amount=Decimal("5")),
        SimpleNamespace(account_id=account_id, service_name="Compute", region=None, currency="USD", usage_date=date(2026, 9, 1), amount=Decimal("2")),
        SimpleNamespace(account_id=account_id, service_name="Compute", region=None, currency="USD", usage_date=date(2026, 9, 3), amount=Decimal("4")),
    ]

    series = build_cost_series(records)[0]

    assert [point.amount for point in series.observations] == [Decimal("7.0000"), Decimal("0.0000"), Decimal("4.0000")]


def test_linear_forecast_produces_requested_future_points_without_prophet():
    account_id = uuid4()
    records = [
        SimpleNamespace(account_id=account_id, service_name="Compute", region=None, currency="USD", usage_date=date(2026, 9, day), amount=Decimal(str(day)))
        for day in range(1, 5)
    ]

    forecasts, model_name = forecast_series(build_cost_series(records)[0], forecast_days=3, prefer_prophet=False)

    assert model_name == "linear_trend_fallback"
    assert len(forecasts) == 3
    assert forecasts[0].usage_date == date(2026, 9, 5)
    assert forecasts[0].upper_bound >= forecasts[0].amount >= forecasts[0].lower_bound


def test_anomaly_detector_flags_cost_above_upper_bound():
    account_id = uuid4()
    records = [
        SimpleNamespace(account_id=account_id, service_name="Compute", region=None, currency="USD", usage_date=date(2026, 9, day), amount=Decimal(amount))
        for day, amount in enumerate(["10", "10", "10", "50"], start=1)
    ]

    anomalies = detect_anomalies(build_cost_series(records)[0])

    assert len(anomalies) == 1
    assert anomalies[0].usage_date == date(2026, 9, 4)
    assert anomalies[0].severity == "critical"


def test_forecast_can_start_after_stale_billing_data():
    account_id = uuid4()
    records = [
        SimpleNamespace(account_id=account_id, service_name="Compute", region=None, currency="USD", usage_date=date(2026, 9, day), amount=Decimal(str(day)))
        for day in range(1, 11)
    ]

    forecasts, _ = forecast_series(
        build_cost_series(records)[0],
        forecast_days=3,
        prefer_prophet=False,
        forecast_start_date=date(2026, 9, 22),
    )

    assert [point.usage_date for point in forecasts] == [date(2026, 9, 23), date(2026, 9, 24), date(2026, 9, 25)]