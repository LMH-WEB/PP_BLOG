from groq import Groq
from ddgs import DDGS
import feedparser
import streamlit as st
import json, os, re

def clean_text(text: str) -> str:
    """한자·일본어(히라가나·가타카나) 제거 후 반환"""
    cleaned = re.sub(r'[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF]+', '', text)
    cleaned = re.sub(r' {2,}', ' ', cleaned)
    return cleaned

def strip_markdown(text: str) -> str:
    """다운로드용 txt에서 마크다운 기호 제거"""
    # --- 구분선 제거
    text = re.sub(r'^[-─━=]{2,}\s*$', '', text, flags=re.MULTILINE)
    # ### ## # 헤더 기호 제거
    text = re.sub(r'^#{1,6}\s*', '', text, flags=re.MULTILINE)
    # **굵게** 또는 *기울임* 제거
    text = re.sub(r'\*{1,3}(.+?)\*{1,3}', r'\1', text)
    # ✅ 📊 같은 이모지는 유지, 단 앞뒤 ** 만 제거
    # 연속 빈 줄 2개 이상 → 1개로
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()

# ── 페이지 설정 ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="AI 부동산 블로그",
    page_icon="🏠",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── 토스 스타일 CSS ────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;500;700;900&display=swap');

* { font-family: 'Noto Sans KR', sans-serif !important; }

