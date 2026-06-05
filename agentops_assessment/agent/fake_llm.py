from __future__ import annotations

import hashlib


class FakeLLM:
    """确定性的 LLM 替身。

    候选人不需要为本测评准备外部 API Key。凡是需要稳定模型响应或
    token 估算的地方，都可以使用这个类。
    """
    _global_tokens: int = 0

    @classmethod
    def reset_tokens(cls) -> None:
        cls._global_tokens = 0

    @classmethod
    def get_global_tokens(cls) -> int:
        return cls._global_tokens

    def complete(self, prompt: str) -> dict:
        digest = hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:12]
        p_tokens = max(1, len(prompt.split()))
        c_tokens = 24
        FakeLLM._global_tokens += p_tokens + c_tokens
        return {
            "text": f"fake-llm-response:{digest}",
            "prompt_tokens": p_tokens,
            "completion_tokens": c_tokens,
        }
