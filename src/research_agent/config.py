from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ENV_FILE_CONFIG = SettingsConfigDict(
    env_file=".env",
    env_file_encoding="utf-8",
    extra="ignore",
)


class PlannerSettings(BaseSettings):
    """Environment-backed configuration for the OpenAI planner adapter."""

    model_config = ENV_FILE_CONFIG

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


class TavilySettings(BaseSettings):
    """Environment-backed configuration for bounded Tavily search."""

    model_config = ENV_FILE_CONFIG

    tavily_api_key: SecretStr = Field(alias="TAVILY_API_KEY")
    tavily_search_depth: str = Field(default="basic", alias="TAVILY_SEARCH_DEPTH")
    tavily_timeout_seconds: float = Field(
        default=10.0,
        gt=0,
        le=30,
        alias="TAVILY_TIMEOUT_SECONDS",
    )

    @field_validator("tavily_api_key")
    @classmethod
    def require_tavily_api_key_value(cls, value: SecretStr) -> SecretStr:
        if not value.get_secret_value().strip():
            raise ValueError("TAVILY_API_KEY must not be blank")
        return value

    @field_validator("tavily_search_depth")
    @classmethod
    def require_basic_search(cls, value: str) -> str:
        if value.strip().casefold() != "basic":
            raise ValueError("TAVILY_SEARCH_DEPTH must be basic in Phase 3A")
        return "basic"


class SynthesisSettings(BaseSettings):
    """Environment-backed configuration for final-report synthesis."""

    model_config = ENV_FILE_CONFIG

    openai_api_key: SecretStr = Field(alias="OPENAI_API_KEY")
    openai_synthesis_model: str = Field(
        default="gpt-5.4-mini",
        min_length=1,
        alias="OPENAI_SYNTHESIS_MODEL",
    )
    openai_synthesis_timeout_seconds: float = Field(
        default=30.0,
        gt=0,
        le=120,
        alias="OPENAI_SYNTHESIS_TIMEOUT_SECONDS",
    )

    @field_validator("openai_api_key")
    @classmethod
    def require_api_key_value(cls, value: SecretStr) -> SecretStr:
        if not value.get_secret_value().strip():
            raise ValueError("OPENAI_API_KEY must not be blank")
        return value
