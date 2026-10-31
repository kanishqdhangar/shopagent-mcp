
import time
from audit import write_audit_log

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, Field

from config import settings
from state import AgentState, DecisionLogEntry


class UpsellResult(BaseModel):
    should_upsell: bool = Field(
        description="Whether a higher-priced product should be offered."
    )

    product_id: str | None = Field(
        default=None,
        description="ID of the upsell product, if one exists."
    )

    reason: str = Field(
        description="Why the upsell should or should not be offered."
    )


llm = ChatGoogleGenerativeAI(
    model="gemini-3.5-flash-lite",
    google_api_key=settings.gemini_api_key,
)

structured_llm = llm.with_structured_output(
    UpsellResult,
    include_raw=True,
)


async def check_upsell(state: AgentState) -> dict:
    started_at = time.perf_counter()

    chosen_product = state.get("chosen_product")
    candidates = state.get("candidates", [])
    budget = state.get("budget_ceiling")

    if not chosen_product:
        return {
            "upsell_offer": None,
        }

    chosen_price = float(chosen_product.get("price", 0))

    # Without an explicit budget, skip upselling.
    if budget is None:
        log_entry = DecisionLogEntry(
            step="check_upsell",
            decision="Upsell skipped",
            reason=(
                "No explicit budget was provided. "
                "Skipping upsell to avoid recommending "
                "a more expensive product without a spending limit."
            ),
            tokens_used=0,
            latency_ms=int(
                (time.perf_counter() - started_at) * 1000
            ),
        )

        return {
            "upsell_offer": None,
            "decision_log": [
                *state.get("decision_log", []),
                log_entry,
            ],
        }

    budget = float(budget)

    # Only consider products more expensive than the chosen product
    # and within the user's explicit budget.
    upsell_candidates = [
        product
        for product in candidates
        if (
            str(product.get("id")) != str(chosen_product.get("id"))
            and float(product.get("price", 0)) > chosen_price
            and float(product.get("price", 0)) <= budget
            and int(product.get("stock_qty", 0)) > 0
        )
    ]

    if not upsell_candidates:
        log_entry = DecisionLogEntry(
            step="check_upsell",
            decision="No upsell available",
            reason=(
                "No higher-priced in-stock candidate was available "
                "within the user's budget."
            ),
            tokens_used=0,
            latency_ms=int(
                (time.perf_counter() - started_at) * 1000
            ),
        )

        return {
            "upsell_offer": None,
            "decision_log": [
                *state.get("decision_log", []),
                log_entry,
            ],
        }

    system_prompt = """
You are ShopAgent's upsell decision agent.

Determine whether the user should be offered a higher-priced
alternative.

Rules:

1. The upsell must be more expensive than the selected product.
2. The upsell must not exceed the user's budget ceiling.
3. The upsell must be in stock.
4. The upsell should provide meaningful additional value,
   such as better cushioning, materials, specifications,
   or features.
5. Do not invent products or product IDs.
6. If no candidate provides meaningful additional value,
   do not recommend an upsell.
"""

    prompt = (
        f"Selected product:\n{chosen_product}\n\n"
        f"User budget ceiling:\n₹{budget}\n\n"
        f"Possible upsell products:\n{upsell_candidates}"
    )

    response = await structured_llm.ainvoke(
        [
            SystemMessage(content=system_prompt),
            HumanMessage(content=prompt),
        ]
    )

    parsed: UpsellResult = response["parsed"]
    raw = response["raw"]

    usage = getattr(raw, "usage_metadata", None) or {}

    tokens_used = int(
        usage.get("total_tokens", 0)
    )

    latency_ms = int(
        (time.perf_counter() - started_at) * 1000
    )

    upsell_offer = None

    if parsed.should_upsell and parsed.product_id:
        for product in upsell_candidates:
            if str(product.get("id")) == str(parsed.product_id):
                upsell_offer = product
                break

    if upsell_offer:
        decision = (
            f"Upsell available: {upsell_offer.get('name')}"
        )
    else:
        decision = "No upsell offered"

    log_entry = DecisionLogEntry(
        step="check_upsell",
        decision=decision,
        reason=parsed.reason,
        tokens_used=tokens_used,
        latency_ms=latency_ms,
    )

    # Persist LLM decision in PostgreSQL
    await write_audit_log(
        run_id=state["run_id"],
        node_name="check_upsell",
        decision=decision,
        reasoning=parsed.reason,
        tokens_used=tokens_used,
        latency_ms=latency_ms,
    )

    return {
        "upsell_offer": upsell_offer,
        "decision_log": [
            *state.get("decision_log", []),
            log_entry,
        ],
    }
