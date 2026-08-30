import time

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, Field

from config import settings
from state import AgentState, DecisionLogEntry


class ComparisonResult(BaseModel):
    chosen_product_id: str | None = Field(
        default=None,
        description="ID of the best candidate product."
    )

    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Confidence in the selection from 0 to 1."
    )

    decision: str = Field(
        description="Short explanation of the selection."
    )

    reason: str = Field(
        description="Why this product provides the best value for the user's goal."
    )


llm = ChatGoogleGenerativeAI(
    model="gemini-3.5-flash-lite",
    google_api_key=settings.gemini_api_key,
)

structured_llm = llm.with_structured_output(
    ComparisonResult,
    include_raw=True,
)


async def compare_options(state: AgentState) -> dict:
    started_at = time.perf_counter()

    candidates = state.get("candidates", [])

    if not candidates:
        log_entry = DecisionLogEntry(
            step="compare_options",
            decision="No product selected",
            reason="No candidates were returned by catalog search.",
            tokens_used=0,
            latency_ms=0,
        )

        return {
            "chosen_product": None,
            "decision_log": [
                *state["decision_log"],
                log_entry,
            ],
            "failure_reason": "no_candidates",
        }

    goal = state["goal"]

    system_prompt = """
You are ShopAgent's product comparison and selection agent.

Choose the single best product from the provided candidates.

Rules:

1. Only choose a product from the candidates.
2. Never invent a product or product ID.
3. Respect the user's stated requirements.
4. Prefer the product that best satisfies the user's overall goal.
5. Consider price, product description, specifications and stock.
6. Do not exceed the user's budget.
7. confidence must be between 0 and 1.
8. If the candidates are clearly suitable, confidence should be high.
9. If the candidates do not clearly satisfy the request, use a confidence
   below 0.5.
10. Do not perform checkout or payment here.
"""

    prompt = (
        f"User goal:\n{goal}\n\n"
        f"Candidates:\n{candidates}"
    )

    response = await structured_llm.ainvoke(
        [
            SystemMessage(content=system_prompt),
            HumanMessage(content=prompt),
        ]
    )

    parsed: ComparisonResult = response["parsed"]
    raw = response["raw"]

    latency_ms = int(
        (time.perf_counter() - started_at) * 1000
    )

    usage = getattr(raw, "usage_metadata", None) or {}

    tokens_used = int(
        usage.get("total_tokens", 0)
    )

    chosen_product = None

    for product in candidates:
        if str(product.get("id")) == str(
            parsed.chosen_product_id
        ):
            chosen_product = product
            break

    if chosen_product is None:
        confidence = 0.0
        decision = "No valid product selected"
        reason = (
            "The LLM returned a product ID that was not present "
            "in the candidate list."
        )
    else:
        confidence = parsed.confidence
        decision = (
            f"Selected {chosen_product.get('name')}"
        )
        reason = parsed.reason

    log_entry = DecisionLogEntry(
        step="compare_options",
        decision=decision,
        reason=reason,
        tokens_used=tokens_used,
        latency_ms=latency_ms,
    )

    return {
        "chosen_product": chosen_product,
        "decision_log": [
            *state["decision_log"],
            log_entry,
        ],
    }