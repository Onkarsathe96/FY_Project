from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from math import sqrt
from statistics import mean, pstdev
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models import CloudAccount, CostAnomaly, CostForecast, CostRecord
from app.models.enums import CloudProvider

MONEY_PLACES = Decimal("0.0001")
MIN_HISTORY_DAYS = 3


@dataclass(frozen=True)
class DailyCost:
    usage_date: date
    amount: Decimal


@dataclass(frozen=True)
class CostSeries:
    account_id: UUID
    service_name: str
    region: str | None
    currency: str
    observations: list[DailyCost]


@dataclass
class AnalysisSummary:
    providers: list[CloudProvider]
    series_analysed: int = 0
    series_skipped: int = 0
    forecasts_created: int = 0
    anomalies_detected: int = 0
    model_names: list[str] | None = None


def run_cost_analysis(
    db: Session,
    providers: list[CloudProvider],
    forecast_days: int = 7,
    prefer_prophet: bool = True,
    include_sample_data: bool = False,
) -> AnalysisSummary:
    account_query = select(CloudAccount).where(CloudAccount.provider.in_(providers))
    if not include_sample_data:
        account_query = account_query.where(~CloudAccount.external_account_id.endswith("-sample"))
    accounts = list(db.scalars(account_query).all())
    account_ids = [account.id for account in accounts]
    summary = AnalysisSummary(providers=providers, model_names=[])
    if not account_ids:
        return summary

    records = list(
        db.scalars(
            select(CostRecord)
            .where(CostRecord.account_id.in_(account_ids))
            .order_by(CostRecord.account_id, CostRecord.service_name, CostRecord.usage_date)
        ).all()
    )
    db.execute(delete(CostForecast).where(CostForecast.account_id.in_(account_ids)))
    db.execute(delete(CostAnomaly).where(CostAnomaly.account_id.in_(account_ids)))

    for series in build_cost_series(records):
        if len(series.observations) < MIN_HISTORY_DAYS:
            summary.series_skipped += 1
            continue
        forecasts, model_name = forecast_series(series, forecast_days, prefer_prophet, date.today())
        for forecast in forecasts:
            db.add(
                CostForecast(
                    account_id=series.account_id,
                    service_name=series.service_name,
                    region=series.region,
                    forecast_date=forecast.usage_date,
                    currency=series.currency,
                    predicted_amount=forecast.amount,
                    lower_bound=forecast.lower_bound,
                    upper_bound=forecast.upper_bound,
                    model_name=model_name,
                )
            )
        anomalies = detect_anomalies(series)
        for anomaly in anomalies:
            db.add(
                CostAnomaly(
                    account_id=series.account_id,
                    service_name=series.service_name,
                    region=series.region,
                    usage_date=anomaly.usage_date,
                    currency=series.currency,
                    actual_amount=anomaly.actual_amount,
                    expected_amount=anomaly.expected_amount,
                    upper_bound=anomaly.upper_bound,
                    severity=anomaly.severity,
                    explanation=(
                        f"Observed cost {anomaly.actual_amount} exceeded the upper threshold "
                        f"{anomaly.upper_bound} based on prior daily costs."
                    ),
                    metadata_json={"method": "rolling_upper_bound", "history_days": anomaly.history_days},
                )
            )
        summary.series_analysed += 1
        summary.forecasts_created += len(forecasts)
        summary.anomalies_detected += len(anomalies)
        if model_name not in summary.model_names:
            summary.model_names.append(model_name)

    db.commit()
    return summary


def build_cost_series(records: list[CostRecord]) -> list[CostSeries]:
    grouped: dict[tuple[UUID, str, str | None, str], dict[date, Decimal]] = defaultdict(lambda: defaultdict(Decimal))
    for record in records:
        key = (record.account_id, record.service_name, record.region, record.currency)
        grouped[key][record.usage_date] += Decimal(record.amount)

    result: list[CostSeries] = []
    for (account_id, service_name, region, currency), costs_by_date in grouped.items():
        start_date, end_date = min(costs_by_date), max(costs_by_date)
        observations = []
        current_date = start_date
        while current_date <= end_date:
            observations.append(DailyCost(current_date, quantize_money(costs_by_date.get(current_date, Decimal("0")))))
            current_date += timedelta(days=1)
        result.append(CostSeries(account_id, service_name, region, currency, observations))
    return result


@dataclass(frozen=True)
class ForecastPoint:
    usage_date: date
    amount: Decimal
    lower_bound: Decimal
    upper_bound: Decimal


