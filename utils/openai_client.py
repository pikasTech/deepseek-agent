from langchain_openai import OpenAI
from config import OPENAI_API_KEY, OPENAI_BASE_URL, MODEL_NAME, TEMPERATURE, MAX_TOKENS

class OpenAIClient:
    """OpenAI 客户端封装"""
    def __init__(self):
        self.llm = OpenAI(
            openai_api_key=OPENAI_API_KEY,
            base_url=OPENAI_BASE_URL,
            temperature=TEMPERATURE,
            max_tokens=MAX_TOKENS,
        )