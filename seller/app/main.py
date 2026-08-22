from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.mcp_server import mcp
from contextlib import asynccontextmanager

from app.db import get_db
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

@asynccontextmanager
async def lifespan(app: FastAPI):
    async with mcp.session_manager.run():
        yield


app = FastAPI(
    title="ShopAgent Seller API",
    version="0.1.0",
    lifespan=lifespan,
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

app.mount(
    "/mcp",
    mcp.streamable_http_app(
        stateless_http=True,
        json_response=True,
        streamable_http_path="/",
    ),
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
