"""
リサーチモジュール — Gemini 2.5 Flash + Google Search Grounding

ジャンルによって検索方針を変える:
  - psychology: 海外論文・心理学者の知見（エビデンス重視）
  - spiritual: 古今東西の教え・実話エピソード・伝統
  - essay: 検索控えめ、人間の普遍的経験を重視
"""

import json
import re
from google import genai
from google.genai import types


GENRE_INSTRUCTIONS = {
    "psychology": {
        "label": "心理学・ビジネス系（エビデンス重視）",
        "search_policy": """- **英語で検索**して、海外の一次情報（英語の論文・学術サイト・研究者の記事）にアクセス
- 日本語の二次情報（まとめサイト、ブログ）は避ける
- 優先情報源: PubMed、Google Scholar、ResearchGate、Harvard/Stanford/Yale等の心理学部、APA、TED Talks
- 検索クエリは英語で専門用語を使う""",
        "evidence_type": "実在する研究・論文・心理学者の知見",
        "ng": "Google検索で確認できない論文・書籍を引用、著者名や出版年を推測で埋める",
    },
    "spiritual": {
        "label": "スピリチュアル・直感系（物語・未科学を扱う）",
        "search_policy": """- **2軸で集める**：①海外霊性指導者の非論理的智恵 ②それを科学的に再解釈した試み（疑似科学・未科学領域）
- ① 非論理側: エックハルト・トール、ラム・ダス、バイロン・ケイティ、ルーミー、老子、エマニュエル・スウェーデンボルグ、神話・民話、ヨガ哲学、禅、シャーマニズム、ホピ族・マヤ族の智恵
- ② 未科学・疑似科学側: 量子物理学と意識（"quantum consciousness"）、HeartMath研究所の心拍コヒーレンス、ジョー・ディスペンザの瞑想と神経可塑性、グレッグ・ブレイデン、ブルース・リプトン（細胞生物学とエピジェネティクス）、ノエティック・サイエンス研究所（IONS）、ニューロセオロジー、トランスパーソナル心理学（グロフ）、近年の臨死体験研究（NDE）、サイ現象研究
- 検索クエリ例: "quantum physics consciousness", "HeartMath coherence research", "Eckhart Tolle presence", "Joe Dispenza meditation neuroscience", "near death experience research", "noetic sciences IONS"
- 「物語性」と「擬似的でも論理的に語れる根拠」の両方を集める""",
        "evidence_type": "霊性指導者の言葉・物語、および未科学/疑似科学的に語られる研究",
        "ng": "完全に論文だけ集めること、または完全にスピリチュアルだけ集めること（両方欲しい）",
    },
    "essay": {
        "label": "エッセイ・日常系（個人視点重視）",
        "search_policy": """- 検索は最小限。普遍的な人間経験・日常の機微・人生哲学が分かれば十分
- 詩人・作家・哲学者の言葉、共感を呼ぶエピソード、文学からの引用
- 例: 村上春樹、ヘミングウェイ、ヴィクトール・フランクル、岡本太郎などの言葉
- 統計やエビデンスは要らない。情緒と気づきが大事""",
        "evidence_type": "詩人・作家・哲学者の名言、文学的なエピソード",
        "ng": "学術的になりすぎる、データを並べる、論理的に詰めすぎる",
    },
}


def research_topic(concept: str, persona: str, api_key: str, genre: str = "psychology") -> dict:
    """
    コンセプトに基づいてGoogle検索でリサーチを実行する。

    Args:
        genre: "psychology" / "spiritual" / "essay"
    """
    client = genai.Client(api_key=api_key)
    g = GENRE_INSTRUCTIONS.get(genre, GENRE_INSTRUCTIONS["psychology"])

    prompt = f"""あなたは優秀なリサーチャーです。Google検索で実際に調べて、以下のコンセプトに関する素材を集めてください。

【コンセプト】
{concept}

【届けたいペルソナ】
{persona}

【ジャンル】
{g["label"]}

【検索の方針】
{g["search_policy"]}

【リサーチ指示】
1. 実際にGoogle検索した結果から、3〜5個の素材を集める
2. **検索で実在を確認した{g["evidence_type"]}のみ**引用すること（絶対に捏造しない）
3. 出典URLを記録する
4. ペルソナが「なるほど！」と思える意外な視点や逆説を探す
5. このコンセプトで記事を書く場合のONE HACK要素を提案する

【絶対NG】
- {g["ng"]}
- 著者名や年を推測で埋めること
- 日本語のまとめサイトを一次情報として扱うこと

【出力形式】最後に以下のJSON形式のみを出力してください。他の説明文は不要。
```json
{{
    "evidence": [
        {{"title": "素材のタイトル", "summary": "日本語で要約（2-3文）", "source": "出典・著者・URL"}}
    ],
    "key_insight": "この記事の核となる洞察（日本語1文）",
    "suggested_one_idea": "伝えるべき1つのアイデア（日本語）",
    "suggested_one_emotion": "揺さぶるべき1つの感情（日本語）",
    "suggested_one_story": "使うべき比喩・ストーリー（日本語）",
    "suggested_one_action": "読者に促す1つの行動（日本語）",
    "expert_quotes": [
        {{"expert": "実在する人物の名前", "quote": "その人が実際に言った/書いた内容の日本語訳", "context": "どの文脈で使えるか"}}
    ]
}}
```
"""

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            tools=[types.Tool(google_search=types.GoogleSearch())],
            temperature=0.7,
        ),
    )

    raw = response.text.strip()

    json_match = re.search(r"```json\s*(\{.*?\})\s*```", raw, re.DOTALL)
    if json_match:
        json_str = json_match.group(1)
    else:
        json_match = re.search(r"(\{[\s\S]*\})", raw)
        if not json_match:
            raise ValueError(f"JSONが抽出できませんでした: {raw[:500]}")
        json_str = json_match.group(1)

    result = json.loads(json_str)

    sources = []
    if response.candidates and response.candidates[0].grounding_metadata:
        metadata = response.candidates[0].grounding_metadata
        if metadata.grounding_chunks:
            for chunk in metadata.grounding_chunks:
                if chunk.web:
                    sources.append({
                        "title": chunk.web.title or "",
                        "uri": chunk.web.uri or "",
                    })

    result["sources"] = sources
    result["genre"] = genre
    return result
