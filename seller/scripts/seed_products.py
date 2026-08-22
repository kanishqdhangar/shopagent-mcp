import asyncio
from decimal import Decimal

from sqlalchemy import select

from app.db import AsyncSessionLocal
from app.models import Product
from app.services.embedding_service import embedding_service
from app.services.product_embedding import product_to_embedding_text


PRODUCTS = [
    # =========================
    # Running Shoes
    # =========================
    {
        "name": "AeroRun Pro Running Shoes",
        "category": "running",
        "subtype": "shoes",
        "price": Decimal("3499.00"),
        "size": "UK 9",
        "spec_json": {
            "color": "Black",
            "material": "Mesh",
            "cushioning": "High",
            "drop": "8mm",
            "use": "Daily running",
        },
        "stock_qty": 12,
        "description": (
            "Lightweight daily running shoes with responsive "
            "cushioning and breathable mesh."
        ),
    },
    {
        "name": "AeroRun Lite Trainers",
        "category": "running",
        "subtype": "shoes",
        "price": Decimal("2899.00"),
        "size": "UK 8",
        "spec_json": {
            "color": "White",
            "material": "Engineered Mesh",
            "cushioning": "Medium",
            "drop": "8mm",
            "use": "Daily running",
        },
        "stock_qty": 18,
        "description": (
            "Lightweight and breathable trainers designed for "
            "comfortable everyday runs."
        ),
    },
    {
        "name": "Velocity Max Running Shoes",
        "category": "running",
        "subtype": "shoes",
        "price": Decimal("4499.00"),
        "size": "UK 10",
        "spec_json": {
            "color": "Blue",
            "material": "Knit",
            "cushioning": "High",
            "drop": "6mm",
            "use": "Long distance",
        },
        "stock_qty": 7,
        "description": (
            "High-cushioning running shoes built for long-distance "
            "training and extended comfort."
        ),
    },
    {
        "name": "SprintEdge Tempo Shoes",
        "category": "running",
        "subtype": "shoes",
        "price": Decimal("3999.00"),
        "size": "UK 9",
        "spec_json": {
            "color": "Red",
            "material": "Mesh",
            "cushioning": "Responsive",
            "drop": "6mm",
            "use": "Tempo running",
        },
        "stock_qty": 9,
        "description": (
            "Responsive tempo-running shoes designed for fast "
            "training sessions and speed workouts."
        ),
    },
    {
        "name": "TrailGrip Runner",
        "category": "running",
        "subtype": "shoes",
        "price": Decimal("4299.00"),
        "size": "UK 9",
        "spec_json": {
            "color": "Green",
            "material": "Synthetic Mesh",
            "cushioning": "Medium",
            "sole": "Trail Grip",
            "use": "Trail running",
        },
        "stock_qty": 6,
        "description": (
            "Durable trail running shoes with enhanced grip for "
            "uneven outdoor surfaces."
        ),
    },
    {
        "name": "ComfortRun Daily Shoes",
        "category": "running",
        "subtype": "shoes",
        "price": Decimal("2499.00"),
        "size": "UK 8",
        "spec_json": {
            "color": "Grey",
            "material": "Mesh",
            "cushioning": "Soft",
            "drop": "10mm",
            "use": "Daily running",
        },
        "stock_qty": 21,
        "description": (
            "Affordable cushioned running shoes for comfortable "
            "daily jogging and beginner runners."
        ),
    },
    {
        "name": "RaceFly Carbon Trainer",
        "category": "running",
        "subtype": "shoes",
        "price": Decimal("4999.00"),
        "size": "UK 10",
        "spec_json": {
            "color": "Black",
            "material": "Performance Mesh",
            "plate": "Carbon",
            "cushioning": "High",
            "use": "Racing",
        },
        "stock_qty": 4,
        "description": (
            "Performance running shoe with carbon plate and "
            "responsive foam for race-day speed."
        ),
    },
    {
        "name": "FlexRun Stability Shoes",
        "category": "running",
        "subtype": "shoes",
        "price": Decimal("3799.00"),
        "size": "UK 9",
        "spec_json": {
            "color": "Navy",
            "material": "Engineered Mesh",
            "support": "Stability",
            "cushioning": "Medium",
            "use": "Daily running",
        },
        "stock_qty": 11,
        "description": (
            "Stable everyday running shoes offering structured "
            "support and balanced cushioning."
        ),
    },
    {
        "name": "UrbanRun Lightweight Shoes",
        "category": "running",
        "subtype": "shoes",
        "price": Decimal("3199.00"),
        "size": "UK 8",
        "spec_json": {
            "color": "Black",
            "material": "Mesh",
            "cushioning": "Medium",
            "weight": "Lightweight",
            "use": "Road running",
        },
        "stock_qty": 15,
        "description": (
            "Lightweight road-running shoes designed for city "
            "running and everyday training."
        ),
    },

    # =========================
    # Running T-Shirts
    # =========================
    {
        "name": "DryMotion Running T-Shirt",
        "category": "running",
        "subtype": "t-shirt",
        "price": Decimal("999.00"),
        "size": "L",
        "spec_json": {
            "color": "Black",
            "material": "Polyester",
            "technology": "Moisture Wicking",
            "fit": "Regular",
        },
        "stock_qty": 30,
        "description": (
            "Moisture-wicking running t-shirt that keeps the body "
            "dry during intense workouts."
        ),
    },
    {
        "name": "BreezeRun Performance Tee",
        "category": "running",
        "subtype": "t-shirt",
        "price": Decimal("1199.00"),
        "size": "M",
        "spec_json": {
            "color": "Blue",
            "material": "Polyester",
            "technology": "Quick Dry",
            "fit": "Athletic",
        },
        "stock_qty": 24,
        "description": (
            "Breathable quick-dry performance tee for running "
            "and outdoor workouts."
        ),
    },
    {
        "name": "RunCool Mesh T-Shirt",
        "category": "running",
        "subtype": "t-shirt",
        "price": Decimal("899.00"),
        "size": "L",
        "spec_json": {
            "color": "Grey",
            "material": "Mesh",
            "technology": "Ventilation",
            "fit": "Regular",
        },
        "stock_qty": 27,
        "description": (
            "Highly breathable mesh running shirt designed to "
            "improve airflow during hot-weather runs."
        ),
    },
    {
        "name": "EnduranceDry Running Tee",
        "category": "running",
        "subtype": "t-shirt",
        "price": Decimal("1299.00"),
        "size": "XL",
        "spec_json": {
            "color": "Green",
            "material": "Polyester",
            "technology": "Anti Odor",
            "fit": "Athletic",
        },
        "stock_qty": 16,
        "description": (
            "Performance running tee with sweat management and "
            "odor-resistant fabric for long training sessions."
        ),
    },
    {
        "name": "NightRun Reflective Tee",
        "category": "running",
        "subtype": "t-shirt",
        "price": Decimal("1399.00"),
        "size": "M",
        "spec_json": {
            "color": "Black",
            "material": "Polyester",
            "reflective": True,
            "technology": "Quick Dry",
        },
        "stock_qty": 13,
        "description": (
            "Reflective quick-dry running t-shirt designed for "
            "better visibility during evening runs."
        ),
    },
    {
        "name": "EveryRun Basic Tee",
        "category": "running",
        "subtype": "t-shirt",
        "price": Decimal("699.00"),
        "size": "M",
        "spec_json": {
            "color": "White",
            "material": "Polyester",
            "fit": "Regular",
        },
        "stock_qty": 35,
        "description": (
            "Simple lightweight running t-shirt for everyday "
            "training at an affordable price."
        ),
    },

    # =========================
    # Running Shorts
    # =========================
    {
        "name": "AeroFlex Running Shorts",
        "category": "running",
        "subtype": "shorts",
        "price": Decimal("899.00"),
        "size": "M",
        "spec_json": {
            "color": "Black",
            "material": "Polyester",
            "liner": "Built-in",
            "pockets": 1,
        },
        "stock_qty": 22,
        "description": (
            "Lightweight running shorts with a built-in liner "
            "and secure pocket."
        ),
    },
    {
        "name": "SprintLite Running Shorts",
        "category": "running",
        "subtype": "shorts",
        "price": Decimal("799.00"),
        "size": "L",
        "spec_json": {
            "color": "Blue",
            "material": "Polyester",
            "liner": "Brief",
            "pockets": 2,
        },
        "stock_qty": 26,
        "description": (
            "Breathable lightweight shorts designed for speed "
            "workouts and daily runs."
        ),
    },
    {
        "name": "EnduranceRun Training Shorts",
        "category": "running",
        "subtype": "shorts",
        "price": Decimal("1099.00"),
        "size": "XL",
        "spec_json": {
            "color": "Grey",
            "material": "Stretch Polyester",
            "liner": "Built-in",
            "pockets": 2,
        },
        "stock_qty": 19,
        "description": (
            "Stretch running shorts with comfortable lining and "
            "storage for longer training sessions."
        ),
    },
    {
        "name": "TrailMove Running Shorts",
        "category": "running",
        "subtype": "shorts",
        "price": Decimal("1199.00"),
        "size": "M",
        "spec_json": {
            "color": "Green",
            "material": "Ripstop",
            "liner": "Built-in",
            "pockets": 3,
        },
        "stock_qty": 10,
        "description": (
            "Durable running shorts with multiple pockets for "
            "trail runs and outdoor training."
        ),
    },

    # =========================
    # Running Socks
    # =========================
    {
        "name": "RunDry Performance Socks",
        "category": "running",
        "subtype": "socks",
        "price": Decimal("399.00"),
        "size": "M",
        "spec_json": {
            "color": "White",
            "material": "Nylon Blend",
            "technology": "Moisture Wicking",
            "length": "Ankle",
        },
        "stock_qty": 40,
        "description": (
            "Moisture-wicking ankle socks with cushioned support "
            "for everyday running."
        ),
    },
    {
        "name": "CushionStep Running Socks",
        "category": "running",
        "subtype": "socks",
        "price": Decimal("499.00"),
        "size": "L",
        "spec_json": {
            "color": "Black",
            "material": "Polyester Blend",
            "technology": "Cushioned",
            "length": "Crew",
        },
        "stock_qty": 34,
        "description": (
            "Cushioned running socks designed to reduce impact "
            "and improve comfort on long runs."
        ),
    },
    {
        "name": "CoolMesh Running Socks",
        "category": "running",
        "subtype": "socks",
        "price": Decimal("449.00"),
        "size": "M",
        "spec_json": {
            "color": "Grey",
            "material": "Mesh Knit",
            "technology": "Breathable",
            "length": "No Show",
        },
        "stock_qty": 31,
        "description": (
            "Breathable no-show running socks designed for "
            "cooler feet during workouts."
        ),
    },
    {
        "name": "LongRun Compression Socks",
        "category": "running",
        "subtype": "socks",
        "price": Decimal("699.00"),
        "size": "L",
        "spec_json": {
            "color": "Black",
            "material": "Nylon",
            "technology": "Compression",
            "length": "Calf",
        },
        "stock_qty": 17,
        "description": (
            "Calf-length compression socks providing supportive "
            "fit for long-distance running."
        ),
    },

    # =========================
    # Hydration
    # =========================
    {
        "name": "HydraRun 500ml Bottle",
        "category": "running",
        "subtype": "hydration",
        "price": Decimal("599.00"),
        "size": "500ml",
        "spec_json": {
            "color": "Blue",
            "material": "BPA Free Plastic",
            "capacity": "500ml",
            "leakproof": True,
        },
        "stock_qty": 25,
        "description": (
            "Compact leakproof hydration bottle for running "
            "and gym workouts."
        ),
    },
    {
        "name": "HydraRun 750ml Bottle",
        "category": "running",
        "subtype": "hydration",
        "price": Decimal("749.00"),
        "size": "750ml",
        "spec_json": {
            "color": "Black",
            "material": "BPA Free Plastic",
            "capacity": "750ml",
            "leakproof": True,
        },
        "stock_qty": 20,
        "description": (
            "Large-capacity leakproof bottle suitable for "
            "long runs and outdoor training."
        ),
    },
    {
        "name": "QuickSip Running Flask",
        "category": "running",
        "subtype": "hydration",
        "price": Decimal("699.00"),
        "size": "350ml",
        "spec_json": {
            "color": "Clear",
            "material": "Soft Flask",
            "capacity": "350ml",
            "collapsible": True,
        },
        "stock_qty": 14,
        "description": (
            "Soft collapsible hydration flask designed for "
            "carrying water during races and long runs."
        ),
    },
    {
        "name": "HydraRun Waist Bottle Belt",
        "category": "running",
        "subtype": "hydration",
        "price": Decimal("999.00"),
        "size": "Adjustable",
        "spec_json": {
            "color": "Black",
            "bottles": 2,
            "pockets": 1,
            "adjustable": True,
        },
        "stock_qty": 8,
        "description": (
            "Adjustable running hydration belt with bottles and "
            "storage for phones or small essentials."
        ),
    },

    # =========================
    # Accessories
    # =========================
    {
        "name": "RunLite Waist Belt",
        "category": "running",
        "subtype": "accessory",
        "price": Decimal("699.00"),
        "size": "Adjustable",
        "spec_json": {
            "color": "Black",
            "pockets": 2,
            "reflective": True,
        },
        "stock_qty": 18,
        "description": (
            "Slim reflective running belt for carrying a phone, "
            "keys, and small essentials."
        ),
    },
    {
        "name": "NightTrack Reflective Band",
        "category": "running",
        "subtype": "accessory",
        "price": Decimal("299.00"),
        "size": "Adjustable",
        "spec_json": {
            "color": "Yellow",
            "reflective": True,
            "closure": "Velcro",
        },
        "stock_qty": 32,
        "description": (
            "Reflective adjustable band designed to improve "
            "visibility during low-light runs."
        ),
    },
    {
        "name": "RunCap Lightweight Performance Cap",
        "category": "running",
        "subtype": "accessory",
        "price": Decimal("599.00"),
        "size": "Adjustable",
        "spec_json": {
            "color": "Black",
            "material": "Polyester",
            "breathable": True,
            "uv_protection": True,
        },
        "stock_qty": 23,
        "description": (
            "Lightweight breathable running cap with UV protection "
            "for outdoor training."
        ),
    },
    {
        "name": "SweatShield Running Headband",
        "category": "running",
        "subtype": "accessory",
        "price": Decimal("349.00"),
        "size": "One Size",
        "spec_json": {
            "color": "Grey",
            "material": "Stretch Fabric",
            "technology": "Sweat Wicking",
        },
        "stock_qty": 29,
        "description": (
            "Sweat-wicking stretch headband designed to keep "
            "sweat away during running sessions."
        ),
    },
    {
        "name": "Performance Running Gloves",
        "category": "running",
        "subtype": "accessory",
        "price": Decimal("799.00"),
        "size": "M",
        "spec_json": {
            "color": "Black",
            "material": "Stretch Polyester",
            "touchscreen": True,
        },
        "stock_qty": 12,
        "description": (
            "Lightweight running gloves with touchscreen-compatible "
            "fingertips for cooler weather."
        ),
    },
    {
        "name": "RaceDay Running Sunglasses",
        "category": "running",
        "subtype": "accessory",
        "price": Decimal("1499.00"),
        "size": "One Size",
        "spec_json": {
            "color": "Black",
            "lens": "Polarized",
            "uv_protection": "UV400",
            "weight": "Lightweight",
        },
        "stock_qty": 9,
        "description": (
            "Lightweight polarized running sunglasses with UV400 "
            "protection for bright outdoor conditions."
        ),
    },
]


async def seed_products() -> None:
    async with AsyncSessionLocal() as db:
        created = 0
        skipped = 0

        for product_data in PRODUCTS:
            existing = await db.execute(
                select(Product).where(
                    Product.name == product_data["name"]
                )
            )

            if existing.scalar_one_or_none():
                skipped += 1
                continue

            product = Product(**product_data)

            db.add(product)
            await db.flush()

            embedding_text = product_to_embedding_text(product)

            product.embedding = (
                await embedding_service.generate_embedding(
                    embedding_text
                )
            )

            created += 1

            print(
                f"Created: {product.name}"
            )

        await db.commit()

        print()
        print(f"Created products: {created}")
        print(f"Skipped products: {skipped}")


if __name__ == "__main__":
    asyncio.run(seed_products())