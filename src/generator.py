"""
Threads 5投稿一括生成 — Gemini 2.5 Flash + ONE HACK (H/A/C/E/K)

1日のテーマから朝/午前/昼/午後/夜の5投稿を1コールで生成する。
- 各投稿は500字以内
- 各投稿は冒頭フック必須（独立して読まれるため）
- 5投稿全体でRule of One（ワン・ターゲット/アイデア/エモーション/ミステリー/アクション）を貫く
- 各投稿に design_reason を含めて、なぜこのhook/構成かを学習用に記録
"""

import json
from pathlib import Path

from google import genai
from google.genai import types

KNOWLEDGE_DIR = Path(__file__).parent.parent / "knowledge"


SLOT_DEFINITIONS = [
    {
        "slot": "朝",
        "time": "8:00",
        "stage": "H",
        "stage_name": "Hook",
        "role": "矛盾・謎かけで指を止める",
        "guideline": "1〜2行目で『え、どういうこと？』と前のめりにさせる。権威+逆説を推奨。",
    },
    {
        "slot": "午前",
        "time": "11:00",
        "stage": "A",
        "stage_name": "Ask",
        "role": "責任のすり替え・構造への問い",
        "guideline": "『あなたが悪いんじゃない、構造の問題』と安心させる。共通の敵を設定。",
    },
    {
        "slot": "昼",
        "time": "12:00",
        "stage": "C",
        "stage_name": "Core",
        "role": "アハ体験・ワン・キーワード提示",
        "guideline": "ワン・キーワード（新事実）1つを提示し、比喩で直感化。比喩はコアではなく伝達手段。",
    },
    {
        "slot": "午後",
        "time": "17:00",
        "stage": "E",
        "stage_name": "Echo",
        "role": "再共感・別角度の言い直し",
        "guideline": "朝〜昼の核心を別角度・別比喩で言い直す。意識の切り替えを具体的に提示。同じ言葉の繰り返しNG。",
    },
    {
        "slot": "夜",
        "time": "21:00",
        "stage": "K",
        "stage_name": "Key",
        "role": "誘導したいこと（問いかけ／プロフィール／小さな行動／次への引き）",
        "guideline": "投稿の目的に応じて誘導を選ぶ。CTAを入れるならここが最有力。",
    },
]


def load_knowledge() -> dict[str, str]:
    knowledge = {}
    for f in KNOWLEDGE_DIR.glob("*.md"):
        content = f.read_text(encoding="utf-8").strip()
        if content:
            knowledge[f.stem] = content
    return knowledge


_POSTS_SCHEMA = {
    "type": "object",
    "properties": {
        "shared_one_target": {"type": "string"},
        "shared_one_idea": {"type": "string"},
        "shared_one_emotion": {"type": "string"},
        "shared_one_mystery": {"type": "string"},
        "shared_one_action": {"type": "string"},
        "posts": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "slot": {"type": "string"},
                    "time": {"type": "string"},
                    "stage": {"type": "string"},
                    "stage_name": {"type": "string"},
                    "hook": {"type": "string"},
                    "body": {"type": "string"},
                    "char_count": {"type": "integer"},
                    "has_cta": {"type": "boolean"},
                    "authority_used": {"type": "string"},
                    "core_keyword": {"type": "string"},
                    "core_metaphor": {"type": "string"},
                    "key_direction": {"type": "string"},
                    "design_reason": {"type": "string"},
                },
                "required": [
                    "slot",
                    "stage",
                    "hook",
                    "body",
                    "char_count",
                    "has_cta",
                    "design_reason",
                ],
            },
        },
    },
    "required": [
        "shared_one_target",
        "shared_one_idea",
        "shared_one_emotion",
        "shared_one_mystery",
        "shared_one_action",
        "posts",
    ],
}


