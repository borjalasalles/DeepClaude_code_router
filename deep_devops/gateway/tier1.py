"""
Tier-1 gateway — DeepSeek native API (China-hosted, cheapest).

Only reachable when the PII scanner + publicness classifier both clear the
query (design.md §3.3, §4.2).  The kill-switch env var DEEP_DEVOPS_DISABLE_PUBLIC_TIER=1
collapses tier 1 into tier 2 at the router level; this module is never called in that case.

Uses langchain-deepseek (ChatDeepSeek), the native provider — NOT langchain-openai
with a custom base_url.  See memory: deepseek: provider, not openai:.
"""
from __future__ import annotations

import os

from langchain_deepseek import ChatDeepSeek


_MODEL_DEFAULT = "deepseek-chat"  # DeepSeek V4 Flash alias


def build_tier1_client(
    model: str = _MODEL_DEFAULT,
    *,
    streaming: bool = True,
    temperature: float = 0.0,
) -> ChatDeepSeek:
    """Return a configured ChatDeepSeek instance for tier-1 calls.

    Reads DEEPSEEK_API_KEY from the environment (loaded by the caller via
    python-dotenv before this is constructed).  Raises if the key is absent
    so the failure is loud at startup, not silently at first inference call.
    """
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        raise RuntimeError(
            "DEEPSEEK_API_KEY is not set. "
            "Add it to .env or export it before launching deepagents."
        )
    return ChatDeepSeek(
        model=model,
        api_key=api_key,
        streaming=streaming,
        temperature=temperature,
    )
