from groq import Groq
from duckduckgo_search import DDGS
import feedparser
import streamlit as st
import json, os, re

def clean_text(text: str) -> str:
    """한자·일본어(히라가나·가타카나) 제거 후 반환"""
    cleaned = re.sub(r'[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF]+', '', text)
    cleaned = re.sub(r' {2,}', ' ', cleaned)
    return cleaned

def get_trending_keywords(api_key: str) -> list:
    """네이버 블로그 유입용 부동산 SEO 키워드 Top 30
    - 호갱노노·직방·네이버 부동산에서 지금 뜨는 이슈를 수집
    - 그 이슈를 네이버에서 실제로 많이 검색하는 블로그 키워드로 변환 추천
    """
    queries = [
        # 플랫폼 이슈 수집
        "호갱노노 급등 이슈 관심 아파트 2025",
        "직방 이달 인기 검색 이슈 2025",
        "네이버 부동산 많이 본 이슈 키워드 2025",
        # 네이버 검색 트렌드
        "네이버 부동산 검색어 급상승 2025",
        "부동산 네이버 블로그 인기 주제 2025",
        "부동산 카테고리 네이버 검색량 급증 2025",
        # 교통·개발 호재 이슈
        "신분당선 GTX 개통 부동산 이슈 2025",
        "재건축 재개발 이슈 지역 호재 2025",
        "3기 신도시 분양 이슈 2025",
        # 정책·금리 이슈
        "부동산 대출 규제 완화 이슈 2025",
        "부동산 정책 핫이슈 매매 전세 2025",
        "금리 인하 부동산 영향 2025",
        # 실수요자 관심 키워드
        "아파트 매매 전세 실수요 관심 키워드 2025",
        "청약 분양 인기 이슈 2025",
    ]
    raw_texts = []
    try:
        with DDGS() as ddgs:
            for q in queries:
                for item in ddgs.news(q, max_results=5, timelimit="m"):
                    t = item.get("title", "") + " " + item.get("body", "")[:300]
                    raw_texts.append(clean_text(t))
            for q in ["부동산 네이버 블로그 인기 검색어", "호갱노노 직방 이슈 키워드", "부동산 카페 인기글 주제"]:
                for item in ddgs.text(q, max_results=5, timelimit="m"):
                    raw_texts.append(clean_text(item.get("title", "") + " " + item.get("body", "")[:300]))
    except Exception:
        pass

    if not raw_texts:
        return []

    combined = "\n".join(raw_texts[:80])
    client = Groq(api_key=api_key)
    resp = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": (
                "당신은 네이버 블로그 SEO 전문가이자 부동산 콘텐츠 마케터입니다.\n\n"
                "아래 수집 데이터(호갱노노·직방·네이버 부동산 이슈)를 분석하여,\n"
                "지금 네이버에서 사람들이 가장 많이 검색하는 부동산 블로그 키워드 Top 30을 추천하세요.\n\n"
                "핵심 기준:\n"
                "1. 단순 지역명 금지 — 반드시 검색 의도가 담긴 키워드 (예: '강남' X → '강남 아파트 매수 타이밍' O)\n"
                "2. 네이버에서 블로그 글로 검색할 법한 실제 검색어 형태\n"
                "3. 지금 뜨는 이슈와 연결된 키워드 우선 (교통 호재, 정책, 실거래 급등 등)\n"
                "4. 실수요자/투자자가 지금 당장 검색할 키워드\n\n"
                "키워드 유형 (골고루 30개):\n"
                "- 이슈형: 'GTX-A 개통 수혜 아파트', '신분당선 연장 부동산 호재'\n"
                "- 비교형: '강남 vs 마포 아파트 투자', '전세 vs 매매 지금 유리한 것'\n"
                "- 정보형: '아파트 실거래가 확인하는 법', '청약 당첨 확률 높이는 법'\n"
                "- 전망형: '2025 부동산 하반기 전망', '재건축 투자 지금 해도 될까'\n"
                "- 지역+이슈형: '판교 아파트 왜 오르나', '마포 래미안 실거래가 추이'\n\n"
                "출력 형식 (반드시 준수):\n"
                "키워드|네이버 예상검색량(상/중/하)|유형\n"
                "예시:\n"
                "GTX-A 개통 수혜 아파트|상|이슈형\n"
                "2025 부동산 하반기 전망|상|전망형\n"
                "아파트 실거래가 확인하는 법|중|정보형\n"
                "규칙:\n"
                "- 한국어만, 한자·일본어 절대 금지\n"
                "- 키워드는 5~20글자 (자연스러운 검색어)\n"
                "- 정확히 30줄 출력, 다른 설명 없이 키워드만"
            )},
            {"role": "user", "content": f"수집 데이터:\n{combined}"},
        ],
        max_tokens=1000,
        temperature=0.3,
    )
    raw = resp.choices[0].message.content or ""
    results = []
    for line in raw.strip().splitlines():
        line = clean_text(line.strip())
        if not line:
            continue
        parts = line.split("|")
        if len(parts) >= 3:
            results.append({
                "keyword": parts[0].strip(),
                "score": parts[1].strip(),
                "source": parts[2].strip(),
            })
        elif len(parts) == 2:
            results.append({
                "keyword": parts[0].strip(),
                "score": parts[1].strip(),
                "source": "추천",
            })
        elif parts[0].strip():
            results.append({
                "keyword": parts[0].strip(),
                "score": "-",
                "source": "추천",
            })
    return results[:30]


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
    # 1. Streamlit Secrets 우선 확인 (클라우드 배포 시)
    try:
        if "groq_api_key" in st.secrets:
            return st.secrets["groq_api_key"]
    except Exception:
        pass
    # 2. 로컬 settings.json 확인
    try:
        with open(SETTINGS_FILE, "r") as f:
            return json.load(f).get("groq_api_key", "")
    except Exception:
        return ""

