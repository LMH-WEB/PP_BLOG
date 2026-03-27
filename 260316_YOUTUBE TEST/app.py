import re
import google.generativeai as genai
import streamlit as st
from youtube_transcript_api import YouTubeTranscriptApi, NoTranscriptFound, TranscriptsDisabled

# ── 페이지 설정 ──────────────────────────────────────────────────────────────
st.set_page_config(page_title="유튜브 강의 각색기", page_icon="🎓", layout="wide")
st.title("🎓 유튜브 강의 각색기")
st.caption("유튜브 영상 링크를 넣으면 Gemini AI가 강의를 새롭게 각색해 드립니다. (무료)")

# ── 각색 스타일 정의 ─────────────────────────────────────────────────────────
STYLES = {
    "🟢 초보자용 쉽게 설명": {
        "desc": "어려운 용어 없이 누구나 이해할 수 있도록 쉽게 재설명합니다.",
        "prompt": (
            "아래 강의 내용을 완전 초보자도 이해할 수 있도록 쉽게 각색해 주세요. "
            "어려운 전문 용어는 쉬운 말로 풀어 쓰고, 실생활 예시를 들어 설명해 주세요. "
            "각 개념마다 '왜 중요한지'도 짧게 설명해 주세요."
        ),
    },
    "📋 핵심 요약 정리": {
        "desc": "핵심 내용만 간결하게 정리합니다.",
        "prompt": (
            "아래 강의 내용을 핵심만 뽑아 깔끔하게 요약·정리해 주세요. "
            "구조: ① 핵심 주제 1~2줄 요약, ② 주요 개념 목록(불릿), ③ 핵심 포인트 3~5개, ④ 한 줄 결론. "
            "불필요한 반복이나 예시는 제거하고 핵심만 남겨 주세요."
        ),
    },
    "💬 대화체·스토리 형식": {
        "desc": "딱딱한 강의를 친근한 대화나 이야기로 변환합니다.",
        "prompt": (
            "아래 강의 내용을 친근한 대화체나 흥미로운 스토리 형식으로 각색해 주세요. "
            "'~했어요', '~거든요' 같은 부드러운 말투를 사용하고, "
            "강의를 마치 친구가 설명해 주는 것처럼 자연스럽게 만들어 주세요. "
            "중간중간 흥미로운 비유나 짧은 이야기를 넣어도 좋습니다."
        ),
    },
    "🎓 심화·전문가용": {
        "desc": "전문 지식을 추가하고 심화 내용으로 확장합니다.",
        "prompt": (
            "아래 강의 내용을 전문가 수준으로 심화·확장해 주세요. "
            "관련 이론적 배경, 전문 용어의 정확한 정의, 심화 개념, "
            "실무에서의 적용 방법, 주의사항 등을 추가해 주세요. "
            "참고할 만한 관련 개념도 함께 언급해 주세요."
        ),
    },
    "📝 블로그 포스트 형식": {
        "desc": "읽기 좋은 블로그 글 형식으로 변환합니다.",
        "prompt": (
            "아래 강의 내용을 매력적인 블로그 포스트 형식으로 각색해 주세요. "
            "구조: 흥미로운 제목, 도입부(왜 이 내용이 중요한지), 본문(소제목 포함), 마무리. "
            "독자가 끝까지 읽고 싶도록 자연스럽고 읽기 좋게 작성해 주세요."
        ),
    },
}


# ── 유틸 함수 ────────────────────────────────────────────────────────────────
def extract_video_id(url: str) -> str | None:
    """유튜브 URL에서 video ID 추출"""
    match = re.search(r"(?:v=|youtu\.be/|embed/|shorts/)([A-Za-z0-9_-]{11})", url)
    return match.group(1) if match else None


def get_transcript(video_id: str) -> str:
    """자막 추출 (한국어 우선, 없으면 영어)"""
    try:
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
        for lang in ["ko", "en"]:
            try:
                transcript = transcript_list.find_transcript([lang])
                entries = transcript.fetch()
                return " ".join(e.text for e in entries)
            except Exception:
                continue
        # 어떤 언어든 첫 번째 자막 사용
        transcript = next(iter(transcript_list))
        entries = transcript.fetch()
        return " ".join(e.text for e in entries)
    except TranscriptsDisabled:
        raise ValueError("이 영상은 자막이 비활성화되어 있습니다.")
    except NoTranscriptFound:
        raise ValueError("사용 가능한 자막을 찾을 수 없습니다.")
    except Exception as e:
        raise ValueError(f"자막 추출 실패: {e}")


