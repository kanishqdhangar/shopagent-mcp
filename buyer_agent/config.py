from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    gemini_api_key: str
    database_url: str
    razorpay_webhook_secret: str = ""


settings = Settings()