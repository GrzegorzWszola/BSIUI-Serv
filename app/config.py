"""Centralised environment configuration."""

import os
from pathlib import Path

from dotenv import load_dotenv

# The .env file can live in app/ or in the project root directory.
_base_dir = Path(__file__).resolve().parent
load_dotenv(_base_dir / ".env")
load_dotenv(_base_dir.parent / ".env")


def _required(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


SECRET_KEY: str = _required("SECRET_KEY")
ALGORITHM: str = _required("ALGORITHM")
ACCESS_TOKEN_EXPIRE_MINUTES: int = int(
    os.environ.get("ACCESS_TOKEN_EXPIRE_MINUTES", "30")
)
DATABASE_URL: str = os.environ.get("DATABASE_URL", "sqlite:///database.db")
