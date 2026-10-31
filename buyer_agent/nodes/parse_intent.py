import time
import re
from audit import write_audit_log

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, Field

from config import settings
from state import AgentState, DecisionLogEntry


class IntentResult(BaseModel):
    intent_type: str = Field(
        description=(
            "One of: search, compare, purchase, restock"
        )
    )

    category: str | None = Field(
        default=None,
        description="High-level catalog category."
    )

    subtype: str | None = Field(
        default=None,
        description="Specific product subtype."
    )

    budget: float | None = Field(
        default=None,
        description=(
            "Maximum user budget as a number, "
            "or null when no budget is stated."
        )
    )

    product_names: list[str] = Field(
        default_factory=list,
        description=(
            "Explicit product names mentioned by the user."
        )
    )

    search_query: str = Field(
        description=(
            "Concise semantic catalog query representing "
            "what the user wants."
        )
    )

    reason: str = Field(
        description=(
            "Brief explanation of how the intent "
            "and filters were interpreted."
        )
    )

    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Confidence in the extracted intent and filters."
    )


llm = ChatGoogleGenerativeAI(
    model="gemini-3.5-flash-lite",
    google_api_key=settings.gemini_api_key,
)

structured_llm = llm.with_structured_output(
    IntentResult,
    include_raw=True,
)

def detect_explicit_purchase_intent(goal: str) -> bool:
    normalized = goal.strip().lower()

    purchase_patterns = [
        r"^buy\b",
        r"^purchase\b",
        r"^order\b",
        r"^i want to buy\b",
        r"^i want to purchase\b",
        r"^i would like to buy\b",
        r"^i would like to purchase\b",
        r"^please buy\b",
        r"^please purchase\b",
        r"^go ahead and buy\b",
        r"^go ahead and purchase\b",
    ]

    # Questions asking whether to buy are not purchase authorization.
    if normalized.endswith("?"):
        return False

    return any(
        re.search(pattern, normalized)
        for pattern in purchase_patterns
    )

async def parse_intent(state: AgentState) -> dict:
    started_at = time.perf_counter()

    goal = state["goal"]
    scenario = state["scenario"]
    retry_count = state.get("retry_count", 0) + 1
    system_prompt = """
You are the intent parser for ShopAgent.

Convert the user's shopping goal into structured shopping filters.

Rules:

1. Extract an explicit budget when present.
2. Do not invent a budget.
3. Separate category from subtype where possible.

Examples:
"running shoes"
category = "running"
subtype = "shoes"

"running socks"
category = "running"
subtype = "socks"

4. intent_type must be exactly one of:
   - search: The user wants to discover, find, browse, or get recommendations.
   - compare: The user wants to compare products or evaluate alternatives.
   - purchase: The user explicitly wants to buy, order, or purchase a product.
   - restock: The user explicitly wants to reorder or restock a product.

5. A search or comparison request must NEVER be classified as purchase.
6. Mentioning a product, budget, or preferred product does not imply
   permission to purchase.
7. For comparison requests, preserve explicitly mentioned product names.
8. For restock/reorder requests, use intent_type="restock".
9. search_query should contain the semantic requirements useful for
   catalog retrieval.
10. Do not make a purchase decision here.
11. When intent is ambiguous, classify it as search, not purchase.
"""

    response = await structured_llm.ainvoke(
        [
            SystemMessage(content=system_prompt),
            HumanMessage(
                content=(
                    f"Scenario: {scenario}\n"
                    f"Shopping goal: {goal}"
                )
            ),
        ]
    )

    parsed: IntentResult = response["parsed"]
    raw = response["raw"]

    intent_type = parsed.intent_type

    if detect_explicit_purchase_intent(goal):
        intent_type = "purchase"
    latency_ms = int(
        (time.perf_counter() - started_at) * 1000
    )

    usage = getattr(raw, "usage_metadata", None) or {}
    tokens_used = int(
        usage.get("total_tokens", 0)
    )

    parsed_filters = {
        "intent_type": intent_type,
        "category": parsed.category,
        "subtype": parsed.subtype,
        "budget": parsed.budget,
        "product_names": parsed.product_names,
        "search_query": parsed.search_query,
    }

    log_entry = DecisionLogEntry(
        step="parse_intent",
        decision=(
            f"Parsed shopping intent as "
            f"{intent_type}"
        ),
        reason=parsed.reason,
        tokens_used=tokens_used,
        latency_ms=latency_ms,
    )

    await write_audit_log(
        run_id=state["run_id"],
        node_name="parse_intent",
        decision=log_entry.decision,
        reasoning=log_entry.reason,
        tokens_used=tokens_used,
        latency_ms=latency_ms,
    )

    return {
        "parsed_filters": parsed_filters,
        "budget_ceiling": parsed.budget,
        "confidence": parsed.confidence,
        "retry_count": retry_count,
        "decision_log": [
            *state["decision_log"],
            log_entry,
        ],
    }