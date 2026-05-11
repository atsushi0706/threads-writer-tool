"""ナレッジ作り直し後の hook 品質検証スクリプト。

6分野でターゲット別の hook を生成し、JSONで一気に出す。
権威の3層(Tier 1/2/3)が分野に応じて自然に選ばれるか、
禁止フレーズが入ってないかを目視確認するため。
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from google import genai
from google.genai import types

from src.generator import load_knowledge


TARGETS = [
    {
        "field": "ビジネス・経営",
        "persona": "30代で起業した一人社長。サービスは作れたけど集客で詰まっている。SNSで毎日発信してるのにフォロワーが増えず、月末の銀行口座を見るたびに胃がキュッとなる。『マーケティング学ばなきゃ』と本を買うけど、結局3章で止まる。",
    },
    {
        "field": "スピリチュアル",
        "persona": "40代女性。ヨガ・瞑想を10年続けている。『今ここ』を頭では理解しているのに、夜になると過去の出来事を思い出して眠れない。スピリチュアル系の本を読むほど『まだ私は何も悟っていない』と感じる。",
    },
    {
        "field": "心理学・カウンセリング",
        "persona": "心理学を学ぶ大学院生。クライアントワーク始めたばかり。セッション中は集中できるのに、終わった瞬間『あの介入であってたかな』と数時間悩む。指導教員にスーパービジョンを受けるのが怖い。",
    },
    {
        "field": "ヒーリング・コーチング",
        "persona": "30代後半の女性ヒーラー。資格は4つ持っている。クライアントから感謝されると嬉しいけど、セッション料を提示する瞬間に喉が詰まって『今回は特別に半額で』と勝手に値下げしてしまう。",
    },
    {
        "field": "育児・子育て",
        "persona": "4歳の息子を育てるワーママ(34歳)。朝の保育園準備で『靴下履かない!』と床に転がる息子に、出社時間が迫る焦りで怒鳴ってしまう。寝顔を見て『またやっちゃった』と毎晩反省する。",
    },
    {
        "field": "料理・食",
        "persona": "料理初心者の20代女性。レシピ通りに作ってるはずなのに、味が決まらない。SNSで見る料理上手な人と自分の差が分からず、『センスがないのかも』と料理が億劫になってきた。",
    },
]

HOOK_GEN_PROMPT_TEMPLATE = """あなたはThreadsコールドトラフィック向けのトッププロコピーライターです。
以下のターゲット向けに、Threadsの **hook(冒頭2〜5行・80〜180字程度) を3パターン** 生成してください。

【★最優先 hook設計テンプレート】
{hook_template}

【★最優先 コピーライティング原則(ダメvs良い)】
{copy_principles}

---

【今回のターゲット】
分野: {field}

ターゲット(何に悩んでいる、どんな人?):
{persona}

---

【生成指示】
- 3パターンの hook を生成。それぞれ違う型を使うこと:
  1. 型A(権威の暴露構文 / Tier 1人物×著作)
  2. 型B(観察→反証→問いかけ構文 / Tier 3 業界用語)
  3. 型C(概念逆説構文 / Tier 3 業界用語)

- 各 hook は **80〜180字以内**
- ターゲットの分野・業界に合った権威/業界用語を選ぶ(他分野のものを混ぜない)
- ターゲットが実際に使う場面・セリフを必ず入れる
- 禁止フレーズ(目覚めます / 内なる○○ / 受け取り体質 / ○○してみませんか? 等)は絶対NG

【出力形式】純粋なJSON配列のみ:
[
  {{"type": "A", "authority_used": "使った権威(人物・著作 or 業界用語)", "hook": "本文"}},
  {{"type": "B", "authority_used": "...", "hook": "..."}},
  {{"type": "C", "authority_used": "...", "hook": "..."}}
]
"""


def generate_hooks(client, field: str, persona: str, knowledge: dict) -> list:
    prompt = HOOK_GEN_PROMPT_TEMPLATE.format(
        hook_template=knowledge.get("hook_template", ""),
        copy_principles=knowledge.get("copywriting_principles", ""),
        field=field,
        persona=persona,
    )

    resp = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=0.95,
            max_output_tokens=4096,
            response_mime_type="application/json",
            thinking_config=types.ThinkingConfig(thinking_budget=0),
        ),
    )
    text = (resp.text or "").strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        import re
        m = re.search(r"\[.*\]", text, re.DOTALL)
        if m:
            return json.loads(m.group(0))
        raise


def main():
    api_key = os.environ.get("GOOGLE_AI_KEY") or os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("ERROR: set GOOGLE_AI_KEY or GEMINI_API_KEY")
        sys.exit(1)

    client = genai.Client(api_key=api_key)
    knowledge = load_knowledge()
    print(f"loaded knowledge keys: {list(knowledge.keys())}")

    out = {}
    for t in TARGETS:
        field = t["field"]
        print(f"\n=== generating: {field} ===")
        try:
            hooks = generate_hooks(client, field, t["persona"], knowledge)
            out[field] = {
                "persona": t["persona"],
                "hooks": hooks,
            }
            for h in hooks:
                print(f"  [{h.get('type')}] authority={h.get('authority_used')}")
                print(f"      {(h.get('hook') or '')[:120]}")
        except Exception as e:
            print(f"  ERROR: {type(e).__name__}: {e}")
            out[field] = {"persona": t["persona"], "error": str(e)}

    out_path = ROOT / "previews" / "hook_verification.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n✓ saved: {out_path}")


if __name__ == "__main__":
    main()
