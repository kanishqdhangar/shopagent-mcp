from typing import Optional, TypedDict

from pydantic import BaseModel, Field


class DecisionLogEntry(BaseModel):
    step: str
    decision: str
    reason: str
    tokens_used: int
    latency_ms: int


class ParsedFilters(BaseModel):
    category: Optional[str] = None
    subtype: Optional[str] = None
    budget: Optional[float] = None

    # Used by restock_or_compare later
    product_names: list[str] = Field(default_factory=list)
    intent_type: str = "search"


class AgentState(TypedDict):
    goal: str
    scenario: str

    parsed_filters: Optional[dict]

    candidates: list[dict]
    chosen_product: Optional[dict]
    upsell_offer: Optional[dict]

    budget_ceiling: float

    order_status: str
    order_id: Optional[str]

    decision_log: list[DecisionLogEntry]
    failure_reason: Optional[str]