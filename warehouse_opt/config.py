from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application and optimization settings loaded from environment."""

    app_name: str = "Warehouse Optimization API"
    app_version: str = "1.0.0"

    postgres_dsn: str = "postgresql+psycopg://warehouse:warehouse@localhost:5432/warehouse"

    default_batch_size_orders: int = 16
    default_walk_speed_mps: float = 1.3
    default_pick_time_sec: float = 5.2

    # Runtime protection for very large problem instances
    max_skus_for_exact_mip: int = 3500
    max_solver_seconds: int = 120
    candidate_pool_per_sku: int = 20

    model_config = SettingsConfigDict(env_prefix="WAREHOUSE_", extra="ignore")


settings = Settings()