def adapt_with_gemini(transcript: str, style_prompt: str, api_key: str):
    """Gemini API로 강의 각색 (스트리밍)"""
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(
        model_name="gemini-1.5-flash",
        system_instruction=(
            "당신은 교육 콘텐츠 전문가입니다. "
            "유튜브 강의의 자막(스크립트)을 받아 사용자가 원하는 스타일로 각색합니다. "
            "한국어로 자연스럽고 명확하게 작성해 주세요."
        ),
    )

    user_message = (
        f"{style_prompt}\n\n"
        f"--- 원본 강의 자막 ---\n{transcript[:12000]}\n---"
    )

    response = model.generate_content(user_message, stream=True)
    for chunk in response:
        if chunk.text:
            yield chunk.text


# ── 사이드바: API 키 입력 ─────────────────────────────────────────────────────
with st.sidebar:
    st.image("logo.png", use_container_width=True)
    st.header("⚙️ 설정")
    api_key = st.text_input(
        "Google Gemini API Key",
        type="password",
        placeholder="AIzaSy...",
        help="Google AI Studio에서 무료로 발급받을 수 있습니다.",
    )
    st.markdown("---")
    st.markdown("**🔑 API 키 무료 발급**")
    st.markdown("[Google AI Studio 바로가기](https://aistudio.google.com/apikey)")
    st.markdown("---")
    st.markdown(
        "**사용 방법**\n"
        "1. API 키 입력\n"
        "2. 유튜브 링크 붙여넣기\n"
        "3. 각색 스타일 선택\n"
        "4. '각색 시작' 클릭"
    )

# ── 메인 UI ──────────────────────────────────────────────────────────────────
col1, col2 = st.columns([3, 2])

with col1:
    youtube_url = st.text_input(
        "유튜브 링크",
        placeholder="https://www.youtube.com/watch?v=...",
    )

with col2:
    style_name = st.selectbox(
        "각색 스타일",
        options=list(STYLES.keys()),
    )

st.info(f"**{style_name}** — {STYLES[style_name]['desc']}")

run_btn = st.button("🚀 각색 시작", type="primary", use_container_width=True)

# ── 실행 ─────────────────────────────────────────────────────────────────────
if run_btn:
    if not api_key:
        st.error("사이드바에서 Gemini API 키를 먼저 입력해 주세요.")
        st.stop()

    if not youtube_url:
        st.error("유튜브 링크를 입력해 주세요.")
        st.stop()

    video_id = extract_video_id(youtube_url)
    if not video_id:
        st.error("올바른 유튜브 링크를 입력해 주세요.")
        st.stop()
    assert video_id is not None

    # 1단계: 자막 추출
    transcript: str = ""
    with st.spinner("📥 자막을 추출하는 중..."):
        try:
            transcript = get_transcript(video_id)
        except ValueError as e:
            st.error(str(e))
            st.stop()

    if not transcript:
        st.stop()

    st.success(f"✅ 자막 추출 완료 (약 {len(transcript):,}자)")

    with st.expander("원본 자막 보기"):
        st.text(transcript[:3000] + ("..." if len(transcript) > 3000 else ""))

    # 2단계: Gemini로 각색
    st.markdown("---")
    st.subheader(f"📄 각색 결과 — {style_name}")

    style_prompt = STYLES[style_name]["prompt"]
    output_area = st.empty()
    full_text = ""

    try:
        for chunk in adapt_with_gemini(transcript, style_prompt, api_key):
            full_text += chunk
            output_area.markdown(full_text)
    except Exception as e:
        err = str(e)
        if "API_KEY_INVALID" in err or "invalid" in err.lower():
            st.error("API 키가 올바르지 않습니다. 다시 확인해 주세요.")
        elif "quota" in err.lower() or "rate" in err.lower():
            st.error("무료 사용 한도를 초과했습니다. 잠시 후 다시 시도해 주세요.")
        else:
            st.error(f"오류 발생: {e}")

    # 다운로드 버튼
    if full_text:
        st.markdown("---")
        st.download_button(
            "💾 결과 다운로드 (.txt)",
            data=full_text,
            file_name="각색_결과.txt",
            mime="text/plain",
        )
