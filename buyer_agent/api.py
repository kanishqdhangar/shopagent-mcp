from fastapi import FastAPI
from pydantic import BaseModel

from langchain_core.messages import HumanMessage

from graph import buyer_graph


app = FastAPI(
    title="ShopAgent Buyer Agent",
    version="1.0.0",
)


class ChatRequest(BaseModel):
    message: str


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

def extract_product_data(products: list[dict]) -> list[dict]:
    result = []

    for item in products:
        product = item.get("product")

        if not product:
            continue

        result.append(product)

    return result

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
            "messages": [
                HumanMessage(content=request.message)
            ],
            "products": [],
        }
    )

    final_message = result["messages"][-1]

    return ChatResponse(
        response=extract_text(final_message.content),
        products=extract_product_data(result["products"]),
    )