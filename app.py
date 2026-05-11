"""
Threads 5投稿ライターツール — Streamlit UI

1日のテーマ → 5投稿（H→A→C→E→K）一括生成 → コピー → Threadsに貼り付け
リサーチ→5つの角度から1つ選択→その角度で5投稿を生成。
全てGemini Flash（無料枠）で動作。
"""

import json
import os

import streamlit as st
from dotenv import load_dotenv

from src.researcher import research_topic
from src.generator import generate_5posts, regenerate_single_post, SLOT_DEFINITIONS
from src.quiz_generator import build_quiz_set
from src.profile_io import export_profile, import_profile

load_dotenv()
DEFAULT_API_KEY = os.environ.get("GEMINI_API_KEY", "") or os.environ.get("GOOGLE_AI_KEY", "")

# --- ページ設定 ---
st.set_page_config(
    page_title="Threads 5投稿ライター",
    page_icon="🧵",
    layout="wide",
)

st.markdown("""
<style>
    .stApp { max-width: 1200px; margin: 0 auto; }
    .big-title { font-size: 2rem; font-weight: bold; margin-bottom: 0.5rem; }
    .sub-title { font-size: 1rem; color: #666; margin-bottom: 2rem; }
    .post-card {
        background: #f8f9fa; border-radius: 8px; padding: 1rem;
        margin-bottom: 0.5rem; border-left: 4px solid #6366f1;
    }
    .char-ok { color: #22c55e; font-weight: bold; }
    .char-warn { color: #f59e0b; font-weight: bold; }
    .char-over { color: #ef4444; font-weight: bold; }
    .step { flex: 1; text-align: center; padding: 0.5rem; border-radius: 8px; background: #f0f0f0; color: #999; }
    .step-active { background: #6366f1; color: white; }
    .step-done { background: #22c55e; color: white; }
</style>
""", unsafe_allow_html=True)


def show_friendly_error(e: Exception, context: str = "処理"):
    err_str = str(e)
    if "RESOURCE_EXHAUSTED" in err_str or "429" in err_str or "quota" in err_str.lower():
        st.error(
            f"⚠️ **Geminiの1日の無料枠を使い切りました**\n\n"
            f"**解決策（どれか1つ）:**\n"
            f"1. **24時間待つ** → 翌日に自動でリセット\n"
            f"2. **別のGoogleアカウントで新しいAPI Keyを作る** → "
            f"[Google AI Studio](https://aistudio.google.com/apikey)\n"
            f"3. **リサーチや学習モードをOFFにして1コールに減らす**"
        )
    elif "API key" in err_str or "API_KEY" in err_str:
        st.error("⚠️ **APIキーが正しくありません**\n\n左サイドバーのGemini API Keyを確認してください。")
    else:
        st.error(f"{context}に失敗しました: {e}")


