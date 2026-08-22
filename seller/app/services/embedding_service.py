from google import genai

from app.config import settings


class EmbeddingService:
    def __init__(self):
        if not settings.gemini_api_key:
            raise RuntimeError(
                "GEMINI_API_KEY is not configured"
            )

        self.client = genai.Client(
            api_key=settings.gemini_api_key,
        )

        self.model = "gemini-embedding-001"

    async def generate_embedding(
        self,
        text: str,
    ) -> list[float]:
        response = await self.client.aio.models.embed_content(
            model=self.model,
            contents=text,
            config={
                "output_dimensionality": 768,
            },
        )

        return response.embeddings[0].values


embedding_service = EmbeddingService()