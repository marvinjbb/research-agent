from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class PlannerSettings(BaseSettings):
    """Environment-backed configuration for the OpenAI planner adapter."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    openai_api_key: SecretStr = Field(alias="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-5.4-mini", min_length=1, alias="OPENAI_MODEL")
    openai_timeout_seconds: float = Field(
        default=30.0,
        gt=0,
        le=120,
        alias="OPENAI_TIMEOUT_SECONDS",
    )

    @field_validator("openai_api_key")
    @classmethod
    def require_api_key_value(cls, value: SecretStr) -> SecretStr:
        if not value.get_secret_value().strip():
            raise ValueError("OPENAI_API_KEY must not be blank")
        return value
