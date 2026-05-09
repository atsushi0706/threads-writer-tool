"""
Threads 5投稿ライターツール — Streamlit UI

1日のテーマ → 5投稿（H→A→C→E→K）一括生成 → コピー → Threadsに貼り付け
学習モードでコピーライティングクイズも出題(5問・初級/中級/上級)。一般原則(PASONA/PASTOR/PASBECONA/4U/WIIFM)+ 用語(LP/CTA/Hook/DRM/ONE HACKモデル)を学べる。
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
        "quiz_set": None,
        "quiz_answers": {},
        "field": "心理学",
        "author_identity": "",
        "author_pain": "",
        "concept": "",
        "persona": "",
        "cta_label": "",
        "cta_slot": "夜",
        "tone_aggressive": 30,
        "tone_blunt": False,
        "writer_style": "",
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

_init_state()


# --- ヘッダー ---
st.markdown('<div class="big-title">🧵 Threads 5投稿ライター</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">ターゲット(何に悩んでいる、どんな人?) → 朝/午前/昼/午後/夜の5投稿を一括生成</div>', unsafe_allow_html=True)

with st.expander("📖 はじめての方へ｜このツールの使い方", expanded=False):
    st.markdown("""
### 🚨 まずやること

**左サイドバーに「Gemini API Key」を貼り付けてください。**

