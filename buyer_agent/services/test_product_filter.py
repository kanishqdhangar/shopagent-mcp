from services.product_filter import filter_products


PRODUCTS = [
    {
        "product": {
            "name": "Cheap Running Shoes",
            "category": "running",
            "subtype": "shoes",
            "price": "2999.00",
            "stock_qty": 10,
        },
        "similarity": 0.90,
    },
    {
        "product": {
            "name": "Expensive Running Shoes",
            "category": "running",
            "subtype": "shoes",
            "price": "3799.00",
            "stock_qty": 10,
        },
        "similarity": 0.88,
    },
    {
        "product": {
            "name": "Out Of Stock Shoes",
            "category": "running",
            "subtype": "shoes",
            "price": "2999.00",
            "stock_qty": 0,
        },
        "similarity": 0.85,
    },
]


def test_filter_by_price():
    result = filter_products(
        PRODUCTS,
        max_price=3500,
    )

    assert len(result) == 2


def test_filter_in_stock():
    result = filter_products(
        PRODUCTS,
        require_in_stock=True,
    )

    assert len(result) == 2


def test_filter_price_and_stock():
    result = filter_products(
        PRODUCTS,
        max_price=3500,
        require_in_stock=True,
    )

    assert len(result) == 1
    assert result[0]["product"]["name"] == "Cheap Running Shoes"


def test_filter_category_and_subtype():
    result = filter_products(
        PRODUCTS,
        category="running",
        subtype="shoes",
    )

    assert len(result) == 3