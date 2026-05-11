"""regenerate_single_post の revision_request が反映されるか実テスト。

ステップ:
1. 通常生成で5投稿生成
2. 朝枠を「3つの具体的な修正指示」を与えて再生成
3. 旧版 vs 新版を並べて表示
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.generator import generate_5posts, regenerate_single_post


PERSONA = (
    "30代後半の女性ヒーラー。資格は4つ持っている。"
    "クライアントから感謝されると嬉しいけど、セッション料を提示する瞬間に"
    "喉が詰まって『今回は特別に半額で』と勝手に値下げしてしまう。"
)
CONCEPT = PERSONA
FIELD = "ヒーリング・コーチング"


REVISION_TESTS = [
    {
        "label": "「メンタルブロック」という言葉を使わないで",
        "request": "「メンタルブロック」という言葉を絶対に使わないでください。同じ意味を別の日常語で表現してください。",
    },
    {
        "label": "もっと短く・1文40字以内厳守",
        "request": "hook全体を80字以内に短くしてください。1文も必ず40字以内に収めてください。読点で文を区切ること。",
    },
    {
        "label": "母親との具体的な記憶を入れて",
        "request": "本文の中盤に、ターゲットが幼少期に母親から言われた具体的なセリフ(『○○』という形式)を1つ入れてください。",
    },
]


def trim(s, n=140):
    s = (s or "").replace("\n", " / ")
    return s if len(s) <= n else s[:n] + "..."


def main():
    api_key = os.environ.get("GOOGLE_AI_KEY") or os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("ERROR: set GOOGLE_AI_KEY or GEMINI_API_KEY")
        sys.exit(1)

    print("=" * 70)
    print("STEP 1: 通常生成で5投稿生成中...")
    print("=" * 70)
    posts_result = generate_5posts(
        concept=CONCEPT,
        persona=PERSONA,
        field=FIELD,
        research={},
        tone_aggressive=30,
        tone_blunt=False,
        api_key=api_key,
        author_identity="",
        author_pain="",
        cta_label="",
        cta_slot="夜",
    )

    posts = posts_result.get("posts", [])
    morning = next((p for p in posts if p.get("slot") == "朝"), None)
    if not morning:
        print("ERROR: 朝枠が生成されませんでした")
        sys.exit(1)

    print("\n[朝枠 — 旧版]")
    print(f"  hook: {trim(morning.get('hook'), 250)}")
    print(f"  body: {trim(morning.get('body'), 250)}")

    # 各修正指示で1個ずつ再生成
    for i, test in enumerate(REVISION_TESTS, 1):
        print("\n" + "=" * 70)
        print(f"STEP 2.{i}: 修正指示 = 「{test['label']}」")
        print("=" * 70)

        new_post = regenerate_single_post(
            slot="朝",
            concept=CONCEPT,
            persona=PERSONA,
            field=FIELD,
            research={},
            shared_context=posts_result,
            tone_aggressive=30,
            tone_blunt=False,
            api_key=api_key,
            author_identity="",
            author_pain="",
            cta_label="",
            revision_request=test["request"],
            previous_post=morning,
        )

        print("\n[新版]")
        print(f"  hook: {trim(new_post.get('hook'), 250)}")
        print(f"  body: {trim(new_post.get('body'), 250)}")

        # 簡易チェック
        full = (new_post.get("hook", "") + new_post.get("body", ""))
        if i == 1:
            ok = "メンタルブロック" not in full and "ブロック" not in full
            print(f"\n  ✓ チェック [メンタルブロック不使用] = {'OK' if ok else 'NG (まだ含まれる)'}")
        elif i == 2:
            hook_len = len(new_post.get("hook", ""))
            ok = hook_len <= 100  # 80字目標 + 20字余裕
            print(f"\n  ✓ チェック [hook短縮] = {'OK' if ok else 'NG'} (実測: {hook_len}字)")
        elif i == 3:
            ok = "母" in full and ("「" in full and "」" in full)
            print(f"\n  ✓ チェック [母親セリフあり] = {'OK' if ok else 'NG'}")

    out = ROOT / "previews" / "revision_test.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps({
        "original_morning": morning,
        "tests": [{"request": t["request"]} for t in REVISION_TESTS],
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n✓ saved: {out}")


if __name__ == "__main__":
    main()