@dataclass(frozen=True)
class DetectedAnomaly:
    usage_date: date
    actual_amount: Decimal
    expected_amount: Decimal
    upper_bound: Decimal
    severity: str
    history_days: int


def forecast_series(
    series: CostSeries,
    forecast_days: int,
    prefer_prophet: bool,
    forecast_start_date: date | None = None,
) -> tuple[list[ForecastPoint], str]:
    if prefer_prophet:
        prophet_forecast = _try_prophet_forecast(series, forecast_days, forecast_start_date)
        if prophet_forecast is not None:
            return prophet_forecast, "prophet"
    return _linear_trend_forecast(series, forecast_days, forecast_start_date), "linear_trend_fallback"


def _linear_trend_forecast(series: CostSeries, forecast_days: int, forecast_start_date: date | None = None) -> list[ForecastPoint]:
    values = [float(item.amount) for item in series.observations]
    slope, intercept = _linear_fit(values)
    residuals = [value - (intercept + slope * index) for index, value in enumerate(values)]
    interval = max(pstdev(residuals) * 1.96, max(mean(values) * 0.05, 0.01))
    last_date = forecast_start_date or series.observations[-1].usage_date
    skipped_days = max(0, (last_date - series.observations[-1].usage_date).days)
    forecasts = []
    for offset in range(1, forecast_days + 1):
        predicted = max(0.0, intercept + slope * (len(values) - 1 + skipped_days + offset))
        forecasts.append(
            ForecastPoint(
                usage_date=last_date + timedelta(days=offset),
                amount=quantize_money(Decimal(str(predicted))),
                lower_bound=quantize_money(Decimal(str(max(0.0, predicted - interval)))),
                upper_bound=quantize_money(Decimal(str(predicted + interval))),
            )
        )
    return forecasts


def _try_prophet_forecast(series: CostSeries, forecast_days: int, forecast_start_date: date | None = None) -> list[ForecastPoint] | None:
    if len(series.observations) < 7:
        return None
    try:
        import pandas as pd
        from prophet import Prophet

        frame = pd.DataFrame({"ds": [point.usage_date for point in series.observations], "y": [float(point.amount) for point in series.observations]})
        model = Prophet(daily_seasonality=False, weekly_seasonality=True, yearly_seasonality=False)
        model.fit(frame)
        last_observed = series.observations[-1].usage_date
        target_start = forecast_start_date or last_observed
        skipped_days = max(0, (target_start - last_observed).days)
        predicted = model.predict(model.make_future_dataframe(periods=skipped_days + forecast_days, freq="D")).tail(forecast_days)
        return [
            ForecastPoint(
                usage_date=row.ds.date(),
                amount=quantize_money(Decimal(str(max(0.0, row.yhat)))),
                lower_bound=quantize_money(Decimal(str(max(0.0, row.yhat_lower)))),
                upper_bound=quantize_money(Decimal(str(max(0.0, row.yhat_upper)))),
            )
            for row in predicted.itertuples()
        ]
    except (ImportError, ValueError, RuntimeError):
        return None


def detect_anomalies(series: CostSeries) -> list[DetectedAnomaly]:
    values = [point.amount for point in series.observations]
    anomalies: list[DetectedAnomaly] = []
    for index in range(MIN_HISTORY_DAYS, len(values)):
        history = [float(value) for value in values[:index]]
        expected = mean(history)
        deviation = pstdev(history)
        upper_bound = max(expected + 1.96 * deviation, expected * 1.25, 0.01)
        actual = float(values[index])
        if actual > upper_bound:
            ratio = actual / upper_bound if upper_bound else 0
            severity = "critical" if ratio >= 2 else "high" if ratio >= 1.5 else "medium"
            anomalies.append(
                DetectedAnomaly(
                    usage_date=series.observations[index].usage_date,
                    actual_amount=values[index],
                    expected_amount=quantize_money(Decimal(str(expected))),
                    upper_bound=quantize_money(Decimal(str(upper_bound))),
                    severity=severity,
                    history_days=index,
                )
            )
    return anomalies


def _linear_fit(values: list[float]) -> tuple[float, float]:
    count = len(values)
    x_mean = (count - 1) / 2
    y_mean = mean(values)
    denominator = sum((index - x_mean) ** 2 for index in range(count))
    slope = sum((index - x_mean) * (value - y_mean) for index, value in enumerate(values)) / denominator
    return slope, y_mean - slope * x_mean


def quantize_money(value: Decimal) -> Decimal:
    return value.quantize(MONEY_PLACES, rounding=ROUND_HALF_UP)