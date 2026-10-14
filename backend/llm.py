"""The language model every agent uses: gpt-6-luna, reached through the course's Portkey gateway.

The course requires gpt-6-luna for every agent and the course PORTKEY_API_KEY, which lives in
the course .env one folder up (a HW 5/.env also works). Both are enforced here: any other model
name, or a missing PORTKEY_API_KEY, stops the run before a request is sent.
"""

import os
from pathlib import Path

from dotenv import load_dotenv
from openai import AsyncOpenAI
from pydantic_ai.models.openai import OpenAIResponsesModel
from pydantic_ai.providers.openai import OpenAIProvider

HW_DIR = Path(__file__).resolve().parent.parent
MODEL = "gpt-6-luna"
PORTKEY_BASE_URL = "https://api.portkey.ai/v1"
MAX_RETRIES = 6        # the gateway sometimes answers 500/429; the client retries those with exponential backoff
REQUEST_TIMEOUT = 120  # seconds per model request


def gateway_model(name: str = MODEL) -> OpenAIResponsesModel:
    """gpt-6-luna on Portkey (which routes to Azure OpenAI), called through the Responses API.

    The Responses API is needed because Azure refuses tools + reasoning together on /chat/completions.
    """
    if name != MODEL:
        raise ValueError(f"Every agent must use {MODEL}, not {name!r}.")
    load_dotenv(HW_DIR / ".env")  # never overrides variables that are already set
    load_dotenv(HW_DIR.parent / ".env")
    key = os.getenv("PORTKEY_API_KEY")
    if not key:
        raise RuntimeError("Set PORTKEY_API_KEY in the course .env to run the agents.")
    client = AsyncOpenAI(base_url=PORTKEY_BASE_URL, api_key=key, max_retries=MAX_RETRIES, timeout=REQUEST_TIMEOUT)
    return OpenAIResponsesModel(MODEL, provider=OpenAIProvider(openai_client=client))
