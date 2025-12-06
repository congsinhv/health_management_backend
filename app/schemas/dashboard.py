
from pydantic import BaseModel, field_validator
from typing import Optional, List
from datetime import date
from typing import Optional
from decimal import Decimal
from typing import Dict, Any, List, Optional  
from app.schemas.base import BaseSchema, TimestampMixin, IDMixin


# Schema cho response
class KeyMetric(BaseModel):
    value: float
    category: Optional[str] = None
    status: str
    message: str

class ActivitySummary(BaseModel):
    daily: Dict[str, Any]
    weekly: Dict[str, Any]
    monthly: Dict[str, Any]

class HealthOverviewResponse(BaseModel):
    user_info: Dict[str, Any]
    health_score: Dict[str, Any]
    key_metrics: Dict[str, Dict[str, Any]]
    activity_summary: ActivitySummary
    ai_summary: str
    quick_tips: list[str]