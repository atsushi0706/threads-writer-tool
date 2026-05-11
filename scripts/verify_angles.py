"""角度提案 → その角度で5投稿生成、までを6分野で一気に検証。

各分野で:
1. 角度を5案提案させる
2. 案1で5投稿生成
3. hookに人物名・専門用語が入ってないか確認
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.angle_proposer import propose_angles
from src.generator import generate_5posts


TARGETS = [
    {
        "field": "ビジネス・経営",
        "persona": "30代で起業した一人社長。サービスは作れたけど集客で詰まっている。月末の銀行口座を見るたびに胃がキュッとなる。",
        "author_identity": "元銀行員のキャリアコーチ",
        "author_pain": "銀行時代に過労で体を壊した",
    },
    {
        "field": "スピリチュアル",
        "persona": "40代女性。ヨガ・瞑想を10年続けている。『今ここ』を頭では理解しているのに、夜になると過去の出来事を思い出して眠れない。",
        "author_identity": "瞑想インストラクター",
        "author_pain": "自分も10年続けて『悟れない』と苦しんだ",
    },
    {
        "field": "心理学・カウンセリング",
        "persona": "心理学を学ぶ大学院生。クライアントワーク始めたばかり。セッションが終わった瞬間『あの介入であってたかな』と数時間悩む。",
        "author_identity": "現役カウンセラー",
        "author_pain": "新人の時に毎晩反芻して眠れなかった",
    },
    {
        "field": "ヒーリング・コーチング",
        "persona": "30代後半の女性ヒーラー。資格は4つ持っている。セッション料を提示する瞬間に喉が詰まって『今回は特別に半額で』と勝手に値下げしてしまう。",
        "author_identity": "元ヒーラー、現コーチ",
        "author_pain": "自分も5年間モニター価格から抜け出せなかった",
    },
    {
        "field": "育児・子育て",
        "persona": "4歳の息子を育てるワーママ(34歳)。朝の保育園準備で『靴下履かない!』と床に転がる息子に怒鳴ってしまう。",
        "author_identity": "育児セラピスト",
        "author_pain": "自分も長男の時に同じことを繰り返していた",
    },
    {
        "field": "料理・食",
        "persona": "料理初心者の20代女性。レシピ通りに作ってるはずなのに、味が決まらない。『センスがないのかも』と料理が億劫になってきた。",
        "author_identity": "料理研究家",
        "author_pain": "20代の時に同じ悩みで挫折寸前だった",
    },
]


def main():
    api_key = os.environ.get("GOOGLE_AI_KEY") or os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("ERROR: set GOOGLE_AI_KEY or GEMINI_API_KEY")
        sys.exit(1)

    out = {}
    for t in TARGETS:
        field = t["field"]
        print("\n" + "=" * 70)
        print(f"■ {field}")
        print("=" * 70)

        try:
            angles = propose_angles(
                concept=t["persona"],
                persona=t["persona"],
                field=field,
                author_identity=t["author_identity"],
                author_pain=t["author_pain"],
                research={},
                api_key=api_key,
                n=5,
            )
        except Exception as e:
            print(f"  角度提案ERROR: {type(e).__name__}: {e}")
            continue

        print("\n[5つの角度案]")
        for i, a in enumerate(angles, 1):
            print(f"  {i}. {a.get('title')}")
            print(f"     核: {a.get('core_insight')}")
            print(f"     権威: {a.get('key_authority_hint')}")
            print(f"     瞬間: {a.get('target_pain_specific')}")

        # 案1で5投稿生成
        chosen = angles[0]
        try:
            posts_result = generate_5posts(
                concept=t["persona"],
                persona=t["persona"],
                field=field,
                research={},
                api_key=api_key,
                author_identity=t["author_identity"],
                author_pain=t["author_pain"],
                cta_label="",
                cta_slot="夜",
                selected_angle=chosen,
            )
        except Exception as e:
            print(f"  5投稿生成ERROR: {type(e).__name__}: {e}")
            continue

        # 朝枠hook を抜粋
        morning = next((p for p in posts_result.get("posts", []) if p.get("slot") == "朝"), None)
        if morning:
            print(f"\n[案1『{chosen.get('title')}』で生成した朝枠 hook]")
            print(f"  {morning.get('hook')}")
            print(f"\n[body冒頭120字]")
            print(f"  {(morning.get('body') or '')[:120]}")

        out[field] = {
            "angles": angles,
            "chosen_title": chosen.get("title"),
            "morning": morning,
        }

    out_path = ROOT / "previews" / "angle_verification.json"
    out_path.parent.mkdir(exist_ok=True)
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n✓ saved: {out_path}")


if __name__ == "__main__":
    main()
