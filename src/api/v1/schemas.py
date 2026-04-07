from datetime import datetime, timezone
from typing import Generic, Optional, TypeVar

from pydantic import BaseModel, Field


T = TypeVar("T")


# ── Envelope ────────────────────────────────────────────────────────────────────

class APIResponse(BaseModel, Generic[T]):
    success: bool
    data: Optional[T] = None
    request_id: str
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


# ── Schemas ────────────────────────────────────────────────────────────────────

class ResearchRequest(BaseModel):
    eventTitle: str = Field(min_length=1, max_length=500)
    eventSource: str = Field(min_length=1, max_length=253)
    timestamp: int = Field(description="Unix milliseconds from the extension")


class ResearchSections(BaseModel):
    eventSummary: str
    keyVariables: str
    historicalContext: str
    currentDrivers: str
    riskFactors: str
    dataConfidence: str
    dataGaps: str


class ResearchResponse(BaseModel):
    cached: bool
    cachedAt: Optional[str]
    sections: ResearchSections
    dataRetrievalAvailable: bool
    generatedAt: str