- API Keyとは: AIに話しかけるための鍵（Googleアカウントがあれば無料）
- クレジットカード登録 **不要**
- 取得手順 → [Google AI Studio](https://aistudio.google.com/apikey)

---

### 🎯 このツールでできること

**ターゲット(何に悩んでいる、どんな人か)** を入力すると、その人向けの5投稿を一括生成します。

- ✅ 朝/午前/昼/午後/夜の5投稿を1日のストーリーで一括生成
- ✅ 各投稿500字以内・テキストのみ（画像なし＝シャドウバン回避）
- ✅ 各投稿の「**何を意識して書いたか**」を一般コピーライティング観点で詳しく解説(学習機能)
- ✅ 学習モードONでコピーライティングクイズ(5問・初級/中級/上級)。
  PASONA / PASTOR / PASBECONA / 4U / WIIFM、用語(LP / CTA / Hook / DRM / ONE HACK モデル) を学べる
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
- クイズAI生成 ON: 1コール(任意・5問のうち2問がAI生成)
→ フル機能で **3コール / 1日**
""")


# --- ステップインジケーター ---
steps = ["① 入力", "② 5投稿＋クイズ"]
cols = st.columns(2)
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
        help="Google AI Studio (aistudio.google.com) で無料取得。.envにGEMINI_API_KEYを置けば自動入力",
    )
    if not api_key:
        st.info("Gemini API Keyを入力してください。\n\n[Google AI Studio](https://aistudio.google.com/apikey) で無料取得。")
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
        for k in ["step", "research", "posts_result", "quiz_set", "quiz_answers"]:
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

    # --- トーン ---
    st.subheader("トーン設定")
    col1, col2 = st.columns(2)
    with col1:
        st.session_state.tone_aggressive = st.slider(
            "トーン",
            min_value=0, max_value=100, value=st.session_state.tone_aggressive,
            help="0: とても優しい ← → 100: 挑発的",
        )
        v = st.session_state.tone_aggressive
        if v <= 25:
            st.caption("🕊️ とても優しく包み込むトーン")
        elif v <= 50:
            st.caption("😊 基本優しく、核心では少し踏み込む")
        elif v <= 75:
            st.caption("💪 愛のある厳しさ")
        else:
            st.caption("🔥 常識を揺さぶる挑発的フック")
    with col2:
        blunt_choice = st.radio(
            "伝え方",
            options=["柔らかく包む", "グサッと言い切る"],
            index=1 if st.session_state.tone_blunt else 0,
        )
        st.session_state.tone_blunt = (blunt_choice == "グサッと言い切る")

    st.session_state.writer_style = st.text_input(
        "参考にしたいライタースタイル（任意）",
        value=st.session_state.writer_style,
        placeholder="例: メンタリストDaiGo、岡本太郎、村上春樹",
    )

    st.divider()

    # --- 学習モード ---
    st.subheader("📚 学習モード(コピーライティングクイズ)")
    use_quiz = st.checkbox(
        "5投稿生成と同時にクイズも出す(5問)",
        value=True,
        help="一般コピーライティング(PASONA / PASTOR / PASBECONA / 4U / WIIFM など) と用語(LP/CTA/Hook/DRM/ONE HACK)を学べます。AI問題2問でAPIを+1回消費",
    )
    quiz_difficulty = st.radio(
        "難易度",
        options=["beginner", "intermediate", "advanced"],
        format_func=lambda x: {"beginner": "初級(用語・基本)", "intermediate": "中級(応用)", "advanced": "上級(本質)"}[x],
        index=0,
        horizontal=True,
        disabled=not use_quiz,
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

                # 5投稿生成
                with st.spinner("5投稿を生成中..."):
                    posts_result = generate_5posts(
                        concept=st.session_state.concept,
                        persona=st.session_state.persona,
                        field=st.session_state.field,
                        research=st.session_state.research,
                        tone_aggressive=st.session_state.tone_aggressive,
                        tone_blunt=st.session_state.tone_blunt,
                        writer_style=st.session_state.writer_style,
                        api_key=api_key,
                        author_identity=st.session_state.author_identity,
                        author_pain=st.session_state.author_pain,
                        cta_label=st.session_state.cta_label,
                        cta_slot=st.session_state.cta_slot,
                    )
                    st.session_state.posts_result = posts_result

                # クイズ
                if use_quiz:
                    with st.spinner("クイズを準備中..."):
                        st.session_state.quiz_set = build_quiz_set(
                            posts_result, quiz_difficulty, api_key, use_ai=True
                        )
                        st.session_state.quiz_answers = {}
                else:
                    st.session_state.quiz_set = None

                st.session_state.step = 2
                st.rerun()
            except Exception as e:
                show_friendly_error(e, "生成")


# ========================================
# STEP 2: 5投稿表示 + クイズ
# ========================================
elif st.session_state.step == 2:
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

            # 編集可能エリア
            hook = st.text_area(
                "Hook（冒頭フック）",
                value=post.get("hook", ""),
                height=80,
                key=f"hook_{idx}",
            )
            body = st.text_area(
                "Body（本文）",
                value=post.get("body", ""),
                height=200,
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

            # コピー用テキストエリア
            st.text_area(
                "📋 コピー用（hook + body 連結）",
                value=hook + "\n\n" + body,
                height=120,
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

            # 個別再生成ボタン
            col1, col2 = st.columns([3, 1])
            with col2:
                if st.button("🔄 この投稿だけ再生成", key=f"regen_{idx}"):
                    with st.spinner(f"{slot}枠を再生成中..."):
                        try:
                            new_post = regenerate_single_post(
                                slot=slot,
                                concept=st.session_state.concept,
                                persona=st.session_state.persona,
                                field=st.session_state.field,
                                research=st.session_state.research or {},
                                shared_context=posts_result,
                                tone_aggressive=st.session_state.tone_aggressive,
                                tone_blunt=st.session_state.tone_blunt,
                                writer_style=st.session_state.writer_style,
                                api_key=st.session_state.get("_api_key", ""),
                                author_identity=st.session_state.author_identity,
                                author_pain=st.session_state.author_pain,
                                cta_label=st.session_state.cta_label if slot == st.session_state.cta_slot else "",
                            )
                            posts_result["posts"][idx] = {**post, **new_post}
                            st.session_state.posts_result = posts_result
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
    # クイズ
    # ============================
    if st.session_state.quiz_set:
        st.divider()
        st.header("📚 コピーライティング学習クイズ(5問)")
        st.caption("生成された5投稿と、PASONA・PASTOR・PASBECONA・4U・WIIFM などの一般原則 + 用語(LP・CTA・Hook・DRM・ONE HACKモデル)を学びましょう")

        for q_idx, q in enumerate(st.session_state.quiz_set):
            with st.container(border=True):
                st.markdown(f"### Q{q_idx + 1}（{q.get('category', '')}）")
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
                    chosen = st.session_state.quiz_answers[q_idx]
                    if chosen == answer_index:
                        st.success(f"✅ 正解！ {['①','②','③','④'][answer_index]} {options[answer_index]}")
                    else:
                        st.error(f"❌ 不正解。正解は {['①','②','③','④'][answer_index]} {options[answer_index]}")
                    st.info(f"💡 解説：{q.get('explanation', '')}")

    st.divider()

    if st.button("← 入力に戻る", use_container_width=True):
        st.session_state.step = 1
        st.rerun()
