from contextlib import asynccontextmanager

from fastapi import FastAPI
from pydantic import BaseModel

from graph import build_buyer_graph


buyer_graph = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global buyer_graph

    buyer_graph = await build_buyer_graph()

    yield


app = FastAPI(
    title="ShopAgent Buyer Agent",
    version="1.0.0",
    lifespan=lifespan,
)


class ChatRequest(BaseModel):
    message: str
    session_id: str


class ProductResponse(BaseModel):
    id: str
    name: str
    category: str
    subtype: str
    price: float
    size: str
    spec_json: dict
    stock_qty: int
    description: str


class ChatResponse(BaseModel):
    response: str
    products: list[ProductResponse]


def extract_text(content) -> str:
    if isinstance(content, str):
        return content

    if isinstance(content, list):
        text_parts = []

        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                text_parts.append(block.get("text", ""))

        return "\n".join(
            part for part in text_parts if part
        )

    return str(content)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    result = await buyer_graph.ainvoke(
        {
            "goal": request.message,
            "scenario": "budget_search",
            "parsed_filters": None,
            "candidates": [],
            "chosen_product": None,
            "upsell_offer": None,
            "budget_ceiling": 0.0,
            "order_status": "not_started",
            "order_id": None,
            "decision_log": [],
            "failure_reason": None,
        },
        config={
            "configurable": {
                "thread_id": request.session_id,
            }
        },
    )

    chosen_product = result.get("chosen_product")

    if chosen_product:
        response = (
            f"I recommend **{chosen_product['name']}** "
            f"at ₹{float(chosen_product['price']):,.2f}."
        )
    else:
        response = (
            "I couldn't find a suitable product "
            "for your request."
        )

    products = []

    if chosen_product:
        products.append(chosen_product)

    return ChatResponse(
        response=response,
        products=products,
    )