# --- セッション初期化 ---
def _init_state():
    defaults = {
        "step": 1,
        "research": None,
        "posts_result": None,
        "angles": None,
        "selected_angle": None,
        "quiz_set": None,
        "quiz_answers": {},
        "field": "心理学",
        "author_identity": "",
        "author_pain": "",
        "concept": "",
        "persona": "",
        "cta_label": "",
        "cta_slot": "夜",
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

_init_state()


# --- ヘッダー ---
st.markdown('<div class="big-title">🧵 Threads 5投稿ライター</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">ターゲット(何に悩んでいる、どんな人?) → 朝/午前/昼/午後/夜の5投稿を一括生成</div>', unsafe_allow_html=True)

with st.expander("📖 はじめての方へ｜このツールの使い方", expanded=True):
    st.markdown("""
### 🚨 まずやること

**左サイドバーに「Gemini API Key」を貼り付けてください。**

- API Keyとは: AIに話しかけるための鍵(Googleアカウントがあれば無料)
- クレジットカード登録 **不要**
- 所要時間: **約2分**

---

### 🔑 Gemini APIキー取得手順(画像なし・5ステップ)

1. **[Google AI Studio (https://aistudio.google.com/apikey)](https://aistudio.google.com/apikey) を開く**
   → Googleアカウント(Gmail等)でログイン
2. 右上の **「Create API key」** ボタンをクリック
3. プロジェクトを選択(無ければ「Create API key in new project」)
4. 表示された **`AIzaSy...` で始まる文字列をコピー**
5. このアプリの **左サイドバーの「Gemini API Key」欄に貼り付け** → 完了

🖼️ **画像付きの詳しい手順はこちら →**
[GitHub: 画像付きAPIキー取得ガイド](https://github.com/atsushi0706/threads-writer-tool/blob/master/docs/GEMINI_API_KEY_GUIDE.md)

> ⚠️ クレジットカード登録は **完全に不要**。
> 1日1,500リクエストまで無料で使えます(このツールはフル機能で1日3リクエストなので余裕)。

---

### 🎯 このツールでできること

**ターゲット(何に悩んでいる、どんな人か)** を入力すると、その人向けの5投稿を一括生成します。

- ✅ 朝/午前/昼/午後/夜の5投稿を1日のストーリーで一括生成
- ✅ 各投稿500字以内・テキストのみ（画像なし＝シャドウバン回避）
- ✅ 各投稿の「**何を意識して書いたか**」を一般コピーライティング観点で詳しく解説(学習機能)
- ✅ リサーチ後に5つの角度を提案 → 1つ選んでから生成(被り防止)
- ✅ 生成と同時にコピーライティング学習クイズ(5問)で PASONA / PASTOR / PASBECONA / 4U / WIIFM・用語(LP・CTA・Hook・DRM・ONE HACKモデル)を学べる
- ✅ プロフィール＋ターゲットをJSON保存→次回読み込みで一発復元

---

### 📐 5投稿の流れ

| 時間 | ステージ | 役割 |
|---|---|---|
| 朝8時 | **H** Hook | 矛盾・謎かけで指を止める |
| 午前11時 | **A** Ask | 「あなたのせいじゃない、構造の問題」 |
| 昼12時 | **C** Core | アハ体験・新事実の提示 |
| 午後17時 | **E** Echo | 別角度で言い直し |
| 夜21時 | **K** Key | 誘導（問いかけ／プロフ／行動） |

5投稿全体で「1ターゲット／1アイデア／1感情／1ミステリー／1アクション」を貫く設計(コピーライティングの Rule of One 原則)。

---

### ⚠️ API消費の目安
- リサーチ ON: 1コール(任意)
- 5投稿生成: 1コール
- 角度提案: 1コール
- クイズ生成: 1コール(5問のうち2問はAI生成、残り3問は固定プール)
→ フル機能で **3コール / 1日**
""")


# --- ステップインジケーター ---
steps = ["① 入力", "② 角度を選ぶ", "③ 5投稿生成"]
cols = st.columns(3)
for i, (col, label) in enumerate(zip(cols, steps), 1):
    if i < st.session_state.step:
        col.markdown(f'<div class="step step-done">{label} ✓</div>', unsafe_allow_html=True)
    elif i == st.session_state.step:
        col.markdown(f'<div class="step step-active">{label}</div>', unsafe_allow_html=True)
    else:
        col.markdown(f'<div class="step">{label}</div>', unsafe_allow_html=True)

st.divider()


# --- サイドバー ---
with st.sidebar:
    st.header("設定")
    api_key = st.text_input(
        "Gemini API Key",
        type="password",
        value=DEFAULT_API_KEY,
        help="Google AI Studio で無料取得(クレカ不要・所要約2分)。.env に GEMINI_API_KEY を置けば自動入力。",
    )
    if not api_key:
        st.info(
            "🔑 **Gemini API Key が必要です**\n\n"
            "**[👉 Google AI Studio で発行する(無料)](https://aistudio.google.com/apikey)**\n\n"
            "詳しい手順: [画像付きガイド](https://github.com/atsushi0706/threads-writer-tool/blob/master/docs/GEMINI_API_KEY_GUIDE.md)"
        )
    elif DEFAULT_API_KEY and api_key == DEFAULT_API_KEY:
        st.success("✅ .env から自動入力済み")
    if api_key:
        st.session_state["_api_key"] = api_key

    st.divider()
    st.markdown("**プロファイル保存/読込**")

    profile_json = export_profile(st.session_state)
    st.download_button(
        "💾 プロファイルをダウンロード",
        data=profile_json,
        file_name="threads_writer_profile.json",
        mime="application/json",
        use_container_width=True,
        help="入力したプロフィール・ターゲット・設定をJSONで保存。次回アップロードで一発復元できます",
    )

    uploaded = st.file_uploader("📂 プロファイル読み込み", type="json", label_visibility="collapsed")
    if uploaded is not None:
        try:
            loaded = import_profile(uploaded.read().decode("utf-8"))
            for k, v in loaded.items():
                st.session_state[k] = v
            st.success("プロファイルを読み込みました。下のフォームに反映されています。")
        except Exception as e:
            st.error(f"読み込み失敗: {e}")

    st.divider()
    st.caption("Gemini 2.5 Flash(無料枠)+ Google検索で動作")
    st.caption("コピーライティングの Rule of One 原則で5投稿を貫く構成")

    if st.button("最初からやり直す", use_container_width=True):
        for k in ["step", "research", "posts_result", "angles", "selected_angle", "quiz_set", "quiz_answers"]:
            if k in st.session_state:
                del st.session_state[k]
        _init_state()
        st.rerun()


# ========================================
# STEP 1: 入力
# ========================================
if st.session_state.step == 1:

    st.header("① 入力")

    # --- 分野 ---
    st.subheader("分野")
    field_options = ["心理学", "育児・教育", "健康・ヘルスケア", "ビジネス・キャリア", "スピリチュアル", "エッセイ・日常"]
    if st.session_state.field not in field_options:
        st.session_state.field = field_options[0]
    st.session_state.field = st.selectbox(
        "あなたの発信分野",
        options=field_options,
        index=field_options.index(st.session_state.field),
        help="hookで使う『権威』の素材方針が変わります",
    )

    st.divider()

    # --- プロフィール ---
    st.subheader("あなたのプロフィール")
    st.caption("入力すると5投稿に反映されます。空でもOK")
    st.session_state.author_identity = st.text_area(
        "あなたは何者で、どういったことを発信しているか",
        value=st.session_state.author_identity,
        placeholder="例: 元銀行員のキャリアコーチ。30代女性向けに副業から起業を支援",
        height=80,
    )
    st.session_state.author_pain = st.text_area(
        "過去にどんな悩み・痛みを経験したか",
        value=st.session_state.author_pain,
        placeholder="例: 銀行時代に過労で体を壊した。お金のために自分を殺していた経験",
        height=80,
    )

    st.divider()

    # --- ターゲット ---
    st.subheader("ターゲット")
    st.caption("**何に悩んでいて、どんな人への投稿か**を書いてください。1人の顔が浮かぶレベルで具体的に。")
    st.session_state.persona = st.text_area(
        "ターゲット — 何に悩んでいる、どんな人?",
        value=st.session_state.persona,
        placeholder=(
            "例: 30代フリーランスのWebデザイナー。\n"
            "仕事は順調だけど自己肯定感が低くて、夜になると『私って本当にこのままでいいのかな』と"
            "SNSを見ながら自分を他人と比べて落ち込む。完璧にやろうとして何度もやり直してしまい、"
            "気づくと深夜まで仕事している。"
        ),
        height=140,
    )
    # 内部処理用: ターゲット文をコンセプトにも流用(リサーチ・生成側はこの値を読む)
    st.session_state.concept = st.session_state.persona

    st.divider()

    # --- CTA ---
    with st.expander("📌 CTA（任意）— プロフィール誘導文"):
        st.caption("CTAは5投稿のうち1スロットだけに自然に挿入されます。空ならCTAなし")
        st.session_state.cta_label = st.text_input(
            "CTA文言",
            value=st.session_state.cta_label,
            placeholder="例: もっと詳しく知りたい方はプロフィールから",
        )
        st.session_state.cta_slot = st.selectbox(
            "挿入スロット",
            options=["朝", "午前", "昼", "午後", "夜"],
            index=["朝", "午前", "昼", "午後", "夜"].index(st.session_state.cta_slot),
            help="夜（K Key）が最有力",
        )

    st.divider()

    # --- リサーチON/OFF ---
    use_research = st.checkbox(
        "🔍 Google検索で先にリサーチ（API+1回消費・推奨）",
        value=True,
        help="権威・研究結果を実際に検索して素材を集めます。OFFなら一般知識で生成",
    )

    st.divider()

    # --- 生成ボタン ---
    if st.button("🚀 5投稿を生成", type="primary", use_container_width=True, disabled=not api_key):
        if not st.session_state.concept:
            st.error("ターゲットを入力してください。")
        elif not st.session_state.persona:
            st.error("ペルソナを入力してください。")
        else:
            try:
                # リサーチ
                if use_research:
                    with st.spinner("リサーチ中..."):
                        # 分野→既存リサーチgenreにマッピング
                        genre_map = {
                            "心理学": "psychology",
                            "育児・教育": "psychology",
                            "健康・ヘルスケア": "psychology",
                            "ビジネス・キャリア": "psychology",
                            "スピリチュアル": "spiritual",
                            "エッセイ・日常": "essay",
                        }
                        st.session_state.research = research_topic(
                            st.session_state.concept,
                            st.session_state.persona,
                            api_key,
                            genre=genre_map.get(st.session_state.field, "psychology"),
                        )
                else:
                    st.session_state.research = {"evidence": [], "expert_quotes": []}

                # 角度提案(リサーチ素材から5案)
                from src.angle_proposer import propose_angles
                with st.spinner("リサーチ素材から5つの角度を提案中..."):
                    st.session_state.angles = propose_angles(
                        concept=st.session_state.concept,
                        persona=st.session_state.persona,
                        field=st.session_state.field,
                        author_identity=st.session_state.author_identity,
                        author_pain=st.session_state.author_pain,
                        research=st.session_state.research or {},
                        api_key=api_key,
                        n=5,
                    )

                st.session_state.step = 2
                st.rerun()
            except Exception as e:
                show_friendly_error(e, "生成")


# ========================================
# STEP 2: 角度を選ぶ
# ========================================
elif st.session_state.step == 2:
    angles = st.session_state.angles or []
    if not angles:
        st.error("角度の提案がありません。最初からやり直してください。")
        if st.button("最初に戻る"):
            st.session_state.step = 1
            st.rerun()
        st.stop()

    st.subheader("② 今日の角度を選んでください")
    st.caption("同じターゲットでも、毎回違う角度で書けば被りません。気になる切り口を1つ選んでください。")

    choice_idx = st.radio(
        "角度",
        options=list(range(len(angles))),
        format_func=lambda i: f"案{i+1}: {angles[i].get('title', '')}",
        key="angle_choice",
    )
    chosen = angles[choice_idx]

    with st.container(border=True):
        st.markdown(f"### {chosen.get('title', '')}")
        st.markdown(f"**コア気づき**: {chosen.get('core_insight', '')}")
        st.markdown(f"**使う権威ヒント**: {chosen.get('key_authority_hint', '')}")
        st.markdown(f"**痛みの瞬間**: {chosen.get('target_pain_specific', '')}")

    col_a, col_b = st.columns([1, 1])
    if col_a.button("← 入力に戻る", use_container_width=True):
        st.session_state.step = 1
        st.rerun()
    if col_b.button("この角度で5投稿を生成 →", use_container_width=True, type="primary"):
        st.session_state.selected_angle = chosen
        try:
            with st.spinner("5投稿を生成中..."):
                posts_result = generate_5posts(
                    concept=st.session_state.concept,
                    persona=st.session_state.persona,
                    field=st.session_state.field,
                    research=st.session_state.research or {},
                    api_key=st.session_state.get("_api_key", ""),
                    author_identity=st.session_state.author_identity,
                    author_pain=st.session_state.author_pain,
                    cta_label=st.session_state.cta_label,
                    cta_slot=st.session_state.cta_slot,
                    selected_angle=chosen,
                )
                st.session_state.posts_result = posts_result
            # クイズ生成(任意・失敗してもメイン処理は続行)
            try:
                with st.spinner("コピーライティングクイズを準備中..."):
                    st.session_state.quiz_set = build_quiz_set(
                        posts_result,
                        difficulty="beginner",
                        api_key=st.session_state.get("_api_key", ""),
                        use_ai=True,
                        total=5,
                    )
                    st.session_state.quiz_answers = {}
            except Exception:
                st.session_state.quiz_set = None
            st.session_state.step = 3
            st.rerun()
        except Exception as e:
            show_friendly_error(e, "生成")


# ========================================
# STEP 3: 5投稿表示
# ========================================
elif st.session_state.step == 3:
    posts_result = st.session_state.posts_result
    if not posts_result:
        st.error("生成結果がありません。最初からやり直してください。")
        st.stop()

    st.header("② 5投稿生成完了")

    # 共通要素 (Rule of One)
    with st.expander("📋 1日全体のRule of One（5投稿共通の軸）", expanded=False):
        st.markdown(f"""
- **ワン・ターゲット**: {posts_result.get('shared_one_target', '')}
- **ワン・アイデア**: {posts_result.get('shared_one_idea', '')}
- **ワン・エモーション**: {posts_result.get('shared_one_emotion', '')}
- **ワン・ミステリー**: {posts_result.get('shared_one_mystery', '')}
- **ワン・アクション**: {posts_result.get('shared_one_action', '')}
""")

    st.divider()

    # 各投稿を表示
    posts = posts_result.get("posts", [])
    for idx, post in enumerate(posts):
        slot = post.get("slot", "")
        time = post.get("time", "")
        stage = post.get("stage", "")
        stage_name = post.get("stage_name", "")

        with st.container(border=True):
            st.markdown(f"### {slot}（{time}） — **{stage} {stage_name}**")

            # 編集可能エリア(生成結果は全部見えるサイズで)
            hook = st.text_area(
                "Hook(冒頭フック)",
                value=post.get("hook", ""),
                height=180,
                key=f"hook_{idx}",
            )
            body = st.text_area(
                "Body(本文)",
                value=post.get("body", ""),
                height=400,
                key=f"body_{idx}",
            )
            full_text = (hook + body).strip()
            char_count = len(full_text)

            # 文字数表示
            if char_count <= 450:
                cls = "char-ok"
            elif char_count <= 500:
                cls = "char-warn"
            else:
                cls = "char-over"
            st.markdown(f'<span class="{cls}">文字数: {char_count} / 500</span>', unsafe_allow_html=True)

            # コピー用テキストエリア(全部見える高さ)
            st.text_area(
                "📋 コピー用(hook + body 連結)",
                value=hook + "\n\n" + body,
                height=350,
                key=f"copy_{idx}",
                help="右上のコピーボタンでコピーしてThreadsに貼り付け",
            )

            # 解説モード
            with st.expander("💡 なぜこの構成？（ONE HACK解剖）"):
                st.markdown(f"**設計理由**：{post.get('design_reason', '（解説なし）')}")
                st.markdown("---")
                st.markdown("**ONE HACK要素チェック**：")
                st.markdown(f"- **権威**：{post.get('authority_used', '（なし）')}")
                if post.get("core_keyword"):
                    st.markdown(f"- **Core キーワード**：{post.get('core_keyword')}")
                if post.get("core_metaphor"):
                    st.markdown(f"- **伝達手段（比喩）**：{post.get('core_metaphor')}")
                if post.get("key_direction"):
                    st.markdown(f"- **Key 誘導先**：{post.get('key_direction')}")
                st.markdown(f"- **CTA挿入**：{'あり' if post.get('has_cta') else 'なし'}")

            # 個別再生成 — 修正指示を入れて再生成できる
            st.markdown("---")
            st.markdown("**🔄 この投稿を直したいとき**")
            revision_request = st.text_area(
                "どこをどう直したいか具体的に書いてください(空でもOK)",
                key=f"revision_{idx}",
                placeholder=(
                    "例: hookが固いのでもっと短くして / 「○○」という言葉を使わないで / "
                    "もっと具体的な場面を入れて / セリフを変えて / 専門用語を日常語に置き換えて"
                ),
                height=80,
            )
            if st.button("この投稿を再生成", key=f"regen_{idx}", type="primary"):
                with st.spinner(f"{slot}枠を再生成中..."):
                    try:
                        new_post = regenerate_single_post(
                            slot=slot,
                            concept=st.session_state.concept,
                            persona=st.session_state.persona,
                            field=st.session_state.field,
                            research=st.session_state.research or {},
                            shared_context=posts_result,
                            api_key=st.session_state.get("_api_key", ""),
                            author_identity=st.session_state.author_identity,
                            author_pain=st.session_state.author_pain,
                            cta_label=st.session_state.cta_label if slot == st.session_state.cta_slot else "",
                            revision_request=revision_request,
                            previous_post=post,
                        )
                        posts_result["posts"][idx] = {**post, **new_post}
                        st.session_state.posts_result = posts_result
                        # text_area は key が同じだと古い値を保持してしまうので、
                        # 該当slotのwidget state を削除して強制再初期化させる
                        for k in [f"hook_{idx}", f"body_{idx}", f"copy_{idx}", f"revision_{idx}"]:
                            if k in st.session_state:
                                del st.session_state[k]
                        st.rerun()
                    except Exception as e:
                        show_friendly_error(e, "再生成")

    st.divider()

    # 全投稿一括ダウンロード
    st.subheader("💾 全投稿をダウンロード")
    json_data = json.dumps(posts_result, ensure_ascii=False, indent=2)
    st.download_button(
        "JSONでダウンロード",
        data=json_data,
        file_name="threads_5posts.json",
        mime="application/json",
        use_container_width=True,
    )

    st.link_button(
        "🚀 Threadsで投稿する",
        url="https://www.threads.net/",
        use_container_width=True,
    )

    # ============================
    # コピーライティング学習クイズ(5問)
    # ============================
    if st.session_state.quiz_set:
        st.divider()
        st.header("📚 コピーライティング学習クイズ(5問)")
        st.caption("生成された5投稿を題材に、PASONA・PASTOR・PASBECONA・4U・WIIFM などの一般原則 + 用語(LP・CTA・Hook・DRM・ONE HACKモデル)を学べます")

        for q_idx, q in enumerate(st.session_state.quiz_set):
            with st.container(border=True):
                st.markdown(f"### Q{q_idx + 1} ({q.get('category', '')})")
                st.markdown(q.get("question", ""))

                options = q.get("options", [])
                answer_index = q.get("answer_index", 0)

                user_choice = st.radio(
                    "選択肢",
                    options=list(range(len(options))),
                    format_func=lambda i, opts=options: f"{['①','②','③','④'][i]} {opts[i]}",
                    key=f"quiz_{q_idx}",
                    label_visibility="collapsed",
                )

                if st.button("回答する", key=f"answer_{q_idx}"):
                    st.session_state.quiz_answers[q_idx] = user_choice

                if q_idx in st.session_state.quiz_answers:
                    chosen_idx = st.session_state.quiz_answers[q_idx]
                    if chosen_idx == answer_index:
                        st.success(f"✅ 正解! {['①','②','③','④'][answer_index]} {options[answer_index]}")
                    else:
                        st.error(f"❌ 不正解。正解は {['①','②','③','④'][answer_index]} {options[answer_index]}")
                    st.info(f"💡 解説: {q.get('explanation', '')}")

    st.divider()

    col_a, col_b = st.columns(2)
    if col_a.button("← 別の角度を選び直す", use_container_width=True):
        st.session_state.step = 2
        st.rerun()
    if col_b.button("← 入力に戻る", use_container_width=True):
        st.session_state.step = 1
        st.rerun()