/* 배경 */
.stApp { background-color: #F2F4F6; }

/* 사이드바 */
[data-testid="stSidebar"] {
    background-color: #FFFFFF;
    border-right: 1px solid #E5E8EB;
}
[data-testid="stSidebar"] * { color: #191F28 !important; }

/* 메인 컨텐츠 여백 */
.block-container { padding: 2rem 2rem 4rem 2rem !important; max-width: 960px; }

/* 카드 스타일 */
.toss-card {
    background: #FFFFFF;
    border-radius: 16px;
    padding: 24px 28px;
    margin-bottom: 16px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.06);
}
.toss-card-blue {
    background: #3182F6;
    border-radius: 16px;
    padding: 24px 28px;
    margin-bottom: 16px;
    color: white;
}
.toss-tag {
    display: inline-block;
    background: #EBF3FE;
    color: #3182F6;
    font-size: 12px;
    font-weight: 700;
    padding: 4px 10px;
    border-radius: 20px;
    margin-bottom: 10px;
}
.toss-tag-green {
    display: inline-block;
    background: #E8F9F0;
    color: #1BB76E;
    font-size: 12px;
    font-weight: 700;
    padding: 4px 10px;
    border-radius: 20px;
    margin-bottom: 10px;
}
.toss-h1 {
    font-size: 26px;
    font-weight: 900;
    color: #191F28;
    margin: 0 0 6px 0;
    line-height: 1.3;
}
.toss-h2 {
    font-size: 18px;
    font-weight: 700;
    color: #191F28;
    margin: 0 0 4px 0;
}
.toss-body {
    font-size: 14px;
    color: #6B7684;
    line-height: 1.6;
}
.toss-divider {
    border: none;
    border-top: 1px solid #F2F4F6;
    margin: 20px 0;
}
.metric-row {
    display: flex;
    gap: 12px;
    margin-bottom: 16px;
}
.metric-card {
    flex: 1;
    background: #F9FAFB;
    border-radius: 12px;
    padding: 16px;
    text-align: center;
}
.metric-num {
    font-size: 24px;
    font-weight: 900;
    color: #3182F6;
}
.metric-label {
    font-size: 12px;
    color: #8B95A1;
    margin-top: 2px;
}
.blog-output {
    background: #FFFFFF;
    border-radius: 16px;
    padding: 32px 36px;
    box-shadow: 0 2px 12px rgba(0,0,0,0.08);
    line-height: 1.9;
    font-size: 15px;
    color: #191F28;
}
.blog-output h2 {
    font-size: 22px !important;
    font-weight: 900 !important;
    color: #191F28 !important;
    margin-bottom: 20px !important;
    padding-bottom: 12px !important;
    border-bottom: 2px solid #3182F6 !important;
}
.blog-output h3 {
    font-size: 17px !important;
    font-weight: 700 !important;
    color: #3182F6 !important;
    margin: 28px 0 12px 0 !important;
}

/* 버튼 */
.stButton > button {
    background: #3182F6 !important;
    color: white !important;
    border: none !important;
    border-radius: 12px !important;
    padding: 14px 24px !important;
    font-size: 16px !important;
    font-weight: 700 !important;
    width: 100% !important;
    transition: all 0.2s !important;
}
.stButton > button:hover {
    background: #1B6EE0 !important;
    transform: translateY(-1px) !important;
    box-shadow: 0 4px 16px rgba(49,130,246,0.3) !important;
}

/* 입력창 */
.stTextInput > div > div > input {
    border-radius: 12px !important;
    border: 1.5px solid #E5E8EB !important;
    padding: 14px 16px !important;
    font-size: 15px !important;
    background: #FFFFFF !important;
}
.stTextInput > div > div > input:focus {
    border-color: #3182F6 !important;
    box-shadow: 0 0 0 3px rgba(49,130,246,0.12) !important;
}

/* 성공/오류 메시지 */
.stSuccess {
    background: #E8F9F0 !important;
    border: none !important;
    border-radius: 12px !important;
    color: #1BB76E !important;
}
.stError {
    background: #FFF0F0 !important;
    border: none !important;
    border-radius: 12px !important;
}

/* expander */
.streamlit-expanderHeader {
    background: #F9FAFB !important;
    border-radius: 12px !important;
    font-weight: 700 !important;
}

/* 다운로드 버튼 */
.stDownloadButton > button {
    background: #F2F4F6 !important;
    color: #191F28 !important;
    border: none !important;
    border-radius: 12px !important;
    font-weight: 700 !important;
}
.stDownloadButton > button:hover {
    background: #E5E8EB !important;
}

/* spinner */
.stSpinner > div { border-top-color: #3182F6 !important; }

/* 스트리밍 출력 */
[data-testid="stMarkdownContainer"] p { line-height: 1.8; }
</style>
""", unsafe_allow_html=True)


# ── API 키 저장/불러오기 ──────────────────────────────────────────────────────
SETTINGS_FILE = os.path.join(os.path.dirname(__file__), "settings.json")

def load_api_key() -> str:
    try:
        with open(SETTINGS_FILE, "r") as f:
            return json.load(f).get("groq_api_key", "")
    except Exception:
        return ""

def save_api_key(key: str):
    with open(SETTINGS_FILE, "w") as f:
        json.dump({"groq_api_key": key}, f)


# ── RSS 피드 ──────────────────────────────────────────────────────────────────
RSS_FEEDS = [
    ("직방 블로그",    "https://blog.zigbang.com/rss"),
    ("한국경제 부동산", "https://www.hankyung.com/feed/realestate"),
    ("매일경제 부동산", "https://www.mk.co.kr/rss/30100041/"),
    ("조선일보 부동산", "https://www.chosun.com/arc/outboundfeeds/rss/category/economy/real_estate/"),
]

def fetch_rss(keyword: str) -> list:
    results = []
    for source, url in RSS_FEEDS:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:10]:
                title   = entry.get("title", "")
                summary = entry.get("summary", entry.get("description", ""))
                if keyword in title or keyword in summary:
                    results.append({
                        "구분": "RSS",
                        "출처": source,
                        "제목": title,
                        "내용": summary[:300],
                        "링크": entry.get("link", ""),
                    })
        except Exception:
            pass
    return results

def search_news(keyword: str) -> list:
    results = []
    queries = [
        f"{keyword} 부동산 최신",
        f"직방 {keyword}",
        f"호갱노노 {keyword}",
        f"{keyword} 아파트 시세",
    ]
    try:
        with DDGS() as ddgs:
            for query in queries:
                for item in ddgs.news(query, max_results=4, timelimit="m"):
                    results.append({
                        "구분": "뉴스",
                        "출처": item.get("source", ""),
                        "제목": item.get("title", ""),
                        "내용": item.get("body", "")[:300],
                        "날짜": item.get("date", ""),
                        "링크": item.get("url", ""),
                    })
    except Exception:
        pass
    return results

def search_web_docs(keyword: str) -> list:
    results = []
    queries = [
        f"site:blog.naver.com {keyword} 부동산 실거래가",
        f"site:blog.naver.com {keyword} 아파트 시세 분석",
        f"site:cafe.naver.com {keyword} 아파트 매매",
        f"{keyword} 부동산 전망 분석 2025",
        f"{keyword} 아파트 실거래가 동향",
    ]
    try:
        with DDGS() as ddgs:
            for query in queries:
                for item in ddgs.text(query, max_results=3, timelimit="m"):
                    results.append({
                        "구분": "웹문서",
                        "출처": item.get("href", "")[:50],
                        "제목": item.get("title", ""),
                        "내용": item.get("body", "")[:400],
                        "링크": item.get("href", ""),
                    })
    except Exception:
        pass
    return results

def search_price_data(keyword: str) -> list:
    """호갱노노·네이버 부동산 실거래가 전용 검색"""
    results = []
    queries = [
        f"호갱노노 {keyword} 실거래가 최신",
        f"네이버 부동산 {keyword} 매매가 실거래",
        f"{keyword} 아파트 실거래가 2025 최신",
        f"{keyword} 매매가 전세가 시세 2025",
        f"국토교통부 {keyword} 실거래 신고가",
        f"{keyword} 아파트 평당가 시세표",
    ]
    try:
        with DDGS() as ddgs:
            for query in queries:
                for item in ddgs.text(query, max_results=3, timelimit="m"):
                    results.append({
                        "구분": "실거래가",
                        "출처": item.get("href", "")[:60],
                        "제목": item.get("title", ""),
                        "내용": item.get("body", "")[:500],
                        "링크": item.get("href", ""),
                    })
    except Exception:
        pass
    return results

def format_research_data(rss_data, news_data, web_data=None, price_data=None) -> str:
    lines = []
    web_data = web_data or []
    price_data = price_data or []

    if price_data:
        lines.append("=== 호갱노노·네이버 부동산 실거래가 ===")
        seen = set()
        count = 1
        for item in price_data:
            if item["제목"] in seen:
                continue
            seen.add(item["제목"])
            lines.append(f"[{count}] {item['제목']}")
            lines.append(f"    {item['내용']}")
            lines.append(f"    URL: {item['링크']}")
            lines.append("")
            count += 1
            if count > 10:
                break

    if rss_data:
        lines.append("=== RSS (직방·언론사) ===")
        for i, item in enumerate(rss_data[:6], 1):
            lines.append(f"[{i}] [{item['출처']}] {item['제목']}")
            lines.append(f"    {item['내용']}")
            lines.append(f"    URL: {item['링크']}")
            lines.append("")

    if web_data:
        lines.append("=== 네이버 블로그·카페·구글 웹문서 ===")
        seen = set()
        count = 1
        for item in web_data:
            if item["제목"] in seen:
                continue
            seen.add(item["제목"])
            lines.append(f"[{count}] {item['제목']}")
            lines.append(f"    {item['내용']}")
            lines.append(f"    URL: {item['링크']}")
            lines.append("")
            count += 1
            if count > 10:
                break

    if news_data:
        lines.append("=== 최신 뉴스 ===")
        seen = set()
        count = 1
        for item in news_data:
            if item["제목"] in seen:
                continue
            seen.add(item["제목"])
            lines.append(f"[{count}] [{item['출처']}] {item['제목']} ({item.get('날짜', '')})")
            lines.append(f"    {item['내용']}")
            lines.append(f"    URL: {item['링크']}")
            lines.append("")
            count += 1
            if count > 12:
                break

    return "\n".join(lines) if lines else "수집 데이터 없음 — 일반 부동산 지식 기반으로 분석"


# ── 시스템 프롬프트 ────────────────────────────────────────────────────────────
SEARCH_SYSTEM = """당신은 대한민국 최고의 부동산 시장 분석가이자 서치팀 전문가입니다.
호갱노노·네이버 부동산·KB부동산·한국부동산원·국토교통부 실거래 데이터를 정통하게 알고 있습니다.

수집된 데이터를 바탕으로 아래 항목을 빠짐없이 작성하세요.

【실거래가 분석】
1. 호갱노노·네이버 부동산 기준 최신 실거래가
   - 주요 단지명, 면적(평형), 실거래 금액, 거래 시점 명시
   - 직전 거래 대비 가격 변화 (상승/하락/보합 + 금액)
   - 전세가율 및 갭 투자 가능 여부
2. 매매가·전세가 변동률 (전월/전년 대비 % 수치)
3. 거래량 증감 (전월 대비 건수)

【현황 분석】
4. 핵심 이슈 요약 (최소 5개, 구체적 수치 포함)
5. 최근 3개월 주요 뉴스 흐름 (정책·금리·재건축·입주물량)
6. 금리·대출규제·정부정책 등 외부 요인 분석

【미래 예측 및 가설】
7. 향후 3~6개월 시장 방향 시나리오 (낙관/중립/비관 3가지, 각 시나리오에 가격 예측 수치 포함)
8. 전문가 시각의 핵심 가설 3가지 ("~한다면 ~할 것이다" 형식)
9. 투자자·실수요자가 지금 당장 주목해야 할 변수 Top 3

모든 수치에 출처(호갱노노/네이버부동산/KB부동산 등)를 반드시 표기하세요.
수집 데이터가 부족하면 최신 부동산 시장 지식으로 보완하되 출처를 "(추정)" 으로 표기하세요.
한국어로만 작성합니다.
⚠️ 한자(漢字), 일본어(히라가나·가타카나), 중국어 사용 절대 금지.
모든 단어는 순수 한국어 또는 영문 알파벳만 사용하세요."""


BLOG_SYSTEM = """당신은 대한민국 10년 경력의 부동산 전문 칼럼니스트입니다.
한국경제·매일경제·조선일보 부동산 섹션 수준의 분석 글을 씁니다.
호갱노노·네이버 부동산 실거래가 데이터를 직접 인용하여 독자가 신뢰할 수 있는 근거 기반 분석을 합니다.
단순 정보 나열이 아닌, 데이터 → 해석 → 시사점 → 독자 행동 제안의 흐름으로 글을 씁니다.

아래 구조를 반드시 지켜 블로그 글을 완성하세요.

━━━━━━━━━━━━━━━━━━━━━━
글 구조 (이 순서와 분량을 절대 지킬 것)
━━━━━━━━━━━━━━━━━━━━━━

## [제목] — 숫자나 핵심 키워드가 들어간 강렬한 제목

---

### 들어가며
- 첫 줄: 이 글 전체를 단 한 문장으로 압축한 핵심 요약 문장 (굵게 강조, 예: **"지금 강남 아파트 시장은 바닥을 다지고 있는가, 아니면 또 다른 하락의 전조인가."**)
- 분량: 반드시 280자 이상
- 독자에게 직접 말 거는 대화형 문장으로 시작
- 예시: "요즘 ~에 대한 문의가 부쩍 늘고 있습니다."
- 현재 시장 분위기를 생생하게 묘사
- 이 글에서 다룰 3가지 핵심 내용을 자연스럽게 예고
- 칼럼니스트 특유의 리듬감 있는 문체 유지

---

### ✅ 핵심 요약 3가지
✅ **핵심 1:** [수치·사실 포함한 2문장 요약]
✅ **핵심 2:** [수치·사실 포함한 2문장 요약]
✅ **핵심 3:** [수치·사실 포함한 2문장 요약]

---

### 📊 숫자로 보는 시장
📊 **① [실거래가 현황]**
[호갱노노·네이버 부동산 기준 단지명·평형·실거래 금액·거래 시점 → 전월 대비 변화 해설 3~4문장 → 출처 명기]

📊 **② [거래량·전세가율]**
[거래량 수치 + 전세가율 % → 갭투자 가능성·임차 시장 해설 3~4문장 → 출처 명기]

📊 **③ [외부 변수 수치]**
[금리·대출규제·입주물량 등 핵심 수치 → 시장에 미치는 영향 3~4문장 → 출처 명기]

---

### 핵심 1: [소제목 — 실거래가 분석]
- 분량: 반드시 420자 이상
- 호갱노노·네이버 부동산에서 확인한 실거래가를 단지명·면적·금액으로 직접 인용
- 데이터 → 해석 → 시사점 순서로 3~4단락 작성
- "이 수치가 의미하는 것은" 형식으로 분석 깊이 더하기
- 독자가 직접 활용할 수 있는 구체적 인사이트 포함

---

### 핵심 2: [소제목 — 시장 흐름 분석]
- 분량: 반드시 420자 이상
- 매수자·매도자·임차인 각 입장에서 현재 데이터가 의미하는 바 분석
- 과거 유사 국면과 비교하여 현재 위치 진단
- 수치 비교표 또는 전월·전년 대비 변화 흐름 서술

---

### 핵심 3: [소제목 — 전망 및 전략]
- 분량: 반드시 420자 이상
- 금리·정부정책·입주물량 등 외부 변수와 실거래가 연결 분석
- 낙관·중립·비관 시나리오 중 가장 가능성 높은 시나리오 근거와 함께 제시
- 독자가 지금 취할 수 있는 실질적 행동 전략 3가지 제안

---

### 마무리
- 분량: 반드시 220자 이상
- 전체 내용을 힘 있게 정리
- "결국 이 시장이 말하는 것은 ~입니다"로 시작
- 독자에게 실질적 행동 제안으로 마무리
- 강렬한 마지막 문장으로 인상을 남길 것

━━━━━━━━━━━━━━━━━━━━━━
필수 규칙 (위반 절대 금지)
━━━━━━━━━━━━━━━━━━━━━━
- 총 글자 수: 반드시 2600자 이상 3200자 이하 (공백·줄바꿈 제외)
- Q: 또는 Q. 로 시작하는 문장 절대 작성 금지
- 질문-답변(Q&A) 형식 절대 사용 금지
- 글자 수 표기 금지
- 섹션을 생략하거나 짧게 줄이는 것 금지
- 한국어로만 작성 (한자·일본어·중국어 절대 사용 금지)
- 수치 데이터 반드시 포함 (없으면 부동산 시장 일반 수치 활용)
- 히라가나·가타카나·漢字 등 비한국어 문자 출력 절대 금지"""


# ── AI 팀 함수 ────────────────────────────────────────────────────────────────
def run_search_team(keyword: str, api_key: str, rss_data, news_data, web_data=None, price_data=None):
    client = Groq(api_key=api_key)
    raw = format_research_data(rss_data, news_data, web_data or [], price_data or [])
    user_msg = (
        f"분석 키워드: {keyword}\n\n"
        f"--- 수집된 데이터 ---\n{raw}\n---\n\n"
        "위 데이터를 바탕으로 현황 분석과 미래 예측·가설을 모두 작성해 주세요.\n"
        "특히 호갱노노·네이버 부동산 실거래가 데이터를 최우선으로 활용하고,\n"
        "구체적인 단지명·면적·가격·거래 시점을 반드시 포함하세요."
    )
    stream = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": SEARCH_SYSTEM},
            {"role": "user",   "content": user_msg},
        ],
        stream=True,
        max_tokens=2500,
        temperature=0.4,
    )
    for chunk in stream:
        text = chunk.choices[0].delta.content
        if text:
            yield clean_text(text)


def run_blog_team(keyword: str, research: str, api_key: str):
    client = Groq(api_key=api_key)
    user_msg = (
        f"블로그 주제 키워드: {keyword}\n\n"
        f"--- 서치팀 분석 결과 ---\n{research}\n---\n\n"
        "위 자료를 바탕으로 블로그 글을 작성하세요.\n\n"
        "【필수 조건 — 반드시 준수】\n"
        "- 총 글자 수 2600자 이상 (공백 제외)\n"
        "- 들어가며 280자 이상\n"
        "- 핵심 1·2·3 각각 420자 이상\n"
        "- 마무리 220자 이상\n"
        "- Q: / Q. 형식 절대 사용 금지\n"
        "- Q&A 형식 절대 사용 금지\n"
        "- 각 섹션 절대 생략 금지\n"
        "- 호갱노노·네이버 부동산 실거래가 수치를 단지명·금액과 함께 반드시 인용\n"
        "- 단순 정보 나열 금지 — 데이터 → 해석 → 시사점 흐름으로 작성\n"
        "- 10년 경력 부동산 칼럼니스트 분석 문체"
    )
    stream = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": BLOG_SYSTEM},
            {"role": "user",   "content": user_msg},
        ],
        stream=True,
        max_tokens=6000,
        temperature=0.3,
    )
    for chunk in stream:
        text = chunk.choices[0].delta.content
        if text:
            yield clean_text(text)


# ── 사이드바 ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("""
    <div style='padding: 8px 0 20px 0;'>
        <div style='font-size:22px; font-weight:900; color:#191F28;'>🏠 부동산 AI</div>
        <div style='font-size:13px; color:#8B95A1; margin-top:4px;'>블로그 자동 생성 시스템</div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("<div style='font-size:13px; font-weight:700; color:#6B7684; margin-bottom:8px;'>API 설정</div>", unsafe_allow_html=True)
    saved_key = load_api_key()
    api_key = st.text_input(
        "Groq API Key",
        value=saved_key,
        type="password",
        placeholder="gsk_...",
        label_visibility="collapsed",
    )
    col_save, col_test = st.columns(2)
    with col_save:
        if st.button("💾 저장", use_container_width=True):
            if api_key:
                save_api_key(api_key)
                st.success("저장!")
            else:
                st.error("키 입력 필요")
    with col_test:
        if st.button("🔌 테스트", use_container_width=True):
            if not api_key:
                st.error("키 입력 필요")
            else:
                try:
                    Groq(api_key=api_key).chat.completions.create(
                        model="llama-3.3-70b-versatile",
                        messages=[{"role": "user", "content": "hi"}],
                        max_tokens=5,
                    )
                    st.success("✅ 연결!")
                except Exception as e:
                    st.error(f"❌ 오류")

    st.markdown("<hr style='border:none; border-top:1px solid #F2F4F6; margin:20px 0;'>", unsafe_allow_html=True)

    st.markdown("""
    <div style='font-size:13px; color:#8B95A1;'>
    <div style='font-weight:700; color:#191F28; margin-bottom:12px;'>작동 방식</div>
    <div style='margin-bottom:10px;'>
        <span style='background:#EBF3FE; color:#3182F6; font-size:11px; font-weight:700; padding:3px 8px; border-radius:20px;'>1단계</span>
        <div style='margin-top:6px; font-size:13px;'><b>🔍 서치팀</b></div>
        <div style='margin-top:3px; font-size:12px;'>뉴스·웹문서·RSS 수집<br>미래 예측 및 가설 도출</div>
    </div>
    <div>
        <span style='background:#E8F9F0; color:#1BB76E; font-size:11px; font-weight:700; padding:3px 8px; border-radius:20px;'>2단계</span>
        <div style='margin-top:6px; font-size:13px;'><b>✍️ 블로그팀</b></div>
        <div style='margin-top:3px; font-size:12px;'>들어가며 → 핵심요약<br>숫자분석 → 핵심1·2·3 → 마무리</div>
    </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("<hr style='border:none; border-top:1px solid #F2F4F6; margin:20px 0;'>", unsafe_allow_html=True)
    st.markdown("<div style='font-size:12px; color:#8B95A1;'>🔑 <a href='https://console.groq.com/keys' target='_blank' style='color:#3182F6;'>Groq API 키 무료 발급</a></div>", unsafe_allow_html=True)


# ── 메인 헤더 ─────────────────────────────────────────────────────────────────
st.markdown("""
<div class='toss-card' style='background: linear-gradient(135deg, #1B6EE0 0%, #3182F6 100%); color:white; padding:32px 36px;'>
    <div style='font-size:13px; font-weight:700; opacity:0.8; margin-bottom:8px; letter-spacing:1px;'>AI 에이전트</div>
    <div style='font-size:28px; font-weight:900; line-height:1.2;'>개인작업_블로그 작성</div>
</div>
""", unsafe_allow_html=True)

# ── 키워드 입력 ────────────────────────────────────────────────────────────────
st.markdown("<div style='font-size:15px; font-weight:700; color:#191F28; margin:8px 0 8px 0;'>키워드 입력</div>", unsafe_allow_html=True)
keyword = st.text_input(
    "keyword",
    placeholder="예: 강남 아파트,  전세사기,  재건축,  부동산 규제 ...",
    label_visibility="collapsed",
)
run_btn = st.button("🚀  블로그 생성 시작", type="primary", use_container_width=True)


# ── 실행 ──────────────────────────────────────────────────────────────────────
if run_btn:
    if not api_key:
        st.error("사이드바에서 Groq API 키를 먼저 입력해 주세요.")
        st.stop()
    if not keyword.strip():
        st.error("키워드를 입력해 주세요.")
        st.stop()

    kw = keyword.strip()
    st.markdown("<hr style='border:none; border-top:1px solid #E5E8EB; margin:24px 0 20px 0;'>", unsafe_allow_html=True)

    # ── STEP 0: 데이터 수집 ───────────────────────────────────────────────────
    st.markdown("""
    <div class='toss-card'>
        <div class='toss-tag'>STEP 0</div>
        <div class='toss-h2'>📡 데이터 수집</div>
        <div class='toss-body'>호갱노노·네이버 부동산 실거래가 + 뉴스·블로그·RSS 전방위 수집 중...</div>
    </div>
    """, unsafe_allow_html=True)

    with st.spinner("수집 중..."):
        rss_data   = fetch_rss(kw)
        news_data  = search_news(kw)
        web_data   = search_web_docs(kw)
        price_data = search_price_data(kw)

    total = len(rss_data) + len(news_data) + len(web_data) + len(price_data)
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.markdown(f"<div class='metric-card'><div class='metric-num'>{len(price_data)}</div><div class='metric-label'>실거래가</div></div>", unsafe_allow_html=True)
    with col2:
        st.markdown(f"<div class='metric-card'><div class='metric-num'>{len(news_data)}</div><div class='metric-label'>최신 뉴스</div></div>", unsafe_allow_html=True)
    with col3:
        st.markdown(f"<div class='metric-card'><div class='metric-num'>{len(web_data)}</div><div class='metric-label'>웹문서·블로그</div></div>", unsafe_allow_html=True)
    with col4:
        st.markdown(f"<div class='metric-card'><div class='metric-num'>{len(rss_data)}</div><div class='metric-label'>RSS 기사</div></div>", unsafe_allow_html=True)

    if total > 0:
        with st.expander(f"📂 수집된 원본 데이터 보기 (총 {total}건)"):
            st.text(format_research_data(rss_data, news_data, web_data, price_data)[:5000])

    st.markdown("<hr style='border:none; border-top:1px solid #E5E8EB; margin:20px 0;'>", unsafe_allow_html=True)

    # ── STEP 1: 서치팀 ────────────────────────────────────────────────────────
    st.markdown("""
    <div class='toss-card'>
        <div class='toss-tag'>STEP 1</div>
        <div class='toss-h2'>🔍 서치팀 — 현황 분석 + 미래 예측</div>
        <div class='toss-body'>수집 데이터 기반 심층 분석 및 시나리오 도출 중...</div>
    </div>
    """, unsafe_allow_html=True)

    try:
        research_text = st.write_stream(
            run_search_team(kw, api_key, rss_data, news_data, web_data, price_data)
        )
    except Exception as e:
        err = str(e)
        if "auth" in err.lower() or "invalid" in err.lower():
            st.error("❌ Groq API 키가 올바르지 않습니다. 사이드바에서 확인해 주세요.")
        elif "rate" in err.lower() or "quota" in err.lower():
            st.error("⏱️ 사용 한도 초과. 잠시 후 다시 시도해 주세요.")
        elif "connect" in err.lower() or "connection" in err.lower():
            st.error("🌐 연결 오류. 인터넷 연결을 확인하거나 잠시 후 다시 시도해 주세요.")
        else:
            st.error(f"서치팀 오류: {e}")
        st.stop()

    st.success("✅ 서치팀 분석 완료!")
    st.markdown("<hr style='border:none; border-top:1px solid #E5E8EB; margin:20px 0;'>", unsafe_allow_html=True)

    # ── STEP 2: 블로그팀 ──────────────────────────────────────────────────────
    st.markdown("""
    <div class='toss-card'>
        <div class='toss-tag-green'>STEP 2</div>
        <div class='toss-h2'>✍️ 블로그팀 — 전문 칼럼 작성</div>
        <div class='toss-body'>10년 경력 부동산 카피라이터가 글을 작성합니다...</div>
    </div>
    """, unsafe_allow_html=True)

    try:
        blog_text = st.write_stream(run_blog_team(kw, research_text, api_key))
    except Exception as e:
        err = str(e)
        if "auth" in err.lower() or "invalid" in err.lower():
            st.error("❌ Groq API 키가 올바르지 않습니다.")
        elif "rate" in err.lower() or "quota" in err.lower():
            st.error("⏱️ 사용 한도 초과. 잠시 후 다시 시도해 주세요.")
        elif "connect" in err.lower() or "connection" in err.lower():
            st.error("🌐 연결 오류. 잠시 후 다시 시도해 주세요.")
        else:
            st.error(f"블로그팀 오류: {e}")
        st.stop()

    char_count = len(blog_text.replace(" ", "").replace("\n", ""))
    st.markdown("<hr style='border:none; border-top:1px solid #E5E8EB; margin:20px 0;'>", unsafe_allow_html=True)

    # ── 완성 결과 카드 ────────────────────────────────────────────────────────
    st.markdown(f"""
    <div class='toss-card' style='border-left: 4px solid #1BB76E;'>
        <div class='toss-tag-green'>완성</div>
        <div class='toss-h2'>🎉 블로그 글 완성</div>
        <div class='toss-body'>총 <b style='color:#191F28;'>{char_count:,}자</b> (공백 제외) 작성되었습니다.</div>
    </div>
    """, unsafe_allow_html=True)

    # ── 다운로드 ──────────────────────────────────────────────────────────────
    col_dl1, col_dl2 = st.columns(2)
    with col_dl1:
        st.download_button(
            "💾 블로그 글 다운로드 (.txt)",
            data=strip_markdown(blog_text),
            file_name=f"블로그_{kw}.txt",
            mime="text/plain",
            use_container_width=True,
        )
    with col_dl2:
        full_report = (
            f"[키워드: {kw}]\n\n"
            f"=== 수집 데이터 ===\n{format_research_data(rss_data, news_data, web_data)}\n\n"
            f"=== 서치팀 분석 ===\n{strip_markdown(research_text)}\n\n"
            f"=== 블로그 글 ===\n{strip_markdown(blog_text)}"
        )
        st.download_button(
            "📋 전체 리포트 다운로드 (.txt)",
            data=full_report,
            file_name=f"리포트_{kw}.txt",
            mime="text/plain",
            use_container_width=True,
        )
