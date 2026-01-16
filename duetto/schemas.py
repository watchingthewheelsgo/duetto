"""Core data models."""

from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field

class AlertType(str, Enum):
    """Type of market alert."""
    SEC_8K = "sec_8k"
    SEC_S3 = "sec_s3"
    SEC_FORM4 = "sec_form4"
    SEC_6K = "sec_6k"
    FDA_APPROVAL = "fda_approval"
    FDA_PDUFA = "fda_pdufa"
    FDA_TRIAL = "fda_trial"
    PR_NEWS = "pr_news"
    STOCK_MOV = "stock_movement"

class AlertPriority(str, Enum):
    """Priority level of alert."""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

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
    
    # Enrichment
    enrichment_data: Optional[Dict[str, Any]] = Field(None, description="Enriched data (AI summary, stats)")
    raw_data: Optional[Dict[str, Any]] = Field(None, description="Raw source data")
    
    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}

class NotificationLevel(str, Enum):
    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"

class NotificationTemplate(BaseModel):
    """Standardized notification structure for all channels."""
    title: str
    body: str  # Markdown supported
    level: NotificationLevel = NotificationLevel.INFO
    link: Optional[str] = None
    link_text: Optional[str] = "View Details"
    
    # Key-Value pairs for structured display (e.g. Price: $100)
    fields: List[Dict[str, str]] = Field(default_factory=list)
    
    # Platform specific overrides (e.g. {"feishu": {"card": ...}})
    extras: Dict[str, Any] = Field(default_factory=dict)
