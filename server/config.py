from pathlib import Path
from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / '.env')

class Settings(BaseSettings):
    openalex_api_key: str = ''
    database_url: str = 'sqlite:///./work/papertrail.sqlite3'
    llm_base_url: str = 'https://generativelanguage.googleapis.com/v1beta/openai'
    llm_model: str = 'gemini-3.6-flash'
    llm_fallback_model: str = 'gemini-2.5-flash'
    llm_api_key: str = ''
    access_code: str = ''
    reranker_enabled: bool = True
    reranker_model: str = 'Alibaba-NLP/gte-reranker-modernbert-base'
    reranker_backend: str = 'onnx'
    reranker_revision: str = 'f7481e6055501a30fb19d090657df9ec1f79ab2c'
    max_api_calls: int = 12
    model_config = SettingsConfigDict(env_file=ROOT / '.env', extra='ignore')

settings = Settings()
