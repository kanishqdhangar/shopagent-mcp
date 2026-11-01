
import uuid
from contextlib import asynccontextmanager
from typing import Any, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from langgraph.types import Command
from graph import build_buyer_graph


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
        )

    chosen_product = result.get("chosen_product")
    candidates = result.get("candidates", [])

    if intent_type == "compare":
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
    }

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
