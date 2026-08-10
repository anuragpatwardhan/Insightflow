from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg2://insightflow:insightflow@localhost:5432/insightflow"
    duckdb_path: str = "./data/analytics.duckdb"
    ollama_enabled: bool = False
    ollama_host: str = "http://localhost:11434"
    ollama_model: str = "llama3.1:8b"

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False, extra="ignore")


settings = Settings()
