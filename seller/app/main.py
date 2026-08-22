from fastapi import FastAPI

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