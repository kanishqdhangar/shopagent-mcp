from langgraph.checkpoint.redis import AsyncRedisSaver
from langgraph.graph import END, START, StateGraph

from state import AgentState, DecisionLogEntry
from nodes.parse_intent import parse_intent
from nodes.rag_search import rag_search
from nodes.compare_options import compare_options
from nodes.check_upsell import check_upsell
from nodes.budget_guardrail import budget_guardrail
from nodes.checkout import checkout
from nodes.confirm import confirm
from nodes.confirm_alternative import confirm_alternative
from nodes.checkout_alternative import checkout_alternative
from nodes.await_payment import await_payment, handle_payment_failure
from nodes.negotiate import negotiate, validate_negotiation

MAX_CONFIDENCE_RETRIES = 2
CONFIDENCE_THRESHOLD = 0.5


def route_on_confidence(state: AgentState):
    confidence = state.get("confidence", 0.0)
    retry_count = state.get("retry_count", 0)

    if confidence < CONFIDENCE_THRESHOLD:
        if retry_count <= MAX_CONFIDENCE_RETRIES:
            return "retry"

        return "failed"

    parsed_filters = state.get("parsed_filters") or {}
    intent_type = parsed_filters.get("intent_type", "search")

    if state.get("negotiation_requested"):
        return "negotiate"

    # Only explicit purchase and restock requests can reach checkout.
    if intent_type in ("purchase", "restock"):
        return "purchase"

    # Search, comparison, and unknown intents never reach checkout.
    return "display"


def route_initial_request(state: AgentState):
    kind = state.get("request_kind")
    if kind == "negotiate":
        return "negotiate"
    if kind == "checkout_accepted":
        return "validate_negotiation"
    return "parse_intent"

def route_on_failure(state: AgentState):
    failure_reason = state.get("failure_reason")

    if failure_reason:
        return "failed"

    return "proceed"

def route_after_checkout(state: AgentState):
    if state.get("failure_reason"):
        return "failed"

    if state.get("order_status") == "awaiting_confirmation":
        return "needs_confirmation"

    if state.get("order_status") == "created":
        return "await_payment"

    return "proceed"


def route_after_alternative_confirmation(state: AgentState):
    if (
        state.get("alternative_approved") is True
        and state.get("confirmation_status") == "approved"
    ):
        return "approved"

    return "rejected"


def route_after_alternative_checkout(state: AgentState):
    if state.get("failure_reason"):
        return "failed"

    if state.get("order_status") == "created":
        return "await_payment"

    return "proceed"


async def handle_low_confidence(state: AgentState):
    from state import DecisionLogEntry

    log_entry = DecisionLogEntry(
        step="confidence_guardrail",
        decision="Confidence retry limit reached",
        reason=(
            f"Confidence remained below {CONFIDENCE_THRESHOLD} "
            f"after {MAX_CONFIDENCE_RETRIES} retries."
        ),
        tokens_used=0,
        latency_ms=0,
    )

    return {
        "failure_reason": "low_confidence",
        "decision_log": [
            *state["decision_log"],
            log_entry,
        ],
    }

async def build_buyer_graph():
    checkpointer = AsyncRedisSaver(
        redis_url="redis://redis:6379"
    )

    await checkpointer.asetup()

    builder = StateGraph(AgentState)

    builder.add_node(
        "parse_intent",
        parse_intent,
    )

    builder.add_node(
        "rag_search",
        rag_search,
    )

    builder.add_node(
        "compare_options",
        compare_options,
    )

    builder.add_node(
        "check_upsell",
        check_upsell,
    )

    builder.add_node(
        "budget_guardrail",
        budget_guardrail,
    )

    builder.add_node(
        "checkout",
        checkout,
    )

    builder.add_node(
        "handle_low_confidence",
        handle_low_confidence,
    )

    builder.add_node("confirm", confirm)
    builder.add_node("await_payment", await_payment)
    builder.add_node("handle_payment_failure", handle_payment_failure)
    builder.add_node(
        "confirm_alternative",
        confirm_alternative,
    )

    builder.add_node(
        "checkout_alternative",
        checkout_alternative,
    )
    builder.add_node("negotiate", negotiate)
    builder.add_node("validate_negotiation", validate_negotiation)

    builder.add_conditional_edges(START, route_initial_request, {
        "parse_intent": "parse_intent",
        "negotiate": "negotiate",
        "validate_negotiation": "validate_negotiation",
    })
    builder.add_edge("negotiate", END)
    builder.add_conditional_edges("validate_negotiation", route_on_failure, {
        "failed": END,
        "proceed": "budget_guardrail",
    })

    builder.add_edge(
        "parse_intent",
        "rag_search",
    )

    builder.add_edge(
        "rag_search",
        "compare_options",
    )

    builder.add_conditional_edges(
        "compare_options",
        route_on_confidence,
        {
            "retry": "parse_intent",
            "negotiate": "negotiate",
            "purchase": "check_upsell",
            "display": END,
            "failed": "handle_low_confidence",
        },
    )

    builder.add_edge("handle_low_confidence", END)

    builder.add_edge(
        "check_upsell",
        "budget_guardrail",
    )

    builder.add_conditional_edges(
        "budget_guardrail",
        route_on_failure,
        {
            "failed": END,
            "proceed": "checkout",
        },
    )
    builder.add_conditional_edges(
        "checkout",
        route_after_checkout,
        {
            "failed": END,
            "needs_confirmation": "confirm_alternative",
            "await_payment": "await_payment",
            "proceed": "confirm",
        },
    )

    builder.add_conditional_edges(
        "confirm_alternative",
        route_after_alternative_confirmation,
        {
            "approved": "checkout_alternative",
            "rejected": END,
        },
    )
    builder.add_conditional_edges(
    "checkout_alternative",
    route_after_alternative_checkout,
        {
            "failed": END,
            "await_payment": "await_payment",
            "proceed": "confirm",
        },
    )
    
    builder.add_edge("confirm", END)
    builder.add_conditional_edges(
        "await_payment",
        lambda state: "confirmed" if state.get("payment_status") == "paid" else "failed",
        {"confirmed": "confirm", "failed": "handle_payment_failure"},
    )
    builder.add_edge("handle_payment_failure", END)

    return builder.compile(
        checkpointer=checkpointer,
    )
