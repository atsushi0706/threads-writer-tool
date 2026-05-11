"""Gemini モデル呼び出しの共通ヘルパー(フォールバック付き)。

無料枠の枯渇 (429) や 一時的なエラー (503) が起きた時に、
次のモデルにフォールバックして自動再試行する。

優先順位:
1. gemini-3.1-flash-lite  : 新世代(高速・無料枠大きい)
2. gemini-2.5-flash-lite  : 1世代前のlite
3. gemini-2.5-flash       : 品質高(無料枠は小さめ・250req/日と言われる)
4. gemini-flash-lite-latest: エイリアス保険
"""

from __future__ import annotations

import time
from typing import Any

from google.genai.errors import ClientError, ServerError


MODEL_FALLBACK_ORDER = [
    "gemini-3.1-flash-lite",
    "gemini-2.5-flash-lite",
    "gemini-2.5-flash",
    "gemini-flash-lite-latest",
]


def generate_with_fallback(
    client: Any,
    *,
    contents: Any,
    config: Any = None,
    max_retries: int = 1,
) -> Any:
    """モデルを順番に試して最初に成功したレスポンスを返す。

    - 429 (RESOURCE_EXHAUSTED) : 次モデルへ即フォールバック
    - 503 (UNAVAILABLE) : 短いsleep後に同モデルを再試行、それでもダメなら次モデル
    - その他のエラー : 即raise
    """
    last_err: Exception | None = None
    for model in MODEL_FALLBACK_ORDER:
        for attempt in range(max_retries + 1):
            try:
                kwargs = {"model": model, "contents": contents}
                if config is not None:
                    kwargs["config"] = config
                resp = client.models.generate_content(**kwargs)
                # 成功した場合、どのモデルで成功したかを応答に付与
                try:
                    setattr(resp, "_used_model", model)
                except Exception:
                    pass
                return resp
            except ClientError as e:
                last_err = e
                if getattr(e, "code", None) == 429:
                    break  # quota枯渇 → 次のモデルへ
                raise
            except ServerError as e:
                last_err = e
                code = getattr(e, "code", None)
                if code in (503, 504, 500):
                    if attempt < max_retries:
                        time.sleep(2)
                        continue
                    break  # 次モデルへ
                raise
            except Exception as e:
                last_err = e
                raise
    raise RuntimeError(
        f"全てのフォールバックモデルが失敗しました(無料枠枯渇の可能性)。"
        f"最後のエラー: {type(last_err).__name__}: {last_err}"
    )
