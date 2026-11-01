
import uuid
from contextlib import asynccontextmanager
from typing import Any, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from langgraph.types import Command
from graph import build_buyer_graph
from services.negotiation import parse_negotiation_message


buyer_graph = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global buyer_graph
    buyer_graph = await build_buyer_graph()
    yield


app = FastAPI(
    title="ShopAgent Buyer Agent",
    version="1.1.0",
    lifespan=lifespan,
)


# -------------------------
# Request / Response Models
# -------------------------

class ChatRequest(BaseModel):
    message: str
    session_id: str


class ConfirmationRequest(BaseModel):
    session_id: str
    approved: bool


class ChatResponse(BaseModel):
    response: str
    session_id: str
    intent_type: str = "search"
    products: list[dict[str, Any]] = []
    confirmation_required: bool = False
    pending_confirmation: Optional[dict[str, Any]] = None
    order_status: str = "not_started"
    order_id: Optional[str] = None
    failure_reason: Optional[str] = None
    payment_required: bool = False
    payment: Optional[dict[str, Any]] = None
    payment_status: Optional[str] = None
    negotiation: Optional[dict[str, Any]] = None


# -------------------------
# Helpers
# -------------------------

def get_interrupt_payload(result: dict) -> Optional[dict]:
    interrupts = result.get("__interrupt__", [])

    if not interrupts:
        return None

    interrupt = interrupts[0]

    # LangGraph Interrupt objects expose their payload through .value.
    if hasattr(interrupt, "value"):
        return interrupt.value

    if isinstance(interrupt, dict):
        return interrupt.get("value", interrupt)

    return None


def build_chat_response(result: dict, session_id: str) -> ChatResponse:
    interrupt_payload = get_interrupt_payload(result)

    parsed_filters = result.get("parsed_filters") or {}
    intent_type = parsed_filters.get("intent_type", "search")

    if interrupt_payload:
        if interrupt_payload.get("type") == "payment_required":
            return ChatResponse(
                response=interrupt_payload.get("message", "Complete payment to continue."),
                session_id=session_id,
                intent_type=intent_type,
                products=[result["chosen_product"]] if result.get("chosen_product") else [],
                order_status=result.get("order_status", "created"),
                order_id=result.get("order_id"),
                payment_required=True,
                payment=interrupt_payload.get("payment") or result.get("payment_details"),
                payment_status=result.get("payment_status", "pending"),
                negotiation=result.get("pending_negotiation"),
            )
        product = interrupt_payload.get("product", {})

        return ChatResponse(
            response=interrupt_payload.get(
                "message",
                "Your confirmation is required.",
            ),
            session_id=session_id,
            intent_type=intent_type,
            products=[],
            confirmation_required=True,
            pending_confirmation=product,
            order_status=result.get(
                "order_status",
                "awaiting_confirmation",
            ),
            order_id=result.get("order_id"),
            failure_reason=result.get("failure_reason"),
            negotiation=result.get("pending_negotiation"),
        )

    chosen_product = result.get("chosen_product")
    candidates = result.get("candidates", [])

    negotiation_status = result.get("negotiation_status")
    negotiation = result.get("pending_negotiation")
    if negotiation:
        negotiation = {**negotiation, "status": negotiation_status or negotiation.get("status"),
                       "history": result.get("negotiation_history", [])}
    if negotiation_status == "pending" and negotiation:
        response = (f"The seller's configured discount policy offers {negotiation['discount_percent']:.2f}% off "
                    f"{negotiation.get('product_name') or 'this product'}: ₹{negotiation['original_price']:,.2f} "
                    f"to ₹{negotiation['discounted_price']:,.2f}. You can accept, counteroffer, or reject.")
        products = [result["chosen_product"]] if result.get("chosen_product") else []
    elif negotiation_status == "maximum_reached" and negotiation:
        response = (f"That request exceeds the seller's configured discount policy. The maximum is "
                    f"{negotiation['discount_percent']:.2f}%; the best allowed price is ₹{negotiation['discounted_price']:,.2f}.")
        products = [result["chosen_product"]] if result.get("chosen_product") else []
    elif negotiation_status == "accepted":
        response = (f"Offer accepted at ₹{float((negotiation or {}).get('discounted_price', result.get('negotiated_price') or 0)):,.2f}. "
                    "Say ‘buy it’ when you want me to continue to checkout.")
        products = [result["chosen_product"]] if result.get("chosen_product") else []
    elif negotiation_status == "rejected":
        reason = (negotiation or {}).get("rejection_reason")
        response = (f"The seller rejected that request: {reason} No order was placed; we can continue shopping at the catalog price." if reason
                    else "Offer rejected. No order was placed; we can continue shopping at the catalog price.")
        products = [result["chosen_product"]] if result.get("chosen_product") else []
    elif negotiation_status == "cancelled":
        response = "Negotiation cancelled. No order was placed."
        products = [result["chosen_product"]] if result.get("chosen_product") else []
    elif negotiation_status == "no_discount":
        response = f"There is no discount available for this request. The catalog price is ₹{float(result.get('original_price') or 0):,.2f}."
        products = [result["chosen_product"]] if result.get("chosen_product") else []
    elif intent_type == "compare":
        products = candidates

        if chosen_product:
            response = (
                f"After comparing {len(products)} products, "
                f"I recommend **{chosen_product['name']}** "
                f"at ₹{float(chosen_product['price']):,.2f}."
            )
        else:
            response = "I couldn't find suitable products to compare."

    else:
        products = [chosen_product] if chosen_product else []

        if result.get("failure_reason") == "alternative_rejected":
            response = "You rejected the alternative. No order was placed."

        elif result.get("order_status") == "payment_pending":
            response = (
                "Your order has been created and is awaiting payment confirmation."
            )

        elif result.get("order_status") == "paid":
            response = "Payment confirmed. Your order is successful."

        elif result.get("failure_reason"):
            response = (
                f"The shopping workflow could not be completed: "
                f"{result['failure_reason']}."
            )

        elif chosen_product:
            response = (
                f"I recommend **{chosen_product['name']}** "
                f"at ₹{float(chosen_product['price']):,.2f}."
            )

        else:
            response = "I couldn't find a suitable product for your request."

    return ChatResponse(
        response=response,
        session_id=session_id,
        intent_type=intent_type,
        products=products,
        confirmation_required=False,
        pending_confirmation=None,
        order_status=result.get("order_status", "not_started"),
        order_id=result.get("order_id"),
        failure_reason=result.get("failure_reason"),
        payment_status=result.get("payment_status"),
        negotiation=negotiation,
    )

