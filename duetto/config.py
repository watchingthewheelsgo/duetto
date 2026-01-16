"""Configuration settings for Duetto."""

from typing import List, Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

class ServerSettings(BaseSettings):
    host: str = Field("0.0.0.0", validation_alias="DUETTO_HOST")
    port: int = Field(8091, validation_alias="DUETTO_PORT")

class SECSettings(BaseSettings):
    user_agent: str = Field(
        "Duetto/1.0 theheisensky@gmail.com", validation_alias="DUETTO_SEC_USER_AGENT"
    )
    poll_interval: int = Field(30, validation_alias="DUETTO_SEC_POLL_INTERVAL")
    rate_limit: float = Field(1, validation_alias="DUETTO_SEC_RATE_LIMIT")
    monitor_8k: bool = Field(True, validation_alias="DUETTO_MONITOR_8K")
    monitor_s3: bool = Field(True, validation_alias="DUETTO_MONITOR_S3")
    monitor_form4: bool = Field(True, validation_alias="DUETTO_MONITOR_FORM4")

class FDASettings(BaseSettings):
    poll_interval: int = Field(300, validation_alias="DUETTO_FDA_POLL_INTERVAL")
    monitor_fda: bool = Field(True, validation_alias="DUETTO_MONITOR_FDA")

class TradingViewSettings(BaseSettings):
    symbols: List[str] = Field(
        ["NASDAQ:AAPL", "NASDAQ:MSFT", "NASDAQ:GOOGL", "NASDAQ:NVDA", "NASDAQ:TSLA"],
        validation_alias="DUETTO_TRADINGVIEW_SYMBOLS"
    )
    threshold_pct: float = Field(10.0, validation_alias="DUETTO_TRADINGVIEW_THRESHOLD_PCT")

class FilterSettings(BaseSettings):
    min_market_cap: float = Field(0, validation_alias="DUETTO_MIN_MARKET_CAP")
    max_market_cap: float = Field(1_000_000_000, validation_alias="DUETTO_MAX_MARKET_CAP")

class FeishuSettings(BaseSettings):
    webhook_url: Optional[str] = Field(None, validation_alias="DUETTO_FEISHU_WEBHOOK_URL")

class TelegramSettings(BaseSettings):
    bot_token: str = Field("", validation_alias="DUETTO_TELEGRAM_BOT_TOKEN")
    chat_id: str = Field("", validation_alias="DUETTO_TELEGRAM_CHAT_ID")

class EmailSettings(BaseSettings):
    host: str = Field("", validation_alias="DUETTO_SMTP_HOST")
    port: int = Field(587, validation_alias="DUETTO_SMTP_PORT")
    username: str = Field("", validation_alias="DUETTO_SMTP_USERNAME")
    password: str = Field("", validation_alias="DUETTO_SMTP_PASSWORD")
    sender: str = Field("", validation_alias="DUETTO_EMAIL_FROM")
    recipients: str = Field("", validation_alias="DUETTO_EMAIL_TO")

class AISettings(BaseSettings):
    provider: str = Field("rule", validation_alias="DUETTO_AI_PROVIDER")
    openai_api_key: str = Field("", validation_alias="DUETTO_OPENAI_API_KEY")
    openai_base_url: str = Field("https://api.openai.com/v1", validation_alias="DUETTO_OPENAI_BASE_URL")
    openai_model: str = Field("gpt-4o-mini", validation_alias="DUETTO_OPENAI_MODEL")
    anthropic_api_key: str = Field("", validation_alias="DUETTO_ANTHROPIC_API_KEY")
    anthropic_model: str = Field("claude-3-5-haiku-20241022", validation_alias="DUETTO_ANTHROPIC_MODEL")
    enable_enrichment: bool = Field(False, validation_alias="DUETTO_ENABLE_AI_IN_NOTIFICATIONS")

class Settings(BaseSettings):
    """Global Application Settings."""
    server: ServerSettings = ServerSettings()
    sec: SECSettings = SECSettings()
    fda: FDASettings = FDASettings()
    tv: TradingViewSettings = TradingViewSettings()
    filters: FilterSettings = FilterSettings()
    
    # Notifiers
    feishu: FeishuSettings = FeishuSettings()
    telegram: TelegramSettings = TelegramSettings()
    email: EmailSettings = EmailSettings()
    
    # AI
    ai: AISettings = AISettings()
    
    # Global
    notify_min_priority: str = Field("medium", validation_alias="DUETTO_NOTIFY_MIN_PRIORITY")

    model_config = SettingsConfigDict(
        env_file=".env", 
        env_nested_delimiter="__", 
        extra="ignore"
    )

settings = Settings()
