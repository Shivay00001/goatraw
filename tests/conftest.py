"""Shared pytest fixtures for GoatRaw test suite."""
import pytest
import os

# Set test environment variables before any imports
os.environ.update({
    "SECRET_KEY":       "test-secret-key-for-testing-only",
    "DATABASE_URL":     "postgresql+asyncpg://test:test@localhost:5432/goatraw_test",
    "REDIS_URL":        "redis://localhost:6379/15",  # DB 15 = test DB
    "GROQ_API_KEY":     "test_groq_key",
    "OPENAI_API_KEY":   "test_openai_key",
    "TOGETHER_API_KEY": "test_together_key",
    "DEBUG":            "true",
})
