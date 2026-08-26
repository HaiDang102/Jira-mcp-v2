from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    jira_base_url: str
    jira_pat: str
    jira_project_key: str = "SP"

    jira_timeout: float = 30.0
    jira_connect_timeout: float = 10.0
    jira_max_retries: int = 3

    draft_store_path: str = "jira_mcp_drafts.db"

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )


settings = Settings()