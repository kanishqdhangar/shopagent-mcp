from uuid import UUID
import asyncio
import logging
import os
from mcp.server.transport_security import TransportSecuritySettings
from fastapi import Depends, FastAPI, HTTPException, Query, Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from starlette.middleware.trustedhost import TrustedHostMiddleware
from app.mcp_server import mcp
from contextlib import asynccontextmanager

from app.db import get_db
from app.db import AsyncSessionLocal
from app.schemas import (
    InventoryResponse,
    ProductCreate,
    ProductResponse,
)
from app.services.product_service import (
    check_inventory,
    create_product,
    get_product,
    get_products,
    generate_missing_embeddings, 
    search_products
)
from pydantic import BaseModel
from app.services.embedding_service import embedding_service
from app.services.product_embedding import product_to_embedding_text

import razorpay


from app.config import settings
from app.services.order_service import process_payment_webhook, reconcile_pending_payments
from app.payment_security import verify_razorpay_signature

logger = logging.getLogger(__name__)


async def payment_reconciliation_loop():
    interval = max(30, int(os.getenv("PAYMENT_RECONCILIATION_INTERVAL_SECONDS", "30")))
    while True:
        try:
            if settings.razorpay_key_id and settings.razorpay_key_secret:
                async with AsyncSessionLocal() as db:
                    count = await reconcile_pending_payments(db)
                if count:
                    logger.info("Reconciled %s Razorpay payment(s)", count)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Razorpay payment reconciliation failed")
        await asyncio.sleep(interval)

@asynccontextmanager
async def lifespan(app: FastAPI):
    async with mcp.session_manager.run():
        task = asyncio.create_task(payment_reconciliation_loop())
        try:
            yield
        finally:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass


app = FastAPI(
    title="ShopAgent Seller API",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=[
        "localhost",
        "127.0.0.1",
        "seller",
        "seller:8000",
    ],
)

@app.get("/health")
async def health():
    return {
        "status": "ok",
        "service": "seller-api",
    }


