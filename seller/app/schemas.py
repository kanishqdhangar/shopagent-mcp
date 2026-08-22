from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ProductCreate(BaseModel):
    name: str
    category: str
    subtype: str | None = None
    price: Decimal = Field(gt=0)
    size: str | None = None
    spec_json: dict | None = None
    stock_qty: int = Field(default=0, ge=0)
    description: str | None = None


class ProductResponse(ProductCreate):
    id: UUID
    # embedding: list[float] | None = None

    model_config = ConfigDict(from_attributes=True)


class InventoryResponse(BaseModel):
    product_id: UUID
    stock_qty: int
    in_stock: bool