# -------------------------
# Health
# -------------------------

@app.get("/health")
async def health():
    return {"status": "ok"}


# -------------------------
# Start Shopping Workflow
# -------------------------

@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    if buyer_graph is None:
        raise HTTPException(
            status_code=503,
            detail="Buyer agent is not initialized.",
        )

    config = {
        "configurable": {
            "thread_id": request.session_id,
        }
    }

    snapshot = await buyer_graph.aget_state(config)
    if snapshot and any(getattr(task, "interrupts", ()) for task in snapshot.tasks):
        raise HTTPException(
            status_code=409,
            detail="This conversation has a pending approval or payment. Resolve it before sending another request.",
        )

    previous = dict(snapshot.values) if snapshot and snapshot.values else {}
    pending = previous.get("pending_negotiation") or {}
    negotiation_action = parse_negotiation_message(request.message, pending_offer=bool(pending))
    request_kind = "new"
    preserve = {}
    negotiation_requested = False
    if previous.get("chosen_product") and negotiation_action:
        preserve = {key: previous.get(key) for key in (
            "chosen_product", "candidates", "parsed_filters", "budget_ceiling", "decision_log",
            "pending_negotiation", "negotiation_history", "negotiation_attempts", "original_price",
            "negotiation_product_id", "offered_discount_percent", "negotiated_price", "negotiation_status",
        )}
        request_kind = "negotiate"
        if (negotiation_action.get("action") == "accept" and
                previous.get("negotiation_status") == "accepted" and
                negotiation_action.get("purchase_authorized")):
            request_kind = "checkout_accepted"
    elif negotiation_action and negotiation_action.get("action") in ("request_percent", "request_target_price", "request_best"):
        negotiation_requested = True

    initial_state = {
        "run_id": str(uuid.uuid4()),
        "thread_id": request.session_id,
        "goal": request.message,
        "scenario": "budget_search",
        "parsed_filters": None,
        "candidates": [],
        "chosen_product": None,
        "upsell_offer": None,
        "confidence": 0.0,
        "retry_count": 0,
        "budget_ceiling": None,
        "order_status": "not_started",
        "order_id": None,
        "payment_details": None,
        "payment_status": "not_started",
        "decision_log": [],
        "failure_reason": None,
        "pending_alternative": None,
        "alternative_approved": False,
        "confirmation_status": "not_required",
        "negotiation_status": "none",
        "negotiation_product_id": None,
        "original_price": None,
        "requested_discount_percent": None,
        "offered_discount_percent": None,
        "negotiated_price": None,
        "negotiation_attempts": 0,
        "pending_negotiation": None,
        "negotiation_history": [],
        "negotiation_action": negotiation_action,
        "negotiation_requested": negotiation_requested,
        "purchase_authorized": False,
        "request_kind": request_kind,
    }
    initial_state.update({key: value for key, value in preserve.items() if value is not None})
    initial_state["goal"] = request.message
    initial_state["run_id"] = str(uuid.uuid4())
    initial_state["thread_id"] = request.session_id
    initial_state["request_kind"] = request_kind
    initial_state["negotiation_action"] = negotiation_action
    initial_state["negotiation_requested"] = negotiation_requested

    try:
        result = await buyer_graph.ainvoke(
            initial_state,
            config=config,
        )

        return build_chat_response(result, request.session_id)

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Shopping workflow failed: {str(exc)}",
        )


# -------------------------
# Approve / Reject Alternative
# -------------------------

@app.post("/chat/confirmation", response_model=ChatResponse)
async def confirm_alternative(request: ConfirmationRequest):
    if buyer_graph is None:
        raise HTTPException(
            status_code=503,
            detail="Buyer agent is not initialized.",
        )

    config = {
        "configurable": {
            "thread_id": request.session_id,
        }
    }

    try:
        result = await buyer_graph.ainvoke(
            Command(
                resume={
                    "approved": request.approved,
                }
            ),
            config=config,
        )

        return build_chat_response(result, request.session_id)

    except Exception as exc:
        raise HTTPException(
            status_code=409,
            detail=f"Could not resume shopping workflow: {str(exc)}",
        )
