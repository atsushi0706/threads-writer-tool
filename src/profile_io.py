"""
プロファイル保存/読込モジュール — JSON DL/UL方式

ユーザーの「発信内容・過去の痛み・コンセプト・ペルソナ・CTA・トーン設定」を
JSONファイルとして手元に保存し、次回読み込んで一発復元できるようにする。
URL共有のStreamlitアプリで個別ユーザーごとの設定を保持する仕組み。
"""

import json
from typing import Any


PROFILE_KEYS = [
    "field",
    "author_identity",
    "author_pain",
    "concept",
    "persona",
    "cta_label",
    "cta_slot",
]


def export_profile(state: dict[str, Any]) -> str:
    """セッション状態からプロファイルJSONを作る。"""
    profile = {k: state.get(k, "") for k in PROFILE_KEYS}
    profile["_version"] = 1
    return json.dumps(profile, ensure_ascii=False, indent=2)


def import_profile(json_str: str) -> dict[str, Any]:
    """JSON文字列からプロファイルdictを復元。未知のキーは無視。"""
    data = json.loads(json_str)
    return {k: data.get(k, "") for k in PROFILE_KEYS if k in data}
