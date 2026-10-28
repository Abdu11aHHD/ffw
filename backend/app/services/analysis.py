from ..config import Settings
from .deepseek import DeepSeekService
from .gemini import GeminiService

def analysis_service(settings: Settings):
    if settings.ai_provider == "gemini":
        return GeminiService(settings)
    if settings.ai_provider == "local":
        return GeminiService(settings.model_copy(update={"gemini_api_key": ""}))
    return DeepSeekService(settings)
