from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

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
)


app = FastAPI(
    title="ShopAgent Seller API",
    version="0.1.0",
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