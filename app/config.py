from __future__ import annotations

from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = PROJECT_ROOT / ".env"


class Settings(BaseSettings):
    jira_base_url: str
    jira_pat: str
    jira_project_key: str = "SP"

    jira_timeout: float = 30.0
    jira_connect_timeout: float = 10.0
    jira_max_retries: int = 3

    # SQLite / local state
    draft_store_path: str = "jira_mcp_drafts.db"

    # Jira custom-field mapping.
    # Fill these in .env after identifying the real field IDs on your Jira.
    #
    # Example:
    # JIRA_START_DATE_FIELD_ID=customfield_12345
    # JIRA_EPIC_LINK_FIELD_ID=customfield_10008
    jira_start_date_field_id: str | None = None
    jira_epic_link_field_id: str | None = None

    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @field_validator("draft_store_path")
    @classmethod
    def resolve_draft_store_path(cls, value: str) -> str:
        path = Path(value)
        if not path.is_absolute():
            path = PROJECT_ROOT / path
        return str(path)


settings = Settings()