def _build_tone_instruction(tone_aggressive: int, tone_blunt: bool) -> str:
    if tone_aggressive <= 25:
        aggr = "とても優しく包み込むようなトーンで書いてください。読者を責めず、寄り添い、温かく語りかけます。"
    elif tone_aggressive <= 50:
        aggr = "基本的に優しいトーンですが、核心部分では少し踏み込んだ表現を使います。"
    elif tone_aggressive <= 75:
        aggr = "読者の心に刺さる強めの表現を適度に使います。ただし攻撃的にはならず、愛のある厳しさです。"
    else:
        aggr = "読者の常識を揺さぶる挑発的なフックを使います。ただし人格攻撃は絶対にしません。構造や常識への挑戦です。"

    if tone_blunt:
        blunt = "伝えたいことはグサッとストレートに言い切ります。遠回しにせず、核心を突く一文を必ず入れてください。"
    else:
        blunt = "伝えたいことは比喩やストーリーで柔らかく包んで伝えます。直接的な表現は避け、読者が自分で気づくように導きます。"

    return f"【トーン指定】\n{aggr}\n{blunt}\n"


def generate_5posts(
    concept: str,
    persona: str,
    field: str,
    research: dict,
    tone_aggressive: int = 30,
    tone_blunt: bool = False,
    writer_style: str = "",
    api_key: str = "",
    author_identity: str = "",
    author_pain: str = "",
    cta_label: str = "",
    cta_slot: str = "夜",
) -> dict:
    """5投稿（H→A→C→E→K）を1コールで生成する。

    Args:
        concept: 1日のテーマ
        persona: ターゲット
        field: 分野（心理学・育児・健康・ビジネス・スピリチュアル・エッセイなど）
        research: リサーチ結果
        cta_label: CTA文言（空ならCTAなし）
        cta_slot: CTAを入れるスロット名（朝/午前/昼/午後/夜）
    """
    client = genai.Client(api_key=api_key)
    knowledge = load_knowledge()
    one_hack = knowledge.get("ONE_HACK_model", "")

    evidence_text = ""
    for i, ev in enumerate(research.get("evidence", []), 1):
        evidence_text += f"{i}. {ev.get('title', '')} — {ev.get('summary', '')} (出典: {ev.get('source', '不明')})\n"

    expert_text = ""
    for eq in research.get("expert_quotes", []):
        expert_text += f"- {eq.get('expert', '')}: 「{eq.get('quote', '')}」({eq.get('context', '')})\n"

    tone_instruction = _build_tone_instruction(tone_aggressive, tone_blunt)
    style_instruction = (
        f"【参考にする文体】\n{writer_style}のような文体で書く。\n" if writer_style else ""
    )

    author_instruction = ""
    if author_identity or author_pain:
        author_instruction = f"""【★著者プロフィール — 全投稿に反映】
- 発信内容: {author_identity or "（未入力）"}
- 過去の痛み: {author_pain or "（未入力）"}

★著者の視点から書くこと。
★著者の痛みをペルソナの痛みと重ねる箇所を1〜2投稿に入れる。
★自己アピールは禁止。自然に織り込む。
"""

    cta_instruction = ""
    if cta_label:
        cta_instruction = f"""【★CTA挿入指示】
- 「{cta_slot}」スロットに**だけ**以下のCTAを自然に挿入する：
  「{cta_label}」
- 他の4投稿にはCTAを入れない（has_cta=false）
- CTAを入れる投稿の has_cta は true にする
- 押し売り感を出さず、本文の流れに馴染ませる
- 外部URLは入れない（プロフィール経由の前提）
"""

    slots_text = "\n".join(
        f"- {s['slot']}（{s['time']}）= {s['stage']} {s['stage_name']}：{s['role']}\n  方針: {s['guideline']}"
        for s in SLOT_DEFINITIONS
    )

    system_prompt = f"""あなたはThreadsコールドトラフィック向けのトッププロコピーライターです。
1日のテーマから朝/午前/昼/午後/夜の5投稿を一括生成します。

【ONE HACKモデル — このルールを厳守】
{one_hack}

{tone_instruction}
{style_instruction}
{author_instruction}
{cta_instruction}

【5スロットの割り当て】
{slots_text}

【★最重要 読みやすさルール (これを守らないと全部ボツ) ★】
- **中学生でもスッと読めるレベル**で書く
- **1文は短く**(原則40字以内)。長文・倒置・体言止めの連発禁止
- **抽象概念語は禁止**:
  例: 「自己価値」「内なる安全性」「健全な循環」「目に見えない不安」「価値を受け取るという行為」
  → 全部 **日常語** に翻訳すること
  例NG → 例OK: 「自己価値が低い」 → 「『私なんて…』って思ってしまう」
- **論文調・お経調の語尾禁止**: 「〜のです」「〜こそが」「〜を促進しつつ」「〜という構造自体に問いかける」 等
- **長い文学的比喩は禁止**:
  ×「森の中で旅人に食料と地図を分け与える賢者のよう。旅人は無事に森を抜けた後…」
  → 比喩を入れるなら **1〜2行で完結する身近な例**(コンビニ・電車・LINE 等の生活場面)
- **「〜することが大切です」「必要があります」みたいな教科書フレーズは禁止**

【★最重要 共感ファースト ★】
- ターゲットの **具体的な1日の場面** を本文の中に必ず1個は入れる
  例: 「Zoomを切った後の沈黙」「LINEの『お返事まだですか』通知」「3歳の娘が玄関で靴下を投げる朝」
- ターゲットが **頭の中で実際つぶやいている言葉** をそのまま書く
  例:「『また値下げしちゃった…』」「『あの人みたいになりたいけど無理かも』」
- 「あなたは…」と直接呼びかける
- 「私も同じだった」「分かる」と感じてもらえる温度感

【絶対ルール (構造)】
1. 各投稿は500字以内(hook+body合計)。超過厳禁
2. 各投稿は冒頭フック必須(独立して読まれるため)
3. hook の構造:
   - 朝(H): ターゲットの**ある1日のリアルな場面**から入るのが基本。権威引用は使ってもいいが**短く・分かりやすく**
   - 午前(A): 「あなたのせいじゃない」を**柔らかい言葉**で
   - 昼(C): 新事実を**驚くほど短い1文**で言い切る
   - 午後(E): 別角度の**具体例・あるある**で再提示
   - 夜(K): 問いかけ or 小さな1歩 or プロフィール誘導
4. 5投稿全体でRule of One貫通(ターゲット/アイデア/エモーション/ミステリー/アクションは全て1つ)
5. 海外権威・研究の引用は、**引用したらすぐ次の文で日常語に翻訳**する。引用しっぱなし禁止
   例: ×「アダム・グラントの研究が示すように、成功するギバーは戦略的なアプローチを取ります」
       ○「アダム・グラントって学者がね、面白いこと言ってる。
         『うまくいく人ほど、自分のことも大事にしてる』って」
6. 主語のねじれ厳禁
7. 自動投稿バレ表現禁止(「さっき見ました」等の時間表現/事実でないこと)
8. 解決策出し惜しみ禁止(「答えはnoteに」だけで終わるNG)
9. ペルソナの職業名・属性をそのまま本文に登場させる(汎用語に丸めない)
10. design_reason には『何を意識してこの文を書いたか』を一般コピーライティングの観点で4〜6文で詳しく書く。
    含めるべき要素:
    - 使ったフレームワークまたは原則 (PASONA / PASTOR / PASBECONA / AIDA / 4U / WIIFM / Rule of One / 1人に向けて書く / 具体性の力 / ベネフィット vs 機能 / 感情訴求と論理訴求 / 損失回避 / ヘッドライン原則 など。なるべく一般用語で説明する)
    - hook で読者の指を止めるために具体的に何を仕掛けたか
    - 本文で読者の感情をどう動かそうとしたか
    - なぜこの順序・この具体描写を選んだか
    - ターゲットの『どの心理段階』にこの投稿を当てているか
    ※読者がこの解説を読んでコピーライティングを学べるレベルの説明にする。
"""

    user_prompt = f"""以下の素材で5投稿（H→A→C→E→K）を生成してください。

【ターゲット — 何に悩んでいる、どんな人?】
{persona}

【参考: ターゲット概要(=同上)】
{concept}

【分野】
{field}

【リサーチで見つかった素材】
{evidence_text or "（リサーチ未実施／一般知識から組み立てる）"}

【専門家・著名人・概念の知見】
{expert_text or "（同上）"}

【ONE HACK要素のヒント】
- ONE idea: {research.get('suggested_one_idea', concept)}
- ONE emotion: {research.get('suggested_one_emotion', '気づき')}
- ONE story: {research.get('suggested_one_story', '')}
- ONE action: {research.get('suggested_one_action', '今日できる小さな行動を1つ')}
- Key insight: {research.get('key_insight', '')}

【出力】
shared_one_target/idea/emotion/mystery/action と、5投稿（朝→午前→昼→午後→夜）を出力。
各投稿には:
- slot, time, stage, stage_name
- hook（冒頭フック・1〜2行）
- body（hook以降の本文）
- char_count（hook+bodyの合計文字数）
- has_cta（CTAを入れたか）
- authority_used（hookで使った権威：誰の言葉/どの研究/どの概念）
- core_keyword（C/Eスロットなら新事実キーワード、それ以外は空欄可）
- core_metaphor（C/Eスロットで使った比喩、それ以外は空欄可）
- key_direction（Kスロットで何を誘導したか：問いかけ/プロフィール/小さな行動/次への引き、それ以外は空欄可）
- design_reason（なぜこの構成にしたかの2〜3文の解説）
"""

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=system_prompt + "\n\n" + user_prompt,
        config=types.GenerateContentConfig(
            temperature=0.85,
            max_output_tokens=8192,
            response_mime_type="application/json",
            response_schema=_POSTS_SCHEMA,
            thinking_config=types.ThinkingConfig(thinking_budget=0),
        ),
    )

    text = (response.text or "").strip()
    if not text:
        finish_reason = ""
        if response.candidates:
            finish_reason = str(response.candidates[0].finish_reason)
        raise ValueError(
            f"AIから空の応答が返りました（finish_reason={finish_reason}）。"
            "もう一度お試しください。続く場合はコンセプトを短くしてください。"
        )

    try:
        result = json.loads(text)
    except json.JSONDecodeError:
        result = json.loads(text, strict=False)

    for post in result.get("posts", []):
        full_text = (post.get("hook", "") + post.get("body", "")).strip()
        post["char_count"] = len(full_text)

    return result


