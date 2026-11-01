import asyncio
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.config import settings
from app.services import discount_service


@pytest.mark.parametrize(("percent", "expected"), [
    (5, "95.00"), (10, "90.00"), (15, "85.00"),
])
def test_discount_rounds_from_catalog_price(percent, expected):
    assert discount_service.quote_discount(Decimal("100.00"), Decimal(str(percent))) == Decimal(expected)


def test_policy_cap_and_zero_discount_are_seller_enforced(monkeypatch):
    product_id = uuid4()
    product = SimpleNamespace(id=product_id, price=Decimal("100.00"))
    async def get_product(_db, _product_id):
        return product
    monkeypatch.setattr(discount_service, "get_product", get_product)

    assert asyncio.run(discount_service.apply_discount(None, product_id, percent=0))["discounted_price"] == 100.0
    assert asyncio.run(discount_service.apply_discount(None, product_id, percent=settings.max_discount_percent))["applied"]
    rejected = asyncio.run(discount_service.apply_discount(None, product_id, percent=settings.max_discount_percent + 1))
    assert rejected["applied"] is False
    assert rejected["best_allowed_offer"]["discount_percent"] == settings.max_discount_percent
    assert product.price == Decimal("100.00")


def test_absolute_target_is_converted_and_price_change_rejected(monkeypatch):
    product_id = uuid4()
    product = SimpleNamespace(id=product_id, price=Decimal("100.00"))
    async def get_product(_db, _product_id):
        return product
    monkeypatch.setattr(discount_service, "get_product", get_product)

    quote = asyncio.run(discount_service.apply_discount(None, product_id, target_price=90))
    assert quote["applied"] and quote["applied_discount_percent"] == 10
    changed = asyncio.run(discount_service.apply_discount(None, product_id, percent=10, expected_original_price=99))
    assert changed["applied"] is False
    assert changed["expected_original_price_matches"] is False
