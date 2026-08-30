"""Application configuration loaded from environment variables / `.env`.

Centralizes all settings (DB, embeddings, LLM) so no secret or connection
string is hard-coded anywhere in the codebase.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # Application
    app_name: str = "Wishlist Conversion Discovery Engine"
    environment: str = "development"
    log_level: str = "INFO"
    # Comma-separated browser origins allowed to call the API (Vercel URLs).
    # Empty / "*" keeps the permissive default used in local development.
    cors_origins: str = "*"

    # Database
    postgres_user: str = "discovery"
    postgres_password: str = "discovery"
    postgres_db: str = "discovery"
    postgres_host: str = "127.0.0.1"
    postgres_port: int = 5432
    database_url: str | None = None

    # Embeddings (BGE)
    embedding_model: str = "BAAI/bge-large-en-v1.5"
    embedding_dim: int = 1024

    # LLM (Groq)
    groq_api_key: str | None = None
    groq_model: str = "llama-3.3-70b-versatile"

    # Retrieval
    retrieval_top_k: int = 8
    rag_rerank_top_k: int = 6
    rag_min_chunks: int = 1
    rag_min_top_score: float = 0.38
    rag_min_avg_score: float = 0.32

    # Evaluation targets (Phase 6)
    eval_retrieval_hit_at_k: int = 3
    eval_retrieval_hit_target: float = 0.80
    eval_faithfulness_target: float = 0.85
    eval_taxonomy_accuracy_target: float = 0.80
    eval_report_path: str = "data/eval_report.json"

    # Cost controls (Phase 6)
    embedding_cache_enabled: bool = True
    embedding_cache_max_entries: int = 4096
    embedding_cache_ttl_seconds: int = 86400
    retrieval_cache_enabled: bool = True
    retrieval_cache_max_entries: int = 512
    retrieval_cache_ttl_seconds: int = 300

    # Ingestion
    myntra_play_store_app_id: str = "com.myntra.android"
    research_excel_path: str = "Myntra Wishlist.xlsx"
    # Additional survey workbook(s), comma-separated. Combined with research_excel_path.
    research_excel_secondary_paths: str = "Your Wishlist Habits (Responses).xlsx"
    research_interview_docx: str = "All file.docx"
    play_store_review_limit: int = 200
    chunk_size: int = 512
    chunk_overlap: int = 64
    scraped_json_path: str = "data/scraped_corpus.json"
    insights_json_path: str = "data/insights.json"
    feedback_json_path: str = "data/insight_feedback.json"
    use_json_fallback: bool = True

    # Phase 7 — multi-source scale-out
    default_ingestion_sources: str = "research,play_store,reddit,youtube,product_review,social"
    reddit_search_query: str = "myntra wishlist"
    reddit_fetch_limit: int = 25
    reddit_live_fetch_enabled: bool = False
    apify_api_token: str | None = Field(
        default=None,
        validation_alias=AliasChoices("APIFY_API_TOKEN", "Apify_API_TOKEN", "apify_api_token"),
    )
    apify_reddit_actor: str = "trudax/reddit-scraper-lite"
    youtube_search_query: str = "myntra wishlist shopping"
    youtube_fetch_limit: int = 20
    youtube_api_key: str | None = None
    youtube_live_fetch_enabled: bool = False
    product_review_export_path: str = "data/seeds/product_review.json"
    social_export_path: str = "data/seeds/social.json"
    source_refresh_research_hours: int = 168
    source_refresh_play_store_hours: int = 24
    source_refresh_reddit_hours: int = 12
    source_refresh_youtube_hours: int = 24
    source_refresh_product_review_hours: int = 72
    source_refresh_social_hours: int = 12
    vector_backend: str = "pgvector"
    qdrant_url: str = "http://127.0.0.1:6333"
    qdrant_collection: str = "wishlist_chunks"
    recompute_analytics_on_refresh: bool = True

    # Phase 8 — internal data + ground-truth metric
    internal_events_path: str = "data/seeds/internal_wishlist_events.json"
    conversion_window_days: int = 30
    streaming_ingestion_enabled: bool = False

    @property
    def source_refresh_interval_hours(self) -> dict[str, int]:
        return {
            "research": self.source_refresh_research_hours,
            "play_store": self.source_refresh_play_store_hours,
            "reddit": self.source_refresh_reddit_hours,
            "youtube": self.source_refresh_youtube_hours,
            "product_review": self.source_refresh_product_review_hours,
            "social": self.source_refresh_social_hours,
        }

    @property
    def default_source_list(self) -> list[str]:
        return [s.strip() for s in self.default_ingestion_sources.split(",") if s.strip()]

    @property
    def research_excel_path_list(self) -> list[str]:
        """Primary + secondary research Excel workbooks (deduped, existing paths preferred at runtime)."""
        paths: list[str] = []
        for raw in [self.research_excel_path, *self.research_excel_secondary_paths.split(",")]:
            path = raw.strip()
            if path and path not in paths:
                paths.append(path)
        return paths

    @property
    def sqlalchemy_url(self) -> str:
        """Return an explicit DATABASE_URL, or build one from POSTGRES_* parts."""
        if self.database_url:
            return self.database_url
        return (
            f"postgresql+psycopg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


@lru_cache
def get_settings() -> Settings:
    """Cached settings accessor so the `.env` is parsed only once."""
    return Settings()
