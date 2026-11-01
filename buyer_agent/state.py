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
    run_id: str
    thread_id: str
    goal: str
    scenario: str

    parsed_filters: Optional[dict]

    candidates: list[dict]
    chosen_product: Optional[dict]
    upsell_offer: Optional[dict]
    confidence: float

    retry_count: int
    budget_ceiling: Optional[float]

    order_status: str
    order_id: Optional[str]
    payment_details: Optional[dict]
    payment_status: str

    # Human confirmation for alternative products
    pending_alternative: Optional[dict]
    alternative_approved: bool
    confirmation_status: str

    decision_log: list[DecisionLogEntry]
    failure_reason: Optional[str]

    # Seller-validated, product-scoped bargaining context.
    negotiation_status: str
    negotiation_product_id: Optional[str]
    original_price: Optional[float]
    requested_discount_percent: Optional[float]
    offered_discount_percent: Optional[float]
    negotiated_price: Optional[float]
    negotiation_attempts: int
    pending_negotiation: Optional[dict]
    negotiation_history: list[dict]
    negotiation_action: Optional[dict]
    negotiation_requested: bool
    purchase_authorized: bool
    request_kind: str

    
