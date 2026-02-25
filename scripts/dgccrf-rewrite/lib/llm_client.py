"""Client LLM OpenAI-compatible avec rate limiting et retries."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field

from openai import (
    APIConnectionError,
    APITimeoutError,
    AuthenticationError,
    BadRequestError,
    OpenAI,
    RateLimitError,
)

log = logging.getLogger(__name__)


@dataclass
class LLMResponse:
    content: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    duration_seconds: float


@dataclass
class LLMClient:
    """Rate-limited, retry-capable LLM client for OpenAI-compatible APIs."""

    endpoint: str
    api_key: str
    model: str
    temperature: float = 0.3
    timeout: int = 120
    rate_limit_rpm: int = 30
    retry_count: int = 3
    retry_delay: int = 5

    _client: OpenAI = field(init=False, repr=False)
    _last_call_time: float = field(init=False, default=0)
    _min_interval: float = field(init=False)

    def __post_init__(self):
        self._client = OpenAI(
            base_url=self.endpoint,
            api_key=self.api_key,
            timeout=self.timeout,
        )
        self._min_interval = 60.0 / self.rate_limit_rpm if self.rate_limit_rpm > 0 else 0

    def _rate_limit_wait(self):
        if self._min_interval <= 0:
            return
        elapsed = time.time() - self._last_call_time
        if elapsed < self._min_interval:
            time.sleep(self._min_interval - elapsed)

    def chat(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 4000,
    ) -> LLMResponse:
        """Send a chat completion request with retry logic."""
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        last_error = None
        for attempt in range(self.retry_count):
            self._rate_limit_wait()
            t0 = time.time()

            try:
                response = self._client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=self.temperature,
                    max_tokens=max_tokens,
                )
                self._last_call_time = time.time()
                duration = time.time() - t0

                content = response.choices[0].message.content or ""
                usage = response.usage

                return LLMResponse(
                    content=content,
                    model=response.model or self.model,
                    prompt_tokens=usage.prompt_tokens if usage else 0,
                    completion_tokens=usage.completion_tokens if usage else 0,
                    total_tokens=usage.total_tokens if usage else 0,
                    duration_seconds=round(duration, 2),
                )

            except (AuthenticationError, BadRequestError):
                # No retry for auth or request errors
                raise

            except (RateLimitError, APITimeoutError, APIConnectionError) as e:
                last_error = e
                delay = self.retry_delay * (2 ** attempt)
                log.warning(f"Attempt {attempt + 1}/{self.retry_count} failed: {e}. Retrying in {delay}s...")
                time.sleep(delay)

        raise last_error or RuntimeError("LLM call failed after retries")

    def chat_dry_run(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 4000,
    ) -> dict:
        """Return the request that would be sent, without calling the API."""
        return {
            "model": self.model,
            "max_tokens": max_tokens,
            "temperature": self.temperature,
            "system_chars": len(system_prompt),
            "user_chars": len(user_prompt),
            "estimated_tokens": (len(system_prompt) + len(user_prompt)) // 4,
            "system_prompt_preview": system_prompt[:500] + "..." if len(system_prompt) > 500 else system_prompt,
            "user_prompt_preview": user_prompt[:2000] + "..." if len(user_prompt) > 2000 else user_prompt,
        }
