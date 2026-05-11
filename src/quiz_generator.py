"""
コピーライティング学習クイズ生成モジュール (一般コピーライティング版)

- 5問構成: 固定3問 (quiz_pool.json) + AI生成2問 (生成された5投稿に基づく)
- 出題範囲: PASONA / PASTOR / PASBECONA などのフレームワーク+
  一般原則 (4U, AIDA, WIIFM, 具体性, ベネフィット vs 機能, ヘッドラインの原則, 感情訴求 など)
- 難易度: beginner / intermediate / advanced
"""

import json
import random
from pathlib import Path

from google import genai
from google.genai import types

from .llm_client import generate_with_fallback

QUIZ_POOL_PATH = Path(__file__).parent.parent / "data" / "quiz_pool.json"


def load_quiz_pool() -> dict:
    return json.loads(QUIZ_POOL_PATH.read_text(encoding="utf-8"))


_QUIZ_SCHEMA = {
    "type": "object",
    "properties": {
        "id": {"type": "string"},
        "category": {"type": "string"},
        "question": {"type": "string"},
        "options": {
            "type": "array",
            "items": {"type": "string"},
        },
        "answer_index": {"type": "integer"},
        "explanation": {"type": "string"},
    },
    "required": ["question", "options", "answer_index", "explanation"],
}


def pick_fixed_questions(difficulty: str, n: int = 3) -> list[dict]:
    """固定問題プールから指定難易度の問題をランダムにn問選ぶ。"""
    pool = load_quiz_pool()
    questions = pool.get(difficulty, [])
    if not questions:
        return []
    return random.sample(questions, min(n, len(questions)))


COPYWRITING_REFERENCE = """
# コピーライティングの主要フレームワークと原則

## 代表的なフレームワーク

### PASONA(神田昌典)
Problem (問題) → Affinity (親近感) → Solution (解決策) → Offer (提案) → Narrow (絞り込み) → Action (行動)

### PASTOR (John Forde / Ray Edwardsらが整理)
Person/Problem → Amplify (痛みの増幅) → Story / Solution → Transformation/Testimony (変化の証拠) → Offer → Response (行動)

### PASBECONA (PASONAの拡張版)
Problem → Affinity → Solution → Benefit (利益) → Evidence (証拠) → Contents (詳細) → Offer → Narrow → Action

### AIDA / AIDMA
Attention → Interest → Desire → Memory → Action
読者の心理段階の流れ。冒頭でAttention取れなければ次に進めない。

### QUEST
Qualify (見込み客の絞り込み) → Understand (共感) → Educate (教育) → Stimulate (動機付け) → Transition (行動)

## 普遍原則

### 4U (David Ogilvyらが整理)
- Useful (有益): 読者の役に立つか
- Urgent (緊急): 今読む理由があるか
- Unique (唯一): 他で見たことがあるか
- Ultra-specific (超具体): 抽象でなく具体か

### WIIFM ("What's In It For Me?")
読者の頭の中の常時稼働している問い。
すべての文章は「これを読むとあなたに何の得があるか」に答える形で書かれるべき。

### ベネフィット vs 機能 (Feature vs Benefit)
× 「このサプリには〇〇成分が含まれています」(機能)
○ 「朝、目覚めた瞬間に体が軽い」(ベネフィット = 顧客が得る体験)

### 1コピー1メッセージ (Rule of One)
1本の文章に「1ターゲット・1アイデア・1感情・1行動」だけ載せる。
詰め込みは焦点をぼやけさせる。

### 具体性の力 (Specificity)
「多くの人」より「3歳の長女を育てる32歳のフリーランスデザイナー」。
抽象は流される、具体は刺さる。

### 感情訴求と論理訴求 (Emotion + Logic)
人は感情で買い、論理で正当化する。
感情でフックし、論理で納得させ、最後に感情で背中を押す。

### ヘッドラインの原則 (David Ogilvy)
広告の80%はヘッドラインで決まる。
ヘッドラインで読者の指を止められなければ、本文は読まれない。

### バンドワゴン / ソーシャルプルーフ (Cialdini)
「みんながやっている」は強力。
ただし具体的な数字・固有名・実例で支えること。

### 損失回避 (Kahneman)
「得る喜び」より「失う恐怖」の方が2倍強い。
だが煽りすぎは離反を生む。短期成果と長期信頼のバランス。

### 1人に向けて書く ("One Reader Rule")
不特定多数に向けて書かない。1人を頭に浮かべ、その人にだけ手紙を書くつもりで書く。
"""