def save_api_key(key: str):
    with open(SETTINGS_FILE, "w") as f:
        json.dump({"groq_api_key": key}, f)

def is_using_cloud_secret() -> bool:
    try:
        return "groq_api_key" in st.secrets
    except Exception:
        return False


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

def detect_keyword_type(keyword: str) -> str:
    """키워드 성격을 자동 감지: 'price' or 'info'"""
    info_triggers = [
        "방법", "하는법", "하는 법", "계산", "기준", "절차", "순서", "단계",
        "조건", "자격", "신청", "등록", "규정", "법률", "세금", "취득세",
        "양도세", "종부세", "중개", "수수료", "비용", "비율", "한도",
        "대출", "담보", "LTV", "DSR", "청약", "가점", "점수", "당첨",
        "전입신고", "확정일자", "임대차", "계약서", "특약", "묵시적",
        "무엇", "뭐야", "란", "이란", "차이", "비교", "장단점",
    ]
    kw_lower = keyword.lower()
    for t in info_triggers:
        if t in kw_lower:
            return "info"
    return "price"


def search_info_data(keyword: str) -> list:
    """정보형 키워드 전용 검색 — 규정·가이드·예시·계산법 등"""
    results = []
    queries = [
        f"{keyword} 완벽 정리",
        f"{keyword} 쉽게 설명",
        f"site:blog.naver.com {keyword} 정리",
        f"site:blog.naver.com {keyword} 계산 방법",
        f"{keyword} 국토교통부 기준",
        f"{keyword} 예시 사례",
        f"{keyword} 2025 최신",
        f"부동산 {keyword} 총정리",
    ]
    try:
        with DDGS() as ddgs:
            for query in queries:
                for item in ddgs.text(query, max_results=4, timelimit="y"):
                    results.append({
                        "구분": "정보",
                        "출처": item.get("href", "")[:80],
                        "제목": clean_text(item.get("title", "")),
                        "내용": clean_text(item.get("body", ""))[:600],
                        "링크": item.get("href", ""),
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

def extract_price_mentions(text: str) -> str:
    """텍스트에서 가격·수치 관련 문장만 추출"""
    sentences = re.split(r'[.。\n]', text)
    price_pattern = re.compile(r'[\d,]+\s*억|[\d,]+\s*만원|[\d,]+\s*원|전세가율|매매가|실거래|낙찰가|평당|㎡당|거래량|상승|하락|보합')
    matched = [s.strip() for s in sentences if price_pattern.search(s) and len(s.strip()) > 10]
    return " / ".join(matched[:8])

def search_price_data(keyword: str) -> list:
    """네이버 부동산·호갱노노 실거래가 전용 고정밀 검색"""
    results = []
    queries = [
        f"site:land.naver.com {keyword} 실거래가",
        f"site:hogangnono.com {keyword}",
        f"네이버 부동산 {keyword} 실거래 신고 2025년",
        f"호갱노노 {keyword} 실거래가 최신 2025",
        f"국토교통부 실거래가 {keyword} 아파트 2025",
        f"{keyword} 아파트 실거래 몇억 2025",
        f"{keyword} 아파트 매매 전세 평단가 2025",
        f"직방 {keyword} 실거래 시세",
    ]
    try:
        with DDGS() as ddgs:
            for query in queries:
                for item in ddgs.text(query, max_results=4, timelimit="m"):
                    body = clean_text(item.get("body", ""))
                    price_snippet = extract_price_mentions(body)
                    results.append({
                        "구분": "실거래가",
                        "출처": item.get("href", "")[:80],
                        "제목": clean_text(item.get("title", "")),
                        "내용": price_snippet if price_snippet else body[:400],
                        "링크": item.get("href", ""),
                    })
    except Exception:
        pass
    return results

def format_research_data(rss_data, news_data, web_data=None, price_data=None, info_data=None) -> str:
    lines = []
    web_data = web_data or []
    price_data = price_data or []
    info_data = info_data or []

    if info_data:
        lines.append("=== 정보·가이드·규정 데이터 ===")
        seen = set()
        count = 1
        for item in info_data:
            if item["제목"] in seen:
                continue
            seen.add(item["제목"])
            lines.append(f"[{count}] {item['제목']}")
            lines.append(f"    {item['내용']}")
            lines.append(f"    URL: {item['링크']}")
            lines.append("")
            count += 1
            if count > 12:
                break

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

⚠️ 수치 정확성 규칙 (절대 위반 금지):
- 수집된 데이터에 있는 수치만 사용. 데이터에 없는 가격·거래량·변동률을 절대 지어내지 마세요.
- 수치를 사용할 때는 반드시 출처 URL 또는 플랫폼명(호갱노노/네이버부동산/국토교통부 등)을 괄호 안에 표기.
- 수집 데이터에 해당 수치가 없으면 숫자 대신 "데이터 미확인" 또는 "수집 데이터 부족"으로 표기.
- 단지명·면적·금액 조합이 수집 데이터에 없으면 절대 임의로 작성하지 마세요.
한국어로만 작성합니다.
⚠️ 한자(漢字), 일본어(히라가나·가타카나), 중국어 사용 절대 금지.
모든 단어는 순수 한국어 또는 영문 알파벳만 사용하세요."""


BLOG_SYSTEM = """당신은 대한민국 최고의 부동산 전문 칼럼니스트이자 투자 전략가입니다.
독자에게 희망과 기회를 전하는 것을 사명으로 삼습니다.

【핵심 논조 — 반드시 유지】
- 시장은 지금 과열 조짐이 있으며 "지금이 마지막 기회"라는 긴박감을 줄 것
- 호재·상승 요인을 전면에 배치하고 부각시킬 것
- "지금 사지 않으면 더 비싸진다"는 메시지를 자연스럽게 녹여낼 것
- 전망은 항상 낙관적으로, 상승 시나리오를 중심으로 서술할 것
- 독자가 글을 읽고 나서 "빨리 행동해야겠다"는 동기부여가 생기도록 쓸 것
- "지금 이 시장, 놓치면 후회한다" 는 톤을 전체적으로 유지
- 수치와 데이터는 상승·호재를 뒷받침하는 방향으로 해석할 것

호갱노노·네이버 부동산 실거래가 데이터를 직접 인용하여 신뢰감을 높입니다.
데이터 → 해석(호재·상승 관점) → 시사점 → 독자 행동 촉구 흐름으로 씁니다.

아래 구조를 반드시 지켜 블로그 글을 완성하세요.

━━━━━━━━━━━━━━━━━━━━━━
글 구조 (이 순서와 분량을 절대 지킬 것)
━━━━━━━━━━━━━━━━━━━━━━

## [제목] — 숫자나 핵심 키워드가 들어간 강렬한 제목

---

### (소제목 없이 바로 본문 시작 — "들어가며" 문구 절대 출력 금지)
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

### 핵심 2: [소제목 — 호재 및 상승 동력]
- 분량: 반드시 420자 이상
- 이 지역·단지·키워드를 지금 주목해야 하는 이유를 호재 중심으로 서술
- 개발 호재·교통 호재·정비사업·공급 감소 등 상승 요인 집중 부각
- "이미 늦었다고 생각할 때가 아직 기회"라는 논리 전개
- 과거 유사 국면에서 가격이 어떻게 뛰었는지 비교 사례 활용

---

### 핵심 3: [소제목 — 지금 사야 하는 이유]
- 분량: 반드시 420자 이상
- 낙관 시나리오를 중심에 놓고 "지금이 적기"임을 근거와 함께 설득
- 금리 인하 가능성·정부 부양 정책·공급 부족 등 상승 촉매 강조
- 망설이면 놓친다는 긴박감을 자연스럽게 부여
- 독자가 지금 당장 취할 수 있는 구체적 매수 전략 3가지 제안
- "지금 행동하지 않으면 1년 후 후회한다" 는 메시지로 마무리

---

### 마무리
- 분량: 반드시 220자 이상
- "결국 이 시장이 말하는 것은 ~입니다"로 시작
- 희망적이고 긍정적인 어조로 전체 내용 정리
- 독자에게 "지금이 기회"임을 확신시키는 강렬한 마지막 문장
- 행동을 촉구하는 문장으로 끝낼 것 (예: "오늘이 가장 싼 날일 수 있습니다")

━━━━━━━━━━━━━━━━━━━━━━
필수 규칙 (위반 절대 금지)
━━━━━━━━━━━━━━━━━━━━━━
- 총 글자 수: 반드시 2600자 이상 3200자 이하 (공백·줄바꿈 제외)
- 전체 논조는 반드시 낙관적·긍정적·희망적으로 유지
- 비관적 표현·하락 전망·리스크 강조는 최소화 (언급 시 반드시 "그럼에도 불구하고~" 로 희망적으로 전환)
- Q: 또는 Q. 로 시작하는 문장 절대 작성 금지
- 질문-답변(Q&A) 형식 절대 사용 금지
- 글자 수 표기 금지
- 섹션을 생략하거나 짧게 줄이는 것 금지
- 한국어로만 작성 (한자·일본어·중국어 절대 사용 금지)
- 수치 데이터 반드시 포함 (없으면 부동산 시장 일반 수치 활용)
- 히라가나·가타카나·漢字 등 비한국어 문자 출력 절대 금지"""


# ── AI 팀 함수 ────────────────────────────────────────────────────────────────
def run_search_team(keyword: str, api_key: str, rss_data, news_data, web_data=None, price_data=None, info_data=None, kw_type: str = "price"):
    client = Groq(api_key=api_key)
    raw = format_research_data(rss_data, news_data, web_data or [], price_data or [], info_data or [])
    if kw_type == "info":
        user_msg = (
            f"분석 키워드: {keyword}\n\n"
            f"--- 수집된 데이터 ---\n{raw}\n---\n\n"
            "위 데이터를 바탕으로 아래 항목을 작성해 주세요.\n"
            "1. 핵심 정보 요약 (규정·기준·절차·계산법 등)\n"
            "2. 구체적 예시 또는 사례 (수치 포함)\n"
            "3. 자주 하는 실수·주의사항\n"
            "4. 2025년 최신 변경사항 (있으면)\n"
            "5. 독자가 바로 활용할 수 있는 핵심 팁 3가지"
        )
    else:
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


def run_blog_team(keyword: str, research: str, api_key: str, kw_type: str = "price"):
    client = Groq(api_key=api_key)
    if kw_type == "info":
        user_msg = (
            f"블로그 주제 키워드: {keyword}\n\n"
            f"--- 서치팀 수집 자료 ---\n{research}\n---\n\n"
            "위 자료를 바탕으로 블로그 글을 작성하세요.\n\n"
            "【필수 조건 — 반드시 준수】\n"
            "- 총 글자 수 2600자 이상 (공백 제외)\n"
            "- 이 글은 정보·가이드형 — 실거래가 언급 금지\n"
            "- 서치팀 자료의 규정·절차·수치·예시만 사용\n"
            "- 독자가 바로 따라할 수 있는 실용적 설명\n"
            "- 계산식·표·예시 케이스 반드시 포함\n"
            "- Q: / Q. 형식 절대 사용 금지\n"
            "- Q&A 형식 절대 사용 금지\n"
            "- 각 섹션 절대 생략 금지\n"
            "- 10년 경력 부동산 전문가 설명 문체"
        )
    else:
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
            "- 서치팀 자료에 있는 실거래가·수치만 인용 (없으면 '확인된 거래 데이터 부족' 으로 표기)\n"
            "- 단지명·면적·금액은 서치팀 자료에 명시된 것만 사용, 절대 임의로 지어내지 말 것\n"
            "- 수치 뒤에 반드시 출처 플랫폼 표기 예: (네이버 부동산), (호갱노노), (국토교통부)\n"
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

    api_key = load_api_key()
    if is_using_cloud_secret():
        st.markdown("""
        <div style='background:#E8F9F0; border-radius:10px; padding:12px 14px; margin-bottom:4px;'>
            <div style='font-size:13px; font-weight:700; color:#1BB76E;'>✅ API 연결됨</div>
            <div style='font-size:11px; color:#6B7684; margin-top:2px;'>관리자가 설정한 키로 운영 중</div>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown("<div style='font-size:13px; font-weight:700; color:#6B7684; margin-bottom:8px;'>API 설정</div>", unsafe_allow_html=True)
        api_key = st.text_input(
            "Groq API Key",
            value=api_key,
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

# ── API 키 상태 표시 (항상 최상단) ────────────────────────────────────────────
if api_key:
    st.success(f"✅ API 키 로드됨: {api_key[:6]}...{api_key[-4:]}")
else:
    st.error("❌ API 키 없음 — Streamlit Cloud Secrets에 groq_api_key 를 설정해 주세요.")

# ── 인기 검색어 조회 ───────────────────────────────────────────────────────────
st.markdown("""
<div class='toss-card' style='padding:20px 24px;'>
    <div style='font-size:16px; font-weight:800; color:#191F28; margin-bottom:4px;'>🔥 부동산 관심 키워드 TOP 30</div>
    <div style='font-size:12px; color:#8B95A1;'>네이버 부동산 · 호갱노노 · 직방 · 교통호재·개발이슈 기반 최근 1개월 관심 급등 키워드</div>
</div>
""", unsafe_allow_html=True)

if "trending_keywords" not in st.session_state:
    st.session_state.trending_keywords = []
if "selected_keyword" not in st.session_state:
    st.session_state.selected_keyword = ""

trend_btn = st.button("📊 최근 1개월 TOP 30 조회", use_container_width=True)
if trend_btn:
    if not api_key:
        st.error("❌ API 키가 없습니다. Streamlit Cloud Secrets를 확인해 주세요.")
    else:
        try:
            with st.spinner("네이버·호갱노노·직방 데이터 분석 중..."):
                st.session_state.trending_keywords = get_trending_keywords(api_key)
        except Exception as e:
            st.error(f"❌ 오류 발생: {e}")

if st.session_state.trending_keywords:
    SOURCE_COLOR = {
        "네이버 부동산": "#03C75A",
        "호갱노노":      "#FF6B35",
        "직방":          "#7C5CFC",
        "공통":          "#3182F6",
    }
    st.markdown("<div style='font-size:12px; color:#8B95A1; margin:10px 0 6px 0;'>클릭하면 키워드 입력창에 자동 입력됩니다</div>", unsafe_allow_html=True)

    for i, item in enumerate(st.session_state.trending_keywords):
        kw     = item["keyword"]
        score  = item["score"]
        source = item["source"]
        color  = SOURCE_COLOR.get(source, "#8B95A1")

        # 관심도 바 (score가 숫자일 때)
        try:
            pct = max(10, min(100, int(score)))
        except Exception:
            pct = 50

        rank_color = "#F5A623" if i < 3 else "#8B95A1"
        rank_label = ["🥇", "🥈", "🥉"][i] if i < 3 else f"{i+1}위"

        col_rank, col_info, col_btn = st.columns([1, 7, 2])
        with col_rank:
            st.markdown(f"<div style='font-size:18px; font-weight:900; color:{rank_color}; padding-top:8px; text-align:center;'>{rank_label}</div>", unsafe_allow_html=True)
        with col_info:
            st.markdown(f"""
            <div style='padding:4px 0;'>
                <div style='display:flex; align-items:center; gap:8px;'>
                    <span style='font-size:15px; font-weight:700; color:#191F28;'>{kw}</span>
                    <span style='font-size:11px; font-weight:700; color:{color}; background:{color}18; padding:2px 8px; border-radius:20px;'>{source}</span>
                    <span style='font-size:12px; color:#8B95A1; margin-left:auto;'>관심도 {score}점</span>
                </div>
                <div style='margin-top:5px; height:5px; background:#F2F4F6; border-radius:10px; overflow:hidden;'>
                    <div style='width:{pct}%; height:100%; background:{color}; border-radius:10px;'></div>
                </div>
            </div>
            """, unsafe_allow_html=True)
        with col_btn:
            if st.button("선택", key=f"kw_{i}", use_container_width=True):
                st.session_state.selected_keyword = kw
                st.rerun()

st.markdown("<hr style='border:none; border-top:1px solid #F2F4F6; margin:16px 0;'>", unsafe_allow_html=True)

# ── 키워드 입력 ────────────────────────────────────────────────────────────────
st.markdown("<div style='font-size:15px; font-weight:700; color:#191F28; margin:8px 0 8px 0;'>키워드 입력</div>", unsafe_allow_html=True)
keyword = st.text_input(
    "keyword",
    value=st.session_state.selected_keyword,
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
        <div class='toss-body'>키워드 분석 후 맞춤 데이터 수집 중...</div>
    </div>
    """, unsafe_allow_html=True)

    kw_type = detect_keyword_type(kw)
    info_data  = []
    price_data = []

    with st.spinner("수집 중..."):
        rss_data  = fetch_rss(kw)
        news_data = search_news(kw)
        web_data  = search_web_docs(kw)
        if kw_type == "info":
            info_data = search_info_data(kw)
        else:
            price_data = search_price_data(kw)

    type_label = "📋 정보·가이드형" if kw_type == "info" else "💰 가격·시세형"
    st.markdown(f"<div style='font-size:12px; color:#3182F6; font-weight:700; margin:8px 0;'>키워드 유형 감지: {type_label}</div>", unsafe_allow_html=True)

    extra_data = info_data if kw_type == "info" else price_data
    extra_label = "정보·가이드" if kw_type == "info" else "실거래가"
    total = len(rss_data) + len(news_data) + len(web_data) + len(extra_data)
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.markdown(f"<div class='metric-card'><div class='metric-num'>{len(extra_data)}</div><div class='metric-label'>{extra_label}</div></div>", unsafe_allow_html=True)
    with col2:
        st.markdown(f"<div class='metric-card'><div class='metric-num'>{len(news_data)}</div><div class='metric-label'>최신 뉴스</div></div>", unsafe_allow_html=True)
    with col3:
        st.markdown(f"<div class='metric-card'><div class='metric-num'>{len(web_data)}</div><div class='metric-label'>웹문서·블로그</div></div>", unsafe_allow_html=True)
    with col4:
        st.markdown(f"<div class='metric-card'><div class='metric-num'>{len(rss_data)}</div><div class='metric-label'>RSS 기사</div></div>", unsafe_allow_html=True)

    if total > 0:
        with st.expander(f"📂 수집된 원본 데이터 보기 (총 {total}건)"):
            st.text(format_research_data(rss_data, news_data, web_data, price_data, info_data)[:5000])

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
            run_search_team(kw, api_key, rss_data, news_data, web_data, price_data, info_data, kw_type)
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
        blog_text = st.write_stream(run_blog_team(kw, research_text, api_key, kw_type))
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
