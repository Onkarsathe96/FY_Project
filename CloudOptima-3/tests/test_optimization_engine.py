import math

import pandas as pd

from app.services.optimization_engine import OptimizationEngine


def test_calculate_savings_ratio_uses_loaded_data_distribution():
    engine = OptimizationEngine()
    service_df = pd.DataFrame(
        {
            "cost": [120.0, 240.0, 80.0, 60.0, 500.0],
            "usage_quantity": [10, 100, 1, 2, 400],
            "usage_type": ["Standard", "Archive", "Infrequent", "General", "Storage"],
        }
    )

    ratio = engine.calculate_savings_ratio("Amazon S3", service_df)
    total = float(service_df["cost"].sum())

    assert 0.05 < ratio < 0.60
    assert engine.calculate_potential_savings("Amazon S3", service_df) == round(total * ratio, 2)
    assert engine.calculate_potential_savings("Amazon S3", service_df) != round(total * 0.45, 2)


def test_generate_recommendations_uses_service_totals_from_loaded_csvs():
    engine = OptimizationEngine()
    engine.store.master_df = pd.DataFrame(
        [
            {"date": "2024-01-01", "service": "S3", "usage_type": "Storage", "usage_quantity": 10, "cost": 120.0, "source_file": "s3.csv"},
            {"date": "2024-01-02", "service": "S3", "usage_type": "Storage", "usage_quantity": 50, "cost": 220.0, "source_file": "s3.csv"},
            {"date": "2024-01-01", "service": "EC2", "usage_type": "Compute", "usage_quantity": 500, "cost": 150.0, "source_file": "ec2.csv"},
        ],
        columns=["date", "service", "usage_type", "usage_quantity", "cost", "source_file"],
    )

    recs = engine.generate_recommendations()
    s3_rec = next(r for r in recs if r["service"] == "S3")
    ec2_rec = next(r for r in recs if r["service"] == "EC2")

    assert s3_rec["potential_savings_monthly"] > 0
    assert ec2_rec["potential_savings_monthly"] > 0
    assert math.isclose(
        sum(r["potential_savings_monthly"] for r in recs),
        round(sum(r["potential_savings_monthly"] for r in recs), 2),
        rel_tol=0.0,
        abs_tol=1e-9,
    )