def generate_ai_questions(
    posts_result: dict,
    difficulty: str,
    api_key: str,
    n: int = 2,
) -> list[dict]:
    """生成された5投稿に基づきAI問題を n 問生成する。"""
    client = genai.Client(api_key=api_key)

    posts = posts_result.get("posts", [])
    posts_text = ""
    for p in posts:
        posts_text += f"\n【{p.get('slot')}({p.get('stage_name', '')})】\n"
        posts_text += f"hook: {p.get('hook', '')}\n"
        posts_text += f"body: {p.get('body', '')}\n"
        posts_text += f"design_reason: {p.get('design_reason', '')}\n"

    difficulty_guide = {
        "beginner": "コピーライティングの基本を問う(PASONA/AIDAの順序、ベネフィットvs機能、WIIFMなど)。選択肢で正誤が明確。",
        "intermediate": "応用判断を問う(なぜここで具体名を入れたか、なぜこの段階で痛みを増幅したか、どのフレームワークの何段階目か)。",
        "advanced": "本質を問う(感情と論理の順序、抽象と具体のバランス、1人に向けて書く意味など)。固有名詞は答えに必須にしない。",
    }

    prompt = f"""あなたはコピーライティング教育のプロです。
生成された5投稿に基づいて、一般コピーライティング学習クイズを{n}問作ってください。

# コピーライティング知識(出題範囲)
{COPYWRITING_REFERENCE}

# 今回生成された5投稿
{posts_text}

# 難易度: {difficulty}
{difficulty_guide.get(difficulty, difficulty_guide['intermediate'])}

# 出題ルール
- 各問は4択の単一選択
- 5投稿のいずれかに具体的に紐づける(例: 「朝の投稿のhookで使われている技法は?」)
- 不正解の3つは「一見正しそうだが微妙にズレている」選択肢にする
- explanation は「なぜそれが正解か」+「該当する一般原則(PASONA/4U/WIIFM等)」を2〜3文で
- カテゴリ名は短く(例: "PASONA構造" "ベネフィット" "ヘッドライン" "具体性")
- ONE HACK や独自フレーム名は使わない。一般コピーライティング知識のみ

# 出力
{n}問を JSON 配列で返す。各問は id/category/question/options(4)/answer_index(0-3)/explanation を持つ。
"""

    response = generate_with_fallback(
        client,
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=0.7,
            max_output_tokens=4096,
            response_mime_type="application/json",
            response_schema={
                "type": "array",
                "items": _QUIZ_SCHEMA,
            },
            thinking_config=types.ThinkingConfig(thinking_budget=0),
        ),
    )

    text = (response.text or "").strip()
    if not text:
        raise ValueError("AIから空の応答が返りました。")

    questions = json.loads(text, strict=False)
    if not isinstance(questions, list):
        questions = [questions]

    for i, q in enumerate(questions):
        if "id" not in q:
            q["id"] = f"AI-{difficulty[:3].upper()}-{i+1:03d}"
        if "category" not in q:
            q["category"] = "AI生成"
    return questions[:n]


def build_quiz_set(
    posts_result: dict,
    difficulty: str,
    api_key: str,
    use_ai: bool = True,
    total: int = 5,
) -> list[dict]:
    """ total 問のクイズセットを組み立てる。

    デフォルト: 固定3問 + AI生成2問 = 計5問
    AI失敗時は固定問題だけで埋める。
    """
    fixed_n = 3 if total >= 3 else total
    ai_n = total - fixed_n

    fixed = pick_fixed_questions(difficulty, n=fixed_n)

    if not use_ai or ai_n <= 0:
        # 固定だけで埋める(プールが足りなければ別難易度から補充)
        if len(fixed) < total:
            extra = pick_fixed_questions(difficulty, n=total)
            seen_ids = {q.get("id") for q in fixed}
            for q in extra:
                if q.get("id") not in seen_ids and len(fixed) < total:
                    fixed.append(q)
        return fixed[:total]

    try:
        ai_questions = generate_ai_questions(posts_result, difficulty, api_key, n=ai_n)
        return fixed + ai_questions
    except Exception:
        # AI失敗 → 固定だけで補充
        extra = pick_fixed_questions(difficulty, n=total)
        seen_ids = {q.get("id") for q in fixed}
        for q in extra:
            if q.get("id") not in seen_ids and len(fixed) < total:
                fixed.append(q)
        return fixed[:total]
