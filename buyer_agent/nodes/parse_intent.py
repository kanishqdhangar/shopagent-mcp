import time

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, Field

from config import settings
from state import AgentState, DecisionLogEntry


class IntentResult(BaseModel):
    intent_type: str = Field(
        description=(
            "One of: search, compare, restock"
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


llm = ChatGoogleGenerativeAI(
    model="gemini-3.5-flash-lite",
    google_api_key=settings.gemini_api_key,
)

structured_llm = llm.with_structured_output(
    IntentResult,
    include_raw=True,
)


async def parse_intent(state: AgentState) -> dict:
    started_at = time.perf_counter()

    goal = state["goal"]
    scenario = state["scenario"]

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

4. intent_type must be:
   - search
   - compare
   - restock

5. For comparison requests, preserve explicitly mentioned product names.
6. For restock/reorder requests, use intent_type="restock".
7. search_query should contain the semantic requirements useful for
   catalog retrieval.
8. Do not make a purchase decision here.
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

    latency_ms = int(
        (time.perf_counter() - started_at) * 1000
    )

    usage = getattr(raw, "usage_metadata", None) or {}
    tokens_used = int(
        usage.get("total_tokens", 0)
    )

    parsed_filters = {
        "intent_type": parsed.intent_type,
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
            f"{parsed.intent_type}"
        ),
        reason=parsed.reason,
        tokens_used=tokens_used,
        latency_ms=latency_ms,
    )

    return {
        "parsed_filters": parsed_filters,
        "decision_log": [
            *state["decision_log"],
            log_entry,
        ],
    }