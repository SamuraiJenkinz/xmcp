"""Load secrets from AWS Secrets Manager with .env fallback for development."""

from __future__ import annotations

import json
import logging
import os

logger = logging.getLogger(__name__)

_SECRET_NAME = os.environ.get("AWS_SECRET_NAME", "/mmc/cts/exchange-mcp")
_AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")


def load_secrets() -> dict[str, str]:
    """Load secrets from AWS Secrets Manager; fall back to .env + env vars.

    In development, if boto3 is not configured or the secret doesn't exist,
    loads from python-dotenv .env file. Returns a dict of secret key-value pairs.
    """
    # Try AWS Secrets Manager first
    try:
        import boto3

        client = boto3.client("secretsmanager", region_name=_AWS_REGION)
        response = client.get_secret_value(SecretId=_SECRET_NAME)
        secrets = json.loads(response["SecretString"])
        logger.info("Loaded secrets from AWS Secrets Manager (%s)", _SECRET_NAME)
        return secrets
    except Exception as exc:
        logger.info(
            "AWS Secrets Manager unavailable (%s), falling back to env vars: %s",
            _SECRET_NAME,
            exc,
        )

    # Fallback: load .env file then return env vars
    try:
        from dotenv import load_dotenv

        load_dotenv()
        logger.info("Loaded .env file")
    except ImportError:
        pass

    return {
        "FLASK_SECRET_KEY": os.environ.get("FLASK_SECRET_KEY", ""),
        "AZURE_CLIENT_ID": os.environ.get("AZURE_CLIENT_ID", ""),
        "AZURE_CLIENT_SECRET": os.environ.get("AZURE_CLIENT_SECRET", ""),
        "AZURE_TENANT_ID": os.environ.get("AZURE_TENANT_ID", ""),
        "AZURE_OPENAI_API_KEY": os.environ.get("AZURE_OPENAI_API_KEY", ""),
    }
