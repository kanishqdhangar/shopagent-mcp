from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Product
from app.schemas import ProductCreate


async def create_product(
    db: AsyncSession,
    product_data: ProductCreate,
) -> Product:
    product = Product(
        **product_data.model_dump(),
    )

    db.add(product)

    await db.commit()
    await db.refresh(product)

    return product


async def get_product(
    db: AsyncSession,
    product_id: UUID,
) -> Product | None:
    result = await db.execute(
        select(Product).where(Product.id == product_id)
    )

    return result.scalar_one_or_none()


async def get_products(
    db: AsyncSession,
    limit: int = 50,
) -> list[Product]:
    result = await db.execute(
        select(Product)
        .order_by(Product.name)
        .limit(limit)
    )

    return list(result.scalars().all())


async def check_inventory(
    db: AsyncSession,
    product_id: UUID,
) -> Product | None:
    return await get_product(db, product_id)