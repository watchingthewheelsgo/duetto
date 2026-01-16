"""Alert data model."""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class AlertType(str, Enum):
    """Type of market alert."""

    SEC_8K = "sec_8k"  # Current reports (M&A, material events)
    SEC_S3 = "sec_s3"  # Securities registration (offerings)
    SEC_FORM4 = "sec_form4"  # Insider trading
    SEC_6K = "sec_6k"  # Foreign private issuer reports
    FDA_APPROVAL = "fda_approval"
    FDA_PDUFA = "fda_pdufa"  # FDA action dates
    FDA_TRIAL = "fda_trial"  # Clinical trial results
    PR_NEWS = "pr_news"  # Press releases
    STOCK_MOVEMENT = "stock_movement"  # Significant price movement


class AlertPriority(str, Enum):
    """Priority level of alert."""

    HIGH = "high"  # M&A, FDA approval, major insider buying
    MEDIUM = "medium"  # Offerings, partnerships
    LOW = "low"  # Routine filings


class Alert(BaseModel):
    """Market alert model."""

    id: str = Field(..., description="Unique alert ID")
    type: AlertType = Field(..., description="Type of alert")
    priority: AlertPriority = Field(default=AlertPriority.MEDIUM)
    ticker: Optional[str] = Field(None, description="Stock ticker symbol")
    company: str = Field(..., description="Company name")
    title: str = Field(..., description="Alert headline")
    summary: str = Field(..., description="Brief summary")
    url: str = Field(..., description="Source URL")
    source: str = Field(..., description="Data source (SEC, FDA, etc)")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    raw_data: Optional[dict] = Field(None, description="Raw source data")

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}
