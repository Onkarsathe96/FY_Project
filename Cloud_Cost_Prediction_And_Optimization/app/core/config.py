from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings loaded from environment variables or a local .env file."""

    app_name: str = "Cloud_Cost_Prediction_And_Optimization"
    app_env: str = "development"
    api_v1_prefix: str = "/api/v1"
    database_url: str = "postgresql+psycopg://cloud_cost_prediction_and_optimization:cloud_cost_prediction_and_optimization@localhost:5432/cloud_cost_prediction_and_optimization"
    log_level: str = "INFO"
    aws_profile: str | None = None
    aws_region: str = "us-east-1"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
