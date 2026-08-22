from uuid import UUID

from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Product
from app.schemas import ProductCreate
from app.services.embedding_service import embedding_service
from app.services.product_embedding import product_to_embedding_text


async def create_product(
    db: AsyncSession,
    product_data: ProductCreate,
) -> Product:
    product = Product(
        **product_data.model_dump(),
    )

    db.add(product)

    # Flush so the product exists in the session before
    # generating its embedding.
    await db.flush()

    embedding_text = product_to_embedding_text(product)

    product.embedding = await embedding_service.generate_embedding(
        embedding_text
    )

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

async def generate_missing_embeddings(
    db: AsyncSession,
) -> int:
    result = await db.execute(
        select(Product).where(
            Product.embedding.is_(None)
        )
    )

    products = list(result.scalars().all())

    for product in products:
        embedding_text = product_to_embedding_text(product)

        product.embedding = (
            await embedding_service.generate_embedding(
                embedding_text
            )
        )

    await db.commit()

    return len(products)

async def search_products(
    db: AsyncSession,
    query_embedding: list[float],
    limit: int = 10,
) -> list[tuple[Product, float]]:
    distance = Product.embedding.cosine_distance(
        query_embedding
    )

    result = await db.execute(
        select(
            Product,
            distance.label("distance"),
        )
        .where(Product.embedding.is_not(None))
        .order_by(distance)
        .limit(limit)
    )

    rows = result.all()

    return [
        (product, float(distance))
        for product, distance in rows
    ]