def regenerate_single_post(
    slot: str,
    concept: str,
    persona: str,
    field: str,
    research: dict,
    shared_context: dict,
    tone_aggressive: int = 30,
    tone_blunt: bool = False,
    writer_style: str = "",
    api_key: str = "",
    author_identity: str = "",
    author_pain: str = "",
    cta_label: str = "",
) -> dict:
    """1スロットだけ再生成する（残り4投稿との整合性を保つ）。"""
    client = genai.Client(api_key=api_key)
    knowledge = load_knowledge()
    one_hack = knowledge.get("ONE_HACK_model", "")

    target_slot = next((s for s in SLOT_DEFINITIONS if s["slot"] == slot), None)
    if not target_slot:
        raise ValueError(f"不明なスロット: {slot}")

    tone_instruction = _build_tone_instruction(tone_aggressive, tone_blunt)
    style_instruction = (
        f"【参考にする文体】\n{writer_style}のような文体で書く。\n" if writer_style else ""
    )

    author_instruction = ""
    if author_identity or author_pain:
        author_instruction = f"""【著者プロフィール】
- 発信内容: {author_identity or "（未入力）"}
- 過去の痛み: {author_pain or "（未入力）"}
"""

    cta_instruction = ""
    if cta_label:
        cta_instruction = f"""【CTA】
このスロットがCTA挿入対象なら以下を自然に入れる：
「{cta_label}」
押し売り感は出さない。
"""

    single_schema = {
        "type": "object",
        "properties": {
            "slot": {"type": "string"},
            "stage": {"type": "string"},
            "stage_name": {"type": "string"},
            "hook": {"type": "string"},
            "body": {"type": "string"},
            "char_count": {"type": "integer"},
            "has_cta": {"type": "boolean"},
            "authority_used": {"type": "string"},
            "core_keyword": {"type": "string"},
            "core_metaphor": {"type": "string"},
            "key_direction": {"type": "string"},
            "design_reason": {"type": "string"},
        },
        "required": ["slot", "stage", "hook", "body", "char_count", "design_reason"],
    }

    prompt = f"""あなたはThreadsコールドトラフィック向けのプロコピーライターです。
すでに生成済みの5投稿のうち、{slot}枠（{target_slot['stage']} {target_slot['stage_name']}）だけを再生成します。
残り4投稿との整合性（同じターゲット・同じアイデア・同じミステリー）を保つこと。

【ONE HACKモデル】
{one_hack}

{tone_instruction}
{style_instruction}
{author_instruction}
{cta_instruction}

【コンセプト】{concept}
【ペルソナ】{persona}
【分野】{field}

【1日全体の Rule of One（既存の他4投稿と同じものを使う）】
- ワン・ターゲット: {shared_context.get('shared_one_target', '')}
- ワン・アイデア: {shared_context.get('shared_one_idea', '')}
- ワン・エモーション: {shared_context.get('shared_one_emotion', '')}
- ワン・ミステリー: {shared_context.get('shared_one_mystery', '')}
- ワン・アクション: {shared_context.get('shared_one_action', '')}

【このスロットの役割】
{target_slot['slot']}（{target_slot['time']}） = {target_slot['stage']} {target_slot['stage_name']}
役割: {target_slot['role']}
方針: {target_slot['guideline']}

【★読みやすさ&共感ルール (これを守らないとボツ) ★】
- 中学生でもスッと読めるレベル / 1文40字以内目安
- 抽象概念語禁止: 「自己価値」「内なる安全性」「健全な循環」等は日常語に翻訳
- 論文調禁止: 「〜のです」「〜こそが」「〜を促進しつつ」「〜という構造に問いかける」 等NG
- 長い文学的比喩禁止(賢者と旅人みたいな1段落使う比喩は厳禁)
- ターゲットの具体的な1日の場面を必ず1個は入れる(LINE・Zoom・通勤・玄関 等)
- 海外権威の引用は、引用直後に日常語で言い直す(引用しっぱなしNG)

【絶対ルール (構造)】
- 500字以内(hook+body合計)
- 冒頭フック必須
- 主語のねじれ厳禁
- 自動投稿バレ表現禁止
- design_reason には『何を意識してこの文を書いたか』を一般コピーライティング観点で4〜6文で詳しく書く。
  使ったフレームワーク/原則(PASONA・PASTOR・PASBECONA・AIDA・4U・WIIFM・Rule of One・1人に向けて書く・具体性・ベネフィット vs 機能・感情×論理・ヘッドライン原則 等)を一般用語で説明し、
  hook で何を仕掛け、本文でどう感情を動かし、なぜこの具体描写と順序を選んだかを学習用に書く。
"""

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=0.9,
            max_output_tokens=4096,
            response_mime_type="application/json",
            response_schema=single_schema,
            thinking_config=types.ThinkingConfig(thinking_budget=0),
        ),
    )

    text = (response.text or "").strip()
    if not text:
        raise ValueError("AIから空の応答が返りました。もう一度お試しください。")

    post = json.loads(text, strict=False)
    full_text = (post.get("hook", "") + post.get("body", "")).strip()
    post["char_count"] = len(full_text)
    return post
