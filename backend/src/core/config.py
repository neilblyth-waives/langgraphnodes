"""
Configuration management using Pydantic Settings.
"""
from typing import List, Optional
from urllib.parse import quote_plus
from pydantic import Field, PostgresDsn, RedisDsn, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    # Environment
    environment: str = Field(default="development", description="Environment: development, staging, production")

    # API Configuration
    api_host: str = Field(default="0.0.0.0", description="API host")
    api_port: int = Field(default=8000, description="API port")
    api_reload: bool = Field(default=True, description="Enable auto-reload in development")
    cors_origins: str = Field(default="http://localhost:3000", description="CORS allowed origins")

    # LLM Provider - OpenAI
    openai_api_key: Optional[str] = Field(default=None, description="OpenAI API key")
    openai_model: str = Field(default="gpt-4-turbo-preview", description="OpenAI model")
    openai_embedding_model: str = Field(default="text-embedding-3-small", description="OpenAI embedding model")

    # LLM Provider - Anthropic
    anthropic_api_key: Optional[str] = Field(default=None, description="Anthropic API key")
    anthropic_model: str = Field(default="claude-3-opus-20240229", description="Anthropic model")

    # LangSmith
    langchain_tracing_v2: bool = Field(default=False, description="Enable LangSmith tracing")
    langchain_api_key: Optional[str] = Field(default=None, description="LangSmith API key")
    langchain_project: str = Field(default="dv360-agent-system", description="LangSmith project name")

    # PostgreSQL
    postgres_host: str = Field(default="145.223.88.120", description="PostgreSQL host")
    postgres_port: int = Field(default=5432, description="PostgreSQL port")
    postgres_db: str = Field(default="dv360agent", description="PostgreSQL database")
    postgres_user: str = Field(default="dvdbowner", description="PostgreSQL user")
    postgres_password: str = Field(default="dvagentlangchain", description="PostgreSQL password")
    database_url: Optional[str] = Field(default=None, description="PostgreSQL connection URL")

    # Redis
    redis_host: str = Field(default="localhost", description="Redis host")
    redis_port: int = Field(default=6379, description="Redis port")
    redis_db: int = Field(default=0, description="Redis database number")
    redis_password: Optional[str] = Field(default=None, description="Redis password")
    redis_url: Optional[str] = Field(default=None, description="Redis connection URL")

    # Snowflake
    snowflake_account: str = Field(default="", description="Snowflake account")
    snowflake_user: str = Field(default="", description="Snowflake user")
    snowflake_password: Optional[str] = Field(default="", description="Snowflake password (not needed with key pair auth)")
    snowflake_warehouse: str = Field(default="", description="Snowflake warehouse")
    snowflake_database: str = Field(default="", description="Snowflake database")
    snowflake_schema: str = Field(default="", description="Snowflake schema")
    snowflake_role: Optional[str] = Field(default=None, description="Snowflake role")
    snowflake_private_key_path: Optional[str] = Field(default=None, description="Path to private key file for key pair authentication (preferred - no 2FA)")

    # Memory Configuration
    vector_dimension: int = Field(default=1536, description="Vector dimension for embeddings")
    memory_top_k: int = Field(default=5, description="Number of relevant memories to retrieve")
    learning_confidence_threshold: float = Field(default=0.7, description="Minimum confidence for learnings")

    # Session Management
    session_ttl_hours: int = Field(default=24, description="Session TTL in hours")
    max_messages_per_session: int = Field(default=100, description="Max messages per session")

    # Query Caching
    query_cache_ttl_minutes: int = Field(default=60, description="Query cache TTL in minutes")
    enable_query_cache: bool = Field(default=True, description="Enable query caching")

    # Rate Limiting
    rate_limit_requests_per_minute: int = Field(default=60, description="Rate limit: requests per minute")
    rate_limit_tokens_per_day: int = Field(default=100000, description="Rate limit: tokens per day")

    # Agent Configuration
    max_agent_execution_time_seconds: int = Field(default=120, description="Max agent execution time")
    enable_parallel_agent_execution: bool = Field(default=True, description="Enable parallel agent execution")

    # Telemetry & Monitoring
    log_level: str = Field(default="INFO", description="Log level")
    enable_prometheus: bool = Field(default=True, description="Enable Prometheus metrics")
    prometheus_port: int = Field(default=9090, description="Prometheus port")
    enable_opentelemetry: bool = Field(default=False, description="Enable OpenTelemetry")
    otel_exporter_otlp_endpoint: str = Field(default="http://localhost:4318", description="OTLP endpoint")

    # Security
    secret_key: str = Field(default="dev-secret-key-change-in-production", description="Secret key for JWT")
    algorithm: str = Field(default="HS256", description="JWT algorithm")
    access_token_expire_minutes: int = Field(default=30, description="Access token expiration")

    @field_validator("database_url", mode="before")
    @classmethod
    def assemble_db_connection(cls, v: Optional[str], info) -> str:
        """Build database URL if not provided."""
        if isinstance(v, str) and v:
            return v

        values = info.data
        return str(
            PostgresDsn.build(
                scheme="postgresql+asyncpg",
                username=values.get("postgres_user"),
                password=values.get("postgres_password"),
                host=values.get("postgres_host"),
                port=values.get("postgres_port"),
                path=f"{values.get('postgres_db') or ''}",
            )
        )

    @field_validator("redis_url", mode="before")
    @classmethod
    def assemble_redis_connection(cls, v: Optional[str], info) -> str:
        """Build Redis URL if not provided. Properly URL-encodes password with special characters."""
        if isinstance(v, str) and v:
            return v

        values = info.data
        password = values.get("redis_password")
        # URL-encode password to handle special characters like %, #, @, etc.
        auth = f"default:{quote_plus(password)}@" if password else ""

        return f"redis://{auth}{values.get('redis_host')}:{values.get('redis_port')}/{values.get('redis_db')}"

    @property
    def cors_origins_list(self) -> List[str]:
        """Parse CORS origins from comma-separated string."""
        return [origin.strip() for origin in self.cors_origins.split(",")]

    @property
    def is_production(self) -> bool:
        """Check if running in production."""
        return self.environment.lower() == "production"

    @property
    def is_development(self) -> bool:
        """Check if running in development."""
        return self.environment.lower() == "development"


# Global settings instance
settings = Settings()
