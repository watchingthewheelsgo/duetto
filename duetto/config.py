"""Configuration settings for Duetto."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings."""

    # Server
    host: str = "0.0.0.0"
    port: int = 8000

    # SEC EDGAR settings
    sec_user_agent: str = "Duetto/1.0 (your-email@example.com)"
    sec_poll_interval: int = 30  # seconds
    sec_rate_limit: float = 0.1  # 10 requests per second max

    # FDA settings
    fda_poll_interval: int = 300  # 5 minutes

    # Filter settings
    min_market_cap: float = 0  # No minimum by default
    max_market_cap: float = 1_000_000_000  # $1B default for small caps

    # Alert types to monitor
    monitor_8k: bool = True
    monitor_s3: bool = True
    monitor_form4: bool = True
    monitor_fda: bool = True

    class Config:
        env_prefix = "DUETTO_"
        env_file = ".env"


settings = Settings()
