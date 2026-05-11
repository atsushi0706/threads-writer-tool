"""角度提案モジュール — Gemini 2.5 Flash

リサーチ結果とターゲットから「5つの違う角度」を提案する。
固定の3要素(コンセプト/ターゲット/経験)から、毎回違う切り口を出すための仕組み。
"""

from __future__ import annotations

import json
from pathlib import Path

from google import genai
from google.genai import types

from .llm_client import generate_with_fallback


_ANGLE_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "core_insight": {"type": "string"},
        "key_authority_hint": {"type": "string"},
        "target_pain_specific": {"type": "string"},
    },
    "required": ["title", "core_insight", "key_authority_hint", "target_pain_specific"],
}


def propose_angles(
    *,
    concept: str,
    persona: str,
    field: str,
    author_identity: str = "",
    author_pain: str = "",
    research: dict | None = None,
    api_key: str,
    n: int = 5,
) -> list[dict]:
    """ターゲットから違う角度を n 案提案する。

    各案は以下4要素:
    - title: 角度の名前(1行・15字以内)
    - core_insight: コア気づき(1文・40字以内)
    - key_authority_hint: body で使う権威ヒント(人物名/概念名/研究データ)
    - target_pain_specific: 痛みの瞬間(具体場面1つ)

    Returns:
        5案のリスト
    """
    research = research or {}

    evidence_text = ""
    for i, ev in enumerate(research.get("evidence", []), 1):
        evidence_text += f"{i}. {ev.get('title', '')} — {ev.get('summary', '')}\n"

    expert_text = ""
    for eq in research.get("expert_quotes", []):
        expert_text += f"- {eq.get('expert', '')}: 「{eq.get('quote', '')}」\n"

    prompt = f"""あなたはコピーライティングの戦略家です。
以下のターゲットから、Threads投稿の「角度」を{n}個提案してください。

【ターゲット — 何に悩んでいる、どんな人?】
{persona}

【コンセプト】
{concept}

【分野】
{field}

【著者プロフィール】
発信内容: {author_identity or "(未入力)"}
過去の痛み: {author_pain or "(未入力)"}

【リサーチで集まった素材】
{evidence_text or "(リサーチなし)"}

【専門家の言葉】
{expert_text or "(なし)"}

---

【★最重要 角度提案ルール ★】
1. **{n}個の角度は全て違う切り口**にしてください。重複NG。
2. 同じターゲットでも、入り方の角度を変える(例: お金側 / 完璧主義側 / 母親との関係側 / 完璧主義側 / セールス恐怖側)
3. **各角度で使う『権威ヒント』は別々の人物・概念**にしてください。同じ人物を使い回さない。
4. アダム・グラント / ブレネー・ブラウン みたいな「定番」だけに偏らず、分野に合った多様な権威を提案する。
5. 権威ヒントは、人物名+概念名/著作名 を簡潔に(例: 「ガボール・マテ / 共感疲労」「行動経済学 / 損失回避」「フランクル / 意味への意志」)。

【各角度の構造】
- title: 角度の名前(1行・15字以内・「お金のブロック側」のような分かりやすい言葉)
- core_insight: コア気づき(1文・40字以内・常識を覆す気づき)
- key_authority_hint: bodyで使う権威(人物名+概念名/著作名/研究)
- target_pain_specific: 痛みの瞬間(具体的場面1つ・「Zoomを切った後」「玄関で靴下を投げる朝」のように)

【出力】
{n}個の角度を JSON 配列で返してください。
"""

    client = genai.Client(api_key=api_key)
    response = generate_with_fallback(
        client,
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=0.95,
            max_output_tokens=4096,
            response_mime_type="application/json",
            response_schema={
                "type": "array",
                "items": _ANGLE_SCHEMA,
            },
            thinking_config=types.ThinkingConfig(thinking_budget=0),
        ),
    )

    text = (response.text or "").strip()
    if not text:
        raise ValueError("AIから空の応答が返りました。")

    angles = json.loads(text, strict=False)
    if not isinstance(angles, list):
        angles = [angles]
    return angles[:n]
