from langchain_google_genai import ChatGoogleGenerativeAI
from app.config import settings
import logging

logger = logging.getLogger(__name__)

def get_llm(temperature: float = 0.0) -> ChatGoogleGenerativeAI:
    """
    Returns an instance of the Gemini LLM configured for consistent outputs.
    Using temperature=0.0 is critical for structured output and avoiding hallucination.
    """
    if not settings.GOOGLE_API_KEY or settings.GOOGLE_API_KEY.startswith("AIzaSy_fake_key"):
        logger.warning("GOOGLE_API_KEY is not set correctly in .env!")
        
    return ChatGoogleGenerativeAI(
        model=settings.LLM_MODEL,
        google_api_key=settings.GOOGLE_API_KEY,
        temperature=temperature,
        max_retries=2,
    )