@app.get("/health/db")
async def database_health(
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(text("SELECT 1"))
    value = result.scalar_one()

    return {
        "status": "ok",
        "database": "postgresql",
        "result": value,
    }

class ProductSearchRequest(BaseModel):
    query: str
    limit: int = 10

@app.post(
    "/products",
    response_model=ProductResponse,
    status_code=201,
)
async def create_product_endpoint(
    product_data: ProductCreate,
    db: AsyncSession = Depends(get_db),
):
    return await create_product(db, product_data)


@app.get(
    "/products",
    response_model=list[ProductResponse],
)
async def list_products_endpoint(
    limit: int = Query(default=50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    return await get_products(db, limit)


@app.get(
    "/products/{product_id}",
    response_model=ProductResponse,
)
async def get_product_endpoint(
    product_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    product = await get_product(db, product_id)

    if product is None:
        raise HTTPException(
            status_code=404,
            detail="Product not found",
        )

    return product


@app.get(
    "/products/{product_id}/inventory",
    response_model=InventoryResponse,
)
async def inventory_endpoint(
    product_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    product = await check_inventory(db, product_id)

    if product is None:
        raise HTTPException(
            status_code=404,
            detail="Product not found",
        )

    return InventoryResponse(
        product_id=product.id,
        stock_qty=product.stock_qty,
        in_stock=product.stock_qty > 0,
    )

@app.post("/products/search")
async def search_products_endpoint(
    request: ProductSearchRequest,
    db: AsyncSession = Depends(get_db),
):
    query_embedding = (
        await embedding_service.generate_embedding(
            request.query
        )
    )

    results = await search_products(
        db,
        query_embedding,
        request.limit,
    )

    return {
        "query": request.query,
        "results": [
            {
                "product": ProductResponse.model_validate(
                    product
                ).model_dump(mode="json"),
                "distance": distance,
                "similarity": 1 - distance,
            }
            for product, distance in results
        ],
    }

@app.post("/webhooks/razorpay")
async def razorpay_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    body = await request.body()

    signature = request.headers.get(
        "X-Razorpay-Signature"
    )

    if not signature:
        raise HTTPException(
            status_code=400,
            detail="Missing Razorpay signature.",
        )

    if not settings.razorpay_webhook_secret:
        raise HTTPException(
            status_code=500,
            detail="Razorpay webhook secret is not configured.",
        )

    if not verify_razorpay_signature(body, signature, settings.razorpay_webhook_secret):
        raise HTTPException(
            status_code=400,
            detail="Invalid Razorpay webhook signature.",
        )

    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid webhook JSON.")

    event_type = payload.get("event")
    if event_type not in {"payment.captured", "order.paid", "payment.failed"}:
        return {"received": True, "processed": False, "event": event_type}

    event_payload = payload.get("payload", {})
    payment_entity = (event_payload.get("payment") or {}).get("entity") or {}
    order_entity = (event_payload.get("order") or {}).get("entity") or {}
    entity = payment_entity or order_entity
    razorpay_order_id = entity.get("order_id") or order_entity.get("id")
    if not razorpay_order_id:
        raise HTTPException(status_code=400, detail="Razorpay order ID missing from webhook.")

    amount = entity.get("amount") or order_entity.get("amount")
    currency = entity.get("currency") or order_entity.get("currency")
    payment_status = entity.get("status") or order_entity.get("status")
    captured = event_type in {"payment.captured", "order.paid"} and payment_status in {"captured", "paid"}
    if event_type == "order.paid" and payment_status == "created":
        captured = False

    import hashlib
    event_id = request.headers.get("X-Razorpay-Event-Id") or hashlib.sha256(body).hexdigest()
    result = await process_payment_webhook(
        db,
        event_id=event_id,
        event_type=event_type,
        razorpay_order_id=razorpay_order_id,
        razorpay_payment_id=payment_entity.get("id"),
        amount=int(amount) if amount is not None else None,
        currency=currency,
        captured=captured,
        payload=payload,
    )
    if result.get("reason"):
        status_code = 404 if result["reason"] == "Order not found." else 400
        raise HTTPException(status_code=status_code, detail=result["reason"])
    return {"received": True, **result}


@app.get("/orders/{order_id}")
async def order_status_endpoint(order_id: UUID, db: AsyncSession = Depends(get_db)):
    from app.services.order_service import get_order
    order = await get_order(db, order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found.")
    return order


app.mount(
    "/mcp",
    mcp.streamable_http_app(
        stateless_http=True,
        json_response=True,
        streamable_http_path="/",
        transport_security=TransportSecuritySettings(
            allowed_hosts=[
                "localhost:*",
                "127.0.0.1:*",
                "seller:*",
            ],
            allowed_origins=[
                "http://localhost:*",
                "http://127.0.0.1:*",
                "http://seller:*",
            ],
        ),
    )
)
#used only for testing purposes no need in prod

# @app.post("/products/{product_id}/embedding/test")
# async def test_product_embedding(
#     product_id: UUID,
#     db: AsyncSession = Depends(get_db),
# ):
#     product = await get_product(db, product_id)

#     if product is None:
#         raise HTTPException(
#             status_code=404,
#             detail="Product not found",
#         )

#     text = product_to_embedding_text(product)

#     embedding = await embedding_service.generate_embedding(
#         text
#     )

#     return {
#         "product_id": product.id,
#         "text": text,
#         "dimensions": len(embedding),
#         "embedding_preview": embedding[:5],
#     }

# @app.post("/products/embeddings/backfill")
# async def backfill_embeddings(
#     db: AsyncSession = Depends(get_db),
# ):
#     count = await generate_missing_embeddings(db)

#     return {
#         "status": "ok",
#         "updated_products": count,
#     }
