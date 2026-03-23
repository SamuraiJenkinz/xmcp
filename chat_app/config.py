"""Flask configuration loaded from environment variables."""

from __future__ import annotations

import os


class Config:
    """Flask configuration loaded from environment variables."""

    # Flask
    SECRET_KEY: str = os.environ.get("FLASK_SECRET_KEY", "dev-secret-change-in-prod")
    SESSION_TYPE: str = "filesystem"
    SESSION_FILE_DIR: str = os.environ.get("SESSION_FILE_DIR", "/tmp/flask-sessions")
    SESSION_PERMANENT: bool = False
    SESSION_USE_SIGNER: bool = True
    DATABASE: str = os.environ.get(
        "CHAT_DB_PATH",
        os.path.join(os.path.dirname(__file__), "..", "chat.db"),
    )

    # Azure AD / Entra ID
    AZURE_CLIENT_ID: str = os.environ.get("AZURE_CLIENT_ID", "")
    AZURE_CLIENT_SECRET: str = os.environ.get("AZURE_CLIENT_SECRET", "")
    AZURE_TENANT_ID: str = os.environ.get("AZURE_TENANT_ID", "")
    AZURE_AUTHORITY: str = f"https://login.microsoftonline.com/{AZURE_TENANT_ID}"

    # Azure OpenAI
    CHATGPT_ENDPOINT: str = os.environ.get("CHATGPT_ENDPOINT", "")
    AZURE_OPENAI_API_KEY: str = os.environ.get("AZURE_OPENAI_API_KEY", "")
    API_VERSION: str = os.environ.get("API_VERSION", "2023-05-15")
    OPENAI_MODEL: str = os.environ.get(
        "OPENAI_MODEL", "mmc-tech-gpt-4o-mini-128k-2024-07-18"
    )

    # Server
    HOST: str = os.environ.get("CHAT_HOST", "0.0.0.0")
    PORT: int = int(os.environ.get("CHAT_PORT", "5000"))

    @classmethod
    def update_from_secrets(cls, secrets: dict[str, str]) -> None:
        """Override config values from secrets dict (AWS Secrets Manager or .env)."""
        if secrets.get("FLASK_SECRET_KEY"):
            cls.SECRET_KEY = secrets["FLASK_SECRET_KEY"]
        if secrets.get("AZURE_CLIENT_SECRET"):
            cls.AZURE_CLIENT_SECRET = secrets["AZURE_CLIENT_SECRET"]
        if secrets.get("AZURE_OPENAI_API_KEY"):
            cls.AZURE_OPENAI_API_KEY = secrets["AZURE_OPENAI_API_KEY"]
        if secrets.get("AZURE_CLIENT_ID"):
            cls.AZURE_CLIENT_ID = secrets["AZURE_CLIENT_ID"]
        if secrets.get("AZURE_TENANT_ID"):
            cls.AZURE_TENANT_ID = secrets["AZURE_TENANT_ID"]
            cls.AZURE_AUTHORITY = (
                f"https://login.microsoftonline.com/{cls.AZURE_TENANT_ID}"
            )
        if secrets.get("CHATGPT_ENDPOINT"):
            cls.CHATGPT_ENDPOINT = secrets["CHATGPT_ENDPOINT"]
        if secrets.get("API_VERSION"):
            cls.API_VERSION = secrets["API_VERSION"]
        if secrets.get("OPENAI_MODEL"):
            cls.OPENAI_MODEL = secrets["OPENAI_MODEL"]
        if secrets.get("CHAT_HOST"):
            cls.HOST = secrets["CHAT_HOST"]
        if secrets.get("CHAT_PORT"):
            cls.PORT = int(secrets["CHAT_PORT"])
        if secrets.get("CHAT_DB_PATH"):
            cls.DATABASE = secrets["CHAT_DB_PATH"]
        if secrets.get("SESSION_FILE_DIR"):
            cls.SESSION_FILE_DIR = secrets["SESSION_FILE_DIR"]
