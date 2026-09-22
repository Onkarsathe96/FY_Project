from fastapi import APIRouter
from app.services.cost_analytics import CostAnalytics
from app.services.predictor import CostPredictor
from app.services.optimization_engine import OptimizationEngine

router = APIRouter(prefix="/api/analytics", tags=["Analytics"])

analytics = CostAnalytics()
predictor = CostPredictor()
optimizer = OptimizationEngine()

@router.get("/max-to-min-cost")
def get_cost_distribution():
    return analytics.get_max_to_min_cost()

@router.get("/most-to-least-used")
def get_usage_distribution():
    return analytics.get_most_to_least_used()

@router.get("/predictions")
def get_predictions(days: int = 30):
    return predictor.predict_future_bills(days)

@router.get("/recommendations")
def get_recommendations():
    return optimizer.generate_recommendations()