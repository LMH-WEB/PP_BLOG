from groq import Groq
from duckduckgo_search import DDGS
import feedparser
import streamlit as st
import json, os, re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

def clean_text(text: str) -> str:
    """한자·일본어(히라가나·가타카나) 제거 후 반환"""
    cleaned = re.sub(r'[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF]+', '', text)
    cleaned = re.sub(r' {2,}', ' ', cleaned)
    return cleaned

def get_trending_keywords(api_key: str, status_fn=None) -> list:
    """네이버 블로그 유입용 부동산 SEO 키워드 Top 30"""
    def _log(msg):
        if status_fn:
            status_fn(msg)

    queries = [
        "GTX 개통 역세권 부동산 호재 2025",
        "재건축 재개발 이슈 지역 호재 2025",
        "부동산 정책 핫이슈 매매 전세 2025",
        "아파트 청약 분양 인기 이슈 2025",
        "국가철도망 신설 노선 수혜 아파트 2025",
    ]
    text_queries = [
        "부동산 네이버 블로그 인기 검색어 2025",
        "수도권 지하철 연장 개통 부동산 블로그",
    ]
    raw_texts = []
    _log("🌐 최신 이슈 수집 중...")
    try:
        with DDGS() as ddgs:
            for q in queries:
                try:
                    for item in ddgs.news(q, max_results=2, timelimit="m"):
                        t = item.get("title", "") + " " + item.get("body", "")[:300]
                        raw_texts.append(clean_text(t))
                except Exception:
                    continue
            for q in text_queries:
                try:
                    for item in ddgs.text(q, max_results=2, timelimit="m"):
                        raw_texts.append(clean_text(item.get("title", "") + " " + item.get("body", "")[:300]))
                except Exception:
                    continue
    except Exception:
        pass

    if raw_texts:
        combined = "수집된 최신 이슈 데이터:\n" + "\n".join(raw_texts[:40])
    else:
        combined = "※ 실시간 웹 데이터 수집 불가 — AI 자체 지식 기반으로 2025년 현재 네이버 부동산 트렌드를 분석하여 키워드를 추천하세요."

    _log("🤖 AI 키워드 분석 중...")
    client = Groq(api_key=api_key)
    resp = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": (
                "당신은 네이버 블로그 SEO 전문가이자 부동산 콘텐츠 마케터입니다.\n\n"
                "아래 데이터를 바탕으로 키워드를 두 그룹으로 나누어 각각 정확히 15개씩 추천하세요.\n"
                "실시간 데이터가 없으면 2025년 현재 한국 부동산 시장 지식을 활용하세요.\n\n"
                "=== 그룹 A: 지하철·국가철도망 호재 키워드 15개 ===\n"
                "- 신설 노선·연장 개통·역세권 수혜와 직접 연결된 키워드\n"
                "- 예시: 'GTX-A 수혜 아파트 매수 타이밍', '위례과천선 역세권 투자 전략',\n"
                "  '신분당선 연장 부동산 호재', '국가철도망 개통 전 역세권 아파트',\n"
                "  '수도권 전철 연장 수혜 지역'\n\n"
                "=== 그룹 B: 사람들이 진짜 궁금해하는 부동산 키워드 15개 ===\n"
                "- 실수요자·투자자가 네이버에서 실제로 검색하는 생생한 키워드\n"
                "- 예시: '전세사기 안 당하는 법', '아파트 청약 가점 계산법',\n"
                "  '2025 부동산 하반기 전망', '재건축 투자 지금 해도 될까',\n"
                "  '갭투자 지금 괜찮을까', '취득세 계산하는 법'\n\n"
                "공통 기준:\n"
                "1. 단순 지역명 금지 — 검색 의도가 담긴 키워드만 (예: '강남' X → '강남 아파트 매수 타이밍' O)\n"
                "2. 네이버에서 블로그 글로 검색할 법한 실제 검색어 형태\n"
                "3. 키워드는 5~20글자 (자연스러운 검색어)\n\n"
                "출력 형식 (반드시 이 형식 그대로):\n"
                "[철도호재]\n"
                "키워드|상/중/하|유형\n"
                "...(15줄)\n"
                "[부동산궁금]\n"
                "키워드|상/중/하|유형\n"
                "...(15줄)\n\n"
                "규칙:\n"
                "- [철도호재] 와 [부동산궁금] 헤더 반드시 출력\n"
                "- 각 그룹 정확히 15줄\n"
                "- 한국어만, 한자·일본어 절대 금지\n"
                "- 헤더와 키워드 외 다른 설명 일절 출력 금지"
            )},
            {"role": "user", "content": combined},
        ],
        max_tokens=1200,
        temperature=0.3,
    )
    raw = resp.choices[0].message.content or ""
    results = []
    current_category = "부동산궁금"
    for line in raw.strip().splitlines():
        line = clean_text(line.strip())
        if not line:
            continue
        if line.startswith("[철도호재]"):
            current_category = "철도호재"
            continue
        if line.startswith("[부동산궁금]"):
            current_category = "부동산궁금"
            continue
        parts = line.split("|")
        if len(parts) >= 3:
            results.append({
                "keyword":  parts[0].strip(),
                "score":    parts[1].strip(),
                "source":   parts[2].strip(),
                "category": current_category,
            })
        elif len(parts) == 2:
            results.append({
                "keyword":  parts[0].strip(),
                "score":    parts[1].strip(),
                "source":   "추천",
                "category": current_category,
            })
        elif parts[0].strip():
            results.append({
                "keyword":  parts[0].strip(),
                "score":    "-",
                "source":   "추천",
                "category": current_category,
            })
    return results[:30]


def strip_markdown(text: str) -> str:
    """다운로드용 txt에서 마크다운 기호 제거"""
    text = re.sub(r'^[-─━=]{2,}\s*$', '', text, flags=re.MULTILINE)
    text = re.sub(r'^#{1,6}\s*', '', text, flags=re.MULTILINE)
    text = re.sub(r'\*{1,3}(.+?)\*{1,3}', r'\1', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


# ── 블로그 저장소 ──────────────────────────────────────────────────────────────
ARCHIVE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "블로그_저장소")
os.makedirs(ARCHIVE_DIR, exist_ok=True)


def auto_save_blog(keyword: str, research: str, blog: str) -> str:
    """블로그 글을 저장소에 자동 저장, 저장된 파일명 반환"""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_kw = re.sub(r'[\\/:*?"<>|]', '_', keyword)[:30]
    fname = f"{ts}_{safe_kw}.txt"
    fpath = os.path.join(ARCHIVE_DIR, fname)
    char_count = len(blog.replace(" ", "").replace("\n", ""))
    content = (
        f"[키워드: {keyword}]\n"
        f"[생성일시: {datetime.now().strftime('%Y-%m-%d %H:%M')}]\n"
        f"[글자수: {char_count:,}자]\n"
        f"{'='*60}\n\n"
        f"=== 서치팀 분석 ===\n{strip_markdown(research)}\n\n"
        f"{'='*60}\n\n"
        f"=== 블로그 글 ===\n{strip_markdown(blog)}"
    )
    with open(fpath, "w", encoding="utf-8") as f:
        f.write(content)
    return fname


def load_archive() -> list:
    """저장소 파일 목록 반환 (최신순)"""
    if not os.path.exists(ARCHIVE_DIR):
        return []
    items = []
    for fname in sorted(os.listdir(ARCHIVE_DIR), reverse=True):
        if not fname.endswith(".txt"):
            continue
        fpath = os.path.join(ARCHIVE_DIR, fname)
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                lines = [f.readline().strip() for _ in range(3)]
            keyword  = lines[0].removeprefix("[키워드: ").removesuffix("]") if lines[0] else fname
            date_str = lines[1].removeprefix("[생성일시: ").removesuffix("]") if lines[1] else ""
            char_str = lines[2].removeprefix("[글자수: ").removesuffix("]") if lines[2] else ""
            items.append({"fname": fname, "fpath": fpath,
                          "keyword": keyword, "date": date_str, "chars": char_str})
        except Exception:
            continue
    return items


def read_archive_file(fpath: str) -> str:
    try:
        with open(fpath, "r", encoding="utf-8") as f:
            return f.read()
    except Exception:
        return ""


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
        f"{keyword} 매매 전세 동향 2025",
        f"{keyword} 부동산 실거래 뉴스",
        f"국토교통부 {keyword} 발표",
        f"{keyword} 아파트 분양 청약 2025",
    ]
    try:
        with DDGS() as ddgs:
            for query in queries:
                for item in ddgs.news(query, max_results=5, timelimit="m"):
                    results.append({
                        "구분": "뉴스",
                        "출처": item.get("source", ""),
                        "제목": clean_text(item.get("title", "")),
                        "내용": clean_text(item.get("body", ""))[:400],
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


def detect_railway_keyword(keyword: str) -> bool:
    """키워드에 철도·노선 관련 단어 포함 여부 감지"""
    railway_triggers = [
        "선", "철도", "GTX", "지하철", "역세권", "노선", "개통", "연장",
        "광역급행", "KTX", "SRT", "위례", "과천", "신분당", "신안산",
        "국가철도", "역", "환승", "급행", "트램", "경전철",
    ]
    for t in railway_triggers:
        if t in keyword:
            return True
    return False


def search_railway_data(keyword: str) -> list:
    """철도·노선 키워드 전용 고정밀 검색 — 노선 정보·개통일·역세권 수혜 아파트"""
    results = []
    queries = [
        f"{keyword} 노선도 역 위치 개통 일정",
        f"{keyword} 수혜 아파트 단지 역세권",
        f"{keyword} 개통 부동산 영향 시세 변화",
        f"국가철도망 {keyword} 확정 노선",
        f"{keyword} 역 주변 아파트 시세 전망 2025",
        f"국토교통부 {keyword} 철도 계획 발표",
        f"site:blog.naver.com {keyword} 역세권 아파트 투자",
        f"site:cafe.naver.com {keyword} 개통 부동산",
        f"{keyword} 신설역 주변 매매 전세 동향 2025",
    ]
    news_queries = [
        f"{keyword} 철도 개통 부동산 뉴스 2025",
        f"국가철도망 {keyword} 최신 뉴스",
        f"{keyword} 역세권 아파트 시세 상승",
    ]
    try:
        with DDGS() as ddgs:
            for query in queries:
                for item in ddgs.text(query, max_results=5, timelimit="y"):
                    results.append({
                        "구분": "철도정보",
                        "출처": item.get("href", "")[:80],
                        "제목": clean_text(item.get("title", "")),
                        "내용": clean_text(item.get("body", ""))[:600],
                        "링크": item.get("href", ""),
                    })
            for query in news_queries:
                for item in ddgs.news(query, max_results=5, timelimit="m"):
                    results.append({
                        "구분": "철도뉴스",
                        "출처": item.get("source", ""),
                        "제목": clean_text(item.get("title", "")),
                        "내용": clean_text(item.get("body", ""))[:400],
                        "날짜": item.get("date", ""),
                        "링크": item.get("url", ""),
                    })
    except Exception:
        pass
    return results


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
        f"site:blog.naver.com {keyword} 매매 전세 시세",
        f"site:cafe.naver.com {keyword} 부동산 투자 분석",
        f"{keyword} 아파트 호재 개발 계획 2025",
        f"네이버 부동산 {keyword} 시세 조회",
        f"{keyword} 부동산 실거래 신고 2025 최신",
    ]
    try:
        with DDGS() as ddgs:
            for query in queries:
                for item in ddgs.text(query, max_results=4, timelimit="m"):
                    results.append({
                        "구분": "웹문서",
                        "출처": item.get("href", "")[:80],
                        "제목": clean_text(item.get("title", "")),
                        "내용": clean_text(item.get("body", ""))[:500],
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

def format_research_data(rss_data, news_data, web_data=None, price_data=None, info_data=None, railway_data=None) -> str:
    lines = []
    web_data = web_data or []
    price_data = price_data or []
    info_data = info_data or []
    railway_data = railway_data or []

    if railway_data:
        lines.append("=== 국가철도망·노선·역세권 데이터 ===")
        seen = set()
        count = 1
        for item in railway_data:
            if item["제목"] in seen:
                continue
            seen.add(item["제목"])
            lines.append(f"[{count}] [{item['구분']}] {item['제목']}")
            lines.append(f"    {item['내용']}")
            lines.append(f"    URL: {item['링크']}")
            lines.append("")
            count += 1
            if count > 15:
                break

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

수집된 데이터와 AI 학습 지식을 모두 활용하여 아래 항목을 빠짐없이 작성하세요.

【필수 출력 — 실거래가 비교 테이블】
키워드와 관련된 대표 아파트 3~5개를 반드시 아래 형식으로 출력하세요.
수집 데이터에 없으면 AI 학습 지식을 활용하되 반드시 (AI추정) 표기:

| 단지명 | 전용면적 | 2023년 시세 | 현재(2025) 시세 | 변동률 | 전세가율 |
|-------|---------|------------|----------------|--------|---------|
| 예시아파트 | 84㎡ | 8억 | 10.5억 | +31% | 52% |

【실거래가 분석】
1. 대표 단지명·면적(평형)·실거래 금액·거래 시점 최소 3건 이상 명시
   - 2023년 vs 현재(2024~2025) 가격 비교 (금액 + 변동률 % 반드시 포함)
   - 직전 고점 대비 현재 위치 분석 (ex: 고점 대비 -15% 수준, 회복 중)
   - 전세가율 % 수치와 갭 투자 가능 여부
2. 매매가·전세가 변동률 (전년 대비 % 수치 — 없으면 AI 추정치 + (AI추정) 표기)
3. 거래량 증감 (최근 3개월 추이)

【현황 분석】
4. 핵심 이슈 5가지 — 각각 구체적 수치·날짜·단지명 포함
5. 상승/하락 촉매 요인 분석 (정책·금리·입주물량·개발 호재)
6. 유사 시기·유사 노선/지역 비교 사례 (과거 GTX-A/신분당선/9호선 개통 전후 사례 등)

【미래 예측 및 가설】
7. 향후 3~6개월 시나리오 3가지 (낙관/중립/비관 — 각 시나리오에 구체적 가격 예측 수치 포함)
8. 핵심 가설 3가지 ("~한다면 ~% 상승/하락할 것이다" 형식으로 수치 포함)
9. 지금 당장 주목할 매수 포인트 Top 3 (단지명 또는 역세권 명시)

⚠️ 작성 규칙:
- 수집 데이터 우선 사용. 없으면 AI 학습 지식으로 채우되 반드시 (AI추정) 표기.
- "데이터 미확인"으로 비워두는 것 금지 — 반드시 AI 추정이라도 구체적 수치 제시.
- 수치 뒤 출처 표기: (호갱노노), (국토교통부), (네이버부동산), (AI추정) 중 하나 필수.
- 한국어만 사용. 한자·일본어·중국어 절대 금지."""


BLOG_SYSTEM = """당신은 대한민국 최고의 부동산 전문 칼럼니스트이자 투자 전략가입니다.
독자에게 구체적인 수치와 실거래 사례를 근거로 투자 판단 정보를 제공하는 것이 사명입니다.

【핵심 원칙 — 반드시 준수】
- 모든 주장에는 반드시 구체적 수치·단지명·날짜·% 변동률이 뒤따라야 함
- "많이 올랐다", "크게 상승했다" 같은 추상적 표현 금지 → "X아파트 84㎡가 2023년 8억에서 2025년 10.5억으로 +31% 상승"처럼 구체적으로
- 서치팀 자료의 데이터를 최우선 인용, 없으면 AI 학습 지식 활용 + (AI추정) 명기
- 호재·상승 요인을 데이터로 뒷받침하며 독자가 "빨리 행동해야겠다"는 동기부여가 생기도록
- 수치와 사례는 상승·호재를 뒷받침하는 방향으로 해석

아래 구조를 반드시 지켜 블로그 글을 완성하세요.

━━━━━━━━━━━━━━━━━━━━━━
글 구조 (이 순서·형식 절대 준수)
━━━━━━━━━━━━━━━━━━━━━━

## [제목] — 구체적 수치 또는 단지명이 들어간 강렬한 제목
예시: "GTX-C 수혜 수원 영통 아파트, 2년 새 +28%… 개통 전 마지막 기회인가"

---

### (소제목 없이 바로 본문 시작)
**[이 글 전체를 압축한 핵심 문장 — 굵게 강조]**
- 분량: 280자 이상
- 독자에게 직접 말 거는 도입 (예: "요즘 ~역 주변 문의가 폭발적으로 늘고 있습니다.")
- 핵심 수치 1~2개로 현재 시장 분위기 묘사 (예: "이 지역 거래량이 전월 대비 43% 증가했습니다")
- 이 글에서 다룰 3가지 핵심 내용 예고

---

### ✅ 핵심 요약 3가지
✅ **핵심 1:** [단지명·가격 수치 포함한 2문장 — 예: "XX아파트 84㎡, 2023년 9억 → 2025년 11.8억(+31%)"]
✅ **핵심 2:** [% 변동률·거래량 수치 포함한 2문장]
✅ **핵심 3:** [개통일·투자 포인트 포함한 2문장]

---

### 📊 실거래가로 보는 시장

📊 **① 주요 단지 실거래가 비교 (2023 vs 2025)**
반드시 아래 형식의 표를 출력하세요:

| 단지명 | 전용면적 | 2023년 | 현재(2025) | 변동률 | 전세가율 |
|-------|---------|--------|-----------|--------|---------|
| (단지1) | 84㎡ | N억 | N억 | +N% | N% |
| (단지2) | 59㎡ | N억 | N억 | +N% | N% |
| (단지3) | 114㎡ | N억 | N억 | +N% | N% |

(서치팀 자료 기준, 없으면 AI 추정치 + (AI추정) 표기)

📊 **② 거래량·전세가율 분석**
- 최근 3개월 거래량 수치 (전년 동기 대비 %)
- 전세가율 % → 갭 규모 계산 (예: "10억 매매가, 전세가율 55% → 갭 4.5억")
- 임차 수요 동향

📊 **③ 외부 변수 수치**
- 기준금리 현황 + 주담대 금리 범위
- 대출 규제 현황 (LTV·DSR 수치)
- 해당 지역·노선 관련 정부 정책 발표 날짜

---

### 핵심 1: [소제목 — 실거래가·가격 변화 심층 분석]
- 분량: 420자 이상
- 반드시 단지명·평형·가격·거래 시점 최소 3건 직접 인용
- "X아파트 84㎡, 2023년 8억 5천 → 2024년 11억 → 2025년 현재 호가 12억 5천(+47%)" 형식
- 직전 고점 대비 현재 위치 분석 (회복률 %)
- 전세가율과 갭 규모로 실투자금 계산 예시
- "이 수치가 의미하는 것은" 형식으로 분석 깊이 더하기

---

### 핵심 2: [소제목 — 호재 및 상승 동력 — 구체적 근거 제시]
- 분량: 420자 이상
- 교통 호재: 개통 예정 노선명·역명·개통일·해당 역까지 이동 시간 단축 효과
- 과거 유사 사례 비교: "GTX-A 동탄역 개통 발표 후 동탄2신도시 아파트 2년 새 N억 상승"처럼 수치로
- 개발 호재: 구역 지정일·사업 단계·예상 준공 시기
- "지금이 아직 기회인 이유"를 데이터로 설득

---

### 핵심 3: [소제목 — 지금 매수해야 하는 이유·투자 전략]
- 분량: 420자 이상
- 낙관 시나리오: 개통/정책 실현 시 예상 가격 범위 (예: "개통 후 추가 N억~N억 상승 예상")
- 구체적 매수 전략 3가지 (단지명·평형·예산 범위 명시)
  전략 1: 역세권 핵심 단지 (예: "X역 도보 5분, Y아파트 84㎡ 예산 N억대")
  전략 2: 수혜권 인근 가성비 단지
  전략 3: 갭투자 가능 단지 (전세가율 60% 이상 단지)
- "지금 행동하지 않으면 N년 후 후회한다" 는 메시지로 마무리

---

### 마무리
- 분량: 220자 이상
- "결국 이 시장이 말하는 것은 ~입니다"로 시작
- 핵심 수치 1~2개로 전체 내용 압축 정리
- 행동을 촉구하는 강렬한 마지막 문장 (예: "오늘이 가장 싼 날일 수 있습니다")

━━━━━━━━━━━━━━━━━━━━━━
필수 규칙 (위반 절대 금지)
━━━━━━━━━━━━━━━━━━━━━━
- 총 글자 수: 2600자 이상 (공백·줄바꿈 제외)
- 추상적 표현 금지: "많이 올랐다/크게 상승했다" → 반드시 구체적 수치로 대체
- "데이터 미확인"으로 비워두는 것 금지 — AI 추정이라도 구체적 수치 반드시 제시
- Q: / Q. 형식 절대 금지 / Q&A 형식 절대 금지
- 각 섹션 생략 금지 / 실거래가 비교 표 반드시 포함
- 한국어만 사용. 한자·일본어·중국어 절대 금지"""


# ── AI 팀 함수 ────────────────────────────────────────────────────────────────
def run_search_team(keyword: str, api_key: str, rss_data, news_data, web_data=None, price_data=None, info_data=None, kw_type: str = "price", railway_data=None):
    client = Groq(api_key=api_key)
    raw = format_research_data(rss_data, news_data, web_data or [], price_data or [], info_data or [], railway_data or [])
    is_railway = detect_railway_keyword(keyword)
    if kw_type == "info":
        user_msg = (
            f"분석 키워드: {keyword}\n\n"
            f"--- 수집된 데이터 ---\n{raw}\n---\n\n"
            "위 데이터와 AI 학습 지식을 모두 활용하여 아래 항목을 작성해 주세요.\n"
            "1. 핵심 정보 요약 (규정·기준·절차·계산법 등) — 수치와 날짜 포함\n"
            "2. 실제 계산 예시 케이스 2~3가지 (금액·비율·단계별 수치 포함)\n"
            "3. 자주 하는 실수·주의사항 (구체적 사례)\n"
            "4. 2024~2025년 최신 변경사항\n"
            "5. 독자가 바로 활용할 수 있는 핵심 팁 3가지\n\n"
            "⚠️ 수치가 없으면 AI 추정치를 사용하되 (AI추정) 표기. '데이터 미확인'으로 비워두지 말 것."
        )
    elif is_railway:
        user_msg = (
            f"분석 키워드: {keyword}\n\n"
            f"--- 수집된 데이터 ---\n{raw}\n---\n\n"
            "위 데이터와 AI 학습 지식을 모두 활용하여 아래 항목을 모두 작성해 주세요.\n\n"
            "【철도·노선 전용 분석 항목】\n"
            "1. 노선 개요 (구간·역 목록·총연장·개통 예정 시기)\n"
            "2. 역세권별 대표 아파트 단지명 + 2023년 시세 vs 현재(2025) 시세 + 변동률 % (테이블 형식)\n"
            "3. 과거 유사 노선 개통 전후 가격 변화 실사례\n"
            "   예: 'GTX-A 동탄역 개통 발표(2019) 후 동탄2신도시 N억→N억', '9호선 2단계 개통 후 강서 N% 상승'\n"
            "4. 지금 주목할 역세권 Top 3 + 단지명·예산 범위·투자 포인트\n"
            "5. 향후 시나리오 3가지 (낙관·중립·비관 — 각각 가격 예측 수치 포함)\n"
            "6. 핵심 가설 3가지 ('개통 시 N억 상승 예상' 형식으로 수치 포함)\n\n"
            "⚠️ 수집 데이터 우선 사용. 없으면 AI 학습 지식으로 채우되 (AI추정) 표기. '미확인'으로 비워두기 금지."
        )
    else:
        user_msg = (
            f"분석 키워드: {keyword}\n\n"
            f"--- 수집된 데이터 ---\n{raw}\n---\n\n"
            "위 데이터와 AI 학습 지식을 모두 활용하여 현황 분석과 미래 예측을 작성해 주세요.\n\n"
            "【필수 포함 항목】\n"
            "1. 대표 아파트 3~5개의 2023년 시세 vs 현재(2025) 시세 비교 테이블\n"
            "   형식: 단지명 | 전용면적 | 2023년 | 현재 | 변동률 | 전세가율\n"
            "2. 실거래 사례 3건 이상 (단지명·면적·금액·거래 시점)\n"
            "3. 전세가율 % + 갭 투자 시 실투자금 계산 예시\n"
            "4. 상승/하락 촉매 요인 (구체적 정책명·날짜·수치)\n"
            "5. 시나리오 3가지 (낙관·중립·비관 — 각각 가격 예측 수치 포함)\n\n"
            "⚠️ 수집 데이터 우선 사용. 없으면 AI 학습 지식으로 채우되 (AI추정) 표기. '미확인'으로 비워두기 금지."
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


def run_blog_team(keyword: str, research: str, api_key: str, kw_type: str = "price", is_railway: bool = False):
    client = Groq(api_key=api_key)
    if kw_type == "info":
        user_msg = (
            f"블로그 주제 키워드: {keyword}\n\n"
            f"--- 서치팀 수집 자료 ---\n{research}\n---\n\n"
            "위 자료를 바탕으로 블로그 글을 작성하세요.\n\n"
            "【필수 조건 — 반드시 준수】\n"
            "- 총 글자 수 2600자 이상 (공백 제외)\n"
            "- 정보·가이드형 글 — 규정·절차·계산법 중심\n"
            "- 계산 예시는 반드시 실제 금액 수치로 (예: '매매가 5억, LTV 70% → 대출 3.5억')\n"
            "- 표 형식으로 조건·기준·한도 정리 (최소 1개 표 필수)\n"
            "- 실수 사례: 구체적 상황 묘사 (예: '전입신고를 계약 후 2주가 넘어 하면 확정일자 효력이...')\n"
            "- Q: / Q. 형식·Q&A 형식 절대 금지\n"
            "- 각 섹션 생략 금지\n"
            "- 10년 경력 부동산 전문가 설명 문체"
        )
    elif is_railway:
        user_msg = (
            f"블로그 주제 키워드: {keyword}\n\n"
            f"--- 서치팀 분석 결과 ---\n{research}\n---\n\n"
            "위 자료를 바탕으로 블로그 글을 작성하세요.\n\n"
            "【철도·노선 전용 필수 조건 — 반드시 준수】\n"
            "- 총 글자 수 2600자 이상 (공백 제외)\n"
            "- 실거래가 비교 표 반드시 포함 (단지명·2023년·현재·변동률·전세가율)\n"
            "- 핵심 1: 노선 구간·역 목록·개통 시기 + 역세권 아파트 2023→2025 가격 비교\n"
            "- 핵심 2: 과거 유사 노선 사례(GTX-A/9호선/신분당선 등) 개통 전후 수치 비교\n"
            "- 핵심 3: 구체적 투자 전략 3가지 (역 이름·단지명·예산 범위·갭 투자 가능 여부)\n"
            "- 수치 뒤 출처 표기: (국토교통부), (호갱노노), (AI추정) 중 하나 필수\n"
            "- 추상적 표현 금지 → 모든 주장은 수치로 뒷받침\n"
            "- Q: / Q. 형식·Q&A 형식 절대 금지 / 각 섹션 생략 금지\n"
            "- 10년 경력 부동산 칼럼니스트 분석 문체"
        )
    else:
        user_msg = (
            f"블로그 주제 키워드: {keyword}\n\n"
            f"--- 서치팀 분석 결과 ---\n{research}\n---\n\n"
            "위 자료를 바탕으로 블로그 글을 작성하세요.\n\n"
            "【필수 조건 — 반드시 준수】\n"
            "- 총 글자 수 2600자 이상 (공백 제외)\n"
            "- 실거래가 비교 표 반드시 포함 (단지명·2023년 시세·현재 시세·변동률·전세가율)\n"
            "- 핵심 1: 단지명·평형·실거래 금액·변동률 최소 3건 인용 + 갭 투자 실투자금 계산\n"
            "- 핵심 2: 호재 근거는 반드시 수치로 ('교통 좋아졌다' 금지 → '역까지 도보 N분·버스 N분 단축')\n"
            "- 핵심 3: 투자 전략 3가지에 단지명·예산 범위·매수 포인트 명시\n"
            "- 수치 뒤 출처: (호갱노노), (국토교통부), (AI추정) 중 하나 필수\n"
            "- 추상적 표현 금지 → 모든 주장은 수치로 뒷받침\n"
            "- Q: / Q. 형식·Q&A 형식 절대 금지 / 각 섹션 생략 금지\n"
            "- 10년 경력 부동산 칼럼니스트 분석 문체"
        )
    stream = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": BLOG_SYSTEM},
            {"role": "user",   "content": user_msg},
        ],
        stream=True,
        max_tokens=4000,
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

# ── 저장소 ────────────────────────────────────────────────────────────────────
if "show_archive" not in st.session_state:
    st.session_state.show_archive = False
if "archive_view_idx" not in st.session_state:
    st.session_state.archive_view_idx = -1

_archive_label = "📂 저장소 닫기" if st.session_state.show_archive else "📂 저장소"
if st.button(_archive_label, use_container_width=True):
    st.session_state.show_archive = not st.session_state.show_archive
    st.session_state.archive_view_idx = -1
    st.rerun()

if st.session_state.show_archive:
    _archive_files = load_archive()

    if not _archive_files:
        st.markdown("""
        <div style='background:#F9FAFB; border-radius:14px; padding:32px; text-align:center; margin-bottom:16px;'>
            <div style='font-size:32px; margin-bottom:8px;'>📭</div>
            <div style='font-size:15px; font-weight:700; color:#191F28;'>저장된 글이 없습니다</div>
            <div style='font-size:13px; color:#8B95A1; margin-top:4px;'>블로그를 생성하면 자동으로 여기에 저장됩니다</div>
        </div>
        """, unsafe_allow_html=True)

    elif st.session_state.archive_view_idx >= 0 and st.session_state.archive_view_idx < len(_archive_files):
        # ── 상세 보기 ──────────────────────────────────────────────────────────
        _item = _archive_files[st.session_state.archive_view_idx]
        _content = read_archive_file(_item["fpath"])

        col_back, col_dl = st.columns([1, 1])
        with col_back:
            if st.button("← 목록으로", use_container_width=True):
                st.session_state.archive_view_idx = -1
                st.rerun()
        with col_dl:
            st.download_button(
                "💾 다운로드 (.txt)",
                data=_content,
                file_name=_item["fname"],
                mime="text/plain",
                use_container_width=True,
            )

        st.markdown(f"""
        <div style='margin:16px 0 4px 0;'>
            <div style='font-size:20px; font-weight:900; color:#191F28;'>{_item['keyword']}</div>
            <div style='font-size:12px; color:#8B95A1; margin-top:4px;'>🗓 {_item['date']} &nbsp;·&nbsp; 📝 {_item['chars']}</div>
        </div>
        <hr style='border:none; border-top:1px solid #E5E8EB; margin:12px 0 20px 0;'>
        """, unsafe_allow_html=True)

        # 블로그 글 본문만 추출해서 표시 (=== 블로그 글 === 이후)
        _blog_part = _content
        if "=== 블로그 글 ===" in _content:
            _blog_part = _content.split("=== 블로그 글 ===", 1)[1].strip()
        st.markdown(_blog_part)

    else:
        # ── 카드 목록 ──────────────────────────────────────────────────────────
        st.markdown(f"""
        <div style='font-size:13px; color:#8B95A1; margin:0 0 12px 0;'>
            총 <b style='color:#191F28;'>{len(_archive_files)}개</b> 저장됨 &nbsp;·&nbsp; 최신순
        </div>
        """, unsafe_allow_html=True)

        for _i, _item in enumerate(_archive_files):
            _col_info, _col_btn = st.columns([8, 2])
            with _col_info:
                st.markdown(f"""
                <div style='background:#FFFFFF; border-radius:12px; padding:14px 18px;
                            box-shadow:0 1px 4px rgba(0,0,0,0.06); margin-bottom:8px;
                            border-left:3px solid #3182F6;'>
                    <div style='font-size:15px; font-weight:700; color:#191F28;'>📄 {_item['keyword']}</div>
                    <div style='font-size:12px; color:#8B95A1; margin-top:4px;'>
                        🗓 {_item['date']} &nbsp;·&nbsp; 📝 {_item['chars']}
                    </div>
                </div>
                """, unsafe_allow_html=True)
            with _col_btn:
                st.markdown("<div style='padding-top:8px;'></div>", unsafe_allow_html=True)
                if st.button("열기", key=f"arch_open_{_i}", use_container_width=True):
                    st.session_state.archive_view_idx = _i
                    st.rerun()

    st.markdown("<hr style='border:none; border-top:1px solid #E5E8EB; margin:20px 0;'>", unsafe_allow_html=True)

# ── API 키 상태 표시 (항상 최상단) ────────────────────────────────────────────
if api_key:
    st.success(f"✅ API 키 로드됨: {api_key[:6]}...{api_key[-4:]}")
else:
    st.error("❌ API 키 없음 — Streamlit Cloud Secrets에 groq_api_key 를 설정해 주세요.")

# ── 인기 검색어 조회 ───────────────────────────────────────────────────────────
st.markdown("""
<div class='toss-card' style='padding:20px 24px;'>
    <div style='font-size:16px; font-weight:800; color:#191F28; margin-bottom:4px;'>🔥 부동산 관심 키워드 TOP 30</div>
    <div style='font-size:12px; color:#8B95A1;'>🚆 지하철·국가철도망 호재 15개 &nbsp;+&nbsp; 🔍 사람들이 진짜 궁금한 부동산 키워드 15개</div>
</div>
""", unsafe_allow_html=True)

if "trending_keywords" not in st.session_state:
    st.session_state.trending_keywords = []
if "selected_keyword" not in st.session_state:
    st.session_state.selected_keyword = ""

trend_btn = st.button("📊 최근 1개월 TOP 30 조회", use_container_width=True)
if trend_btn:
    if not api_key:
        st.error("❌ API 키가 없습니다. 사이드바에서 Groq API 키를 입력해 주세요.")
    else:
        _status_placeholder = st.empty()
        _status_placeholder.info("⏳ 키워드 분석을 시작합니다...")
        try:
            def _update_status(msg):
                _status_placeholder.info(msg)

            st.session_state.trending_keywords = get_trending_keywords(api_key, status_fn=_update_status)
            if st.session_state.trending_keywords:
                _status_placeholder.success(f"✅ 키워드 {len(st.session_state.trending_keywords)}개 로드 완료!")
            else:
                _status_placeholder.error("❌ 키워드 생성 실패 — API 키를 확인하거나 잠시 후 다시 시도해 주세요.")
        except Exception as e:
            err = str(e)
            if "auth" in err.lower() or "invalid" in err.lower() or "api_key" in err.lower():
                _status_placeholder.error("❌ Groq API 키가 올바르지 않습니다. 사이드바에서 확인해 주세요.")
            elif "rate" in err.lower() or "quota" in err.lower() or "429" in err:
                _status_placeholder.error("⏱️ Groq 사용 한도 초과. 잠시 후 다시 시도해 주세요.")
            elif "connect" in err.lower() or "timeout" in err.lower():
                _status_placeholder.error("🌐 연결 오류. 인터넷 연결을 확인해 주세요.")
            else:
                _status_placeholder.error(f"❌ 오류: {e}")

if st.session_state.trending_keywords:
    st.markdown("<div style='font-size:12px; color:#8B95A1; margin:10px 0 6px 0;'>클릭하면 키워드 입력창에 자동 입력됩니다</div>", unsafe_allow_html=True)

    railway_kws  = [x for x in st.session_state.trending_keywords if x.get("category") == "철도호재"]
    general_kws  = [x for x in st.session_state.trending_keywords if x.get("category") != "철도호재"]

    def render_keyword_list(items, base_idx, bar_color):
        for j, item in enumerate(items):
            kw     = item["keyword"]
            score  = item["score"]
            source = item["source"]
            try:
                pct = max(10, min(100, int(score)))
            except Exception:
                pct = 50 if score == "상" else (35 if score == "중" else 20)
            rank_color = "#F5A623" if j < 3 else "#8B95A1"
            rank_label = ["🥇", "🥈", "🥉"][j] if j < 3 else f"{j+1}위"
            col_rank, col_info, col_btn = st.columns([1, 7, 2])
            with col_rank:
                st.markdown(f"<div style='font-size:18px; font-weight:900; color:{rank_color}; padding-top:8px; text-align:center;'>{rank_label}</div>", unsafe_allow_html=True)
            with col_info:
                st.markdown(f"""
                <div style='padding:4px 0;'>
                    <div style='display:flex; align-items:center; gap:8px;'>
                        <span style='font-size:15px; font-weight:700; color:#191F28;'>{kw}</span>
                        <span style='font-size:11px; font-weight:700; color:{bar_color}; background:{bar_color}18; padding:2px 8px; border-radius:20px;'>{source}</span>
                        <span style='font-size:12px; color:#8B95A1; margin-left:auto;'>검색량 {score}</span>
                    </div>
                    <div style='margin-top:5px; height:5px; background:#F2F4F6; border-radius:10px; overflow:hidden;'>
                        <div style='width:{pct}%; height:100%; background:{bar_color}; border-radius:10px;'></div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
            with col_btn:
                if st.button("선택", key=f"kw_{base_idx}_{j}", use_container_width=True):
                    st.session_state.selected_keyword = kw
                    st.rerun()

    col_a, col_b = st.columns(2)

    with col_a:
        st.markdown("""
        <div style='background:#EBF3FE; border-radius:12px; padding:12px 16px; margin-bottom:12px;'>
            <div style='font-size:14px; font-weight:900; color:#1B6EE0;'>🚆 지하철·국가철도망 호재</div>
            <div style='font-size:11px; color:#3182F6; margin-top:2px;'>신설 노선·역세권 수혜 키워드 TOP 15</div>
        </div>
        """, unsafe_allow_html=True)
        render_keyword_list(railway_kws[:15], base_idx=0, bar_color="#3182F6")

    with col_b:
        st.markdown("""
        <div style='background:#FFF4E8; border-radius:12px; padding:12px 16px; margin-bottom:12px;'>
            <div style='font-size:14px; font-weight:900; color:#D4651A;'>🔍 지금 사람들이 궁금한 부동산</div>
            <div style='font-size:11px; color:#F5A623; margin-top:2px;'>실수요자·투자자 관심 키워드 TOP 15</div>
        </div>
        """, unsafe_allow_html=True)
        render_keyword_list(general_kws[:15], base_idx=1, bar_color="#F5A623")

st.markdown("<hr style='border:none; border-top:1px solid #F2F4F6; margin:16px 0;'>", unsafe_allow_html=True)

# ── 키워드 입력 (최대 5개) ────────────────────────────────────────────────────
st.markdown("""
<div style='font-size:15px; font-weight:700; color:#191F28; margin:8px 0 4px 0;'>키워드 입력 <span style='font-size:12px; font-weight:400; color:#8B95A1;'>최대 5개 — 결과는 txt 파일로 다운로드됩니다</span></div>
""", unsafe_allow_html=True)

_kw_placeholders = [
    "예: 강남 아파트 매수 타이밍",
    "예: 전세사기 예방법",
    "예: GTX-C 역세권 투자",
    "예: 재건축 투자 지금 해도 될까",
    "예: 부동산 취득세 계산법",
]
_kw_values = []
for _i in range(5):
    _default = st.session_state.selected_keyword if _i == 0 else ""
    _kw_val = st.text_input(
        f"키워드 {_i + 1}",
        value=_default,
        placeholder=_kw_placeholders[_i],
        key=f"kw_input_{_i}",
        label_visibility="collapsed",
    )
    _kw_values.append(_kw_val)

run_btn = st.button("🚀 블로그 생성 시작", use_container_width=True)


# ── 실행 ──────────────────────────────────────────────────────────────────────
if run_btn:
    if not api_key:
        st.error("사이드바에서 Groq API 키를 먼저 입력해 주세요.")
        st.stop()

    _keywords_to_run = [kw.strip() for kw in _kw_values if kw.strip()]
    if not _keywords_to_run:
        st.error("키워드를 최소 1개 이상 입력해 주세요.")
        st.stop()

    st.markdown("<hr style='border:none; border-top:1px solid #E5E8EB; margin:24px 0 20px 0;'>", unsafe_allow_html=True)

    _results = []

    for _idx, kw in enumerate(_keywords_to_run):
        st.markdown(f"""
        <div class='toss-card' style='padding:16px 20px; margin-bottom:8px;'>
            <div style='font-size:12px; color:#8B95A1; font-weight:700;'>{_idx + 1} / {len(_keywords_to_run)}</div>
            <div style='font-size:16px; font-weight:800; color:#191F28; margin-top:2px;'>{kw}</div>
        </div>
        """, unsafe_allow_html=True)

        _status = st.empty()

        # STEP 0: 데이터 수집 (병렬)
        _status.info("📡 데이터 수집 중...")
        kw_type    = detect_keyword_type(kw)
        is_railway = detect_railway_keyword(kw)
        info_data    = []
        price_data   = []
        railway_data = []
        try:
            _extra_fn = search_info_data if kw_type == "info" else search_price_data
            with ThreadPoolExecutor(max_workers=5) as _pool:
                _f_rss   = _pool.submit(fetch_rss, kw)
                _f_news  = _pool.submit(search_news, kw)
                _f_web   = _pool.submit(search_web_docs, kw)
                _f_extra = _pool.submit(_extra_fn, kw)
                _f_rail  = _pool.submit(search_railway_data, kw) if is_railway else None

                rss_data  = _f_rss.result()
                news_data = _f_news.result()
                web_data  = _f_web.result()
                _extra    = _f_extra.result()
                railway_data = _f_rail.result() if _f_rail else []

            if kw_type == "info":
                info_data, price_data = _extra, []
            else:
                info_data, price_data = [], _extra
        except Exception as _e:
            _status.error(f"데이터 수집 오류: {_e}")
            continue

        # STEP 1: 서치팀
        _status.info("🔍 서치팀 분석 중...")
        try:
            research_text = ""
            for _chunk in run_search_team(kw, api_key, rss_data, news_data, web_data, price_data, info_data, kw_type, railway_data):
                research_text += _chunk
        except Exception as _e:
            err = str(_e)
            if "auth" in err.lower() or "invalid" in err.lower():
                _status.error("❌ Groq API 키가 올바르지 않습니다.")
            elif "rate" in err.lower() or "quota" in err.lower():
                _status.error("⏱️ 사용 한도 초과. 잠시 후 다시 시도해 주세요.")
            else:
                _status.error(f"서치팀 오류: {_e}")
            continue

        # STEP 2: 블로그팀
        _status.info("✍️ 블로그 작성 중...")
        try:
            blog_text = ""
            for _chunk in run_blog_team(kw, research_text, api_key, kw_type, is_railway):
                blog_text += _chunk
        except Exception as _e:
            err = str(_e)
            if "auth" in err.lower() or "invalid" in err.lower():
                _status.error("❌ Groq API 키가 올바르지 않습니다.")
            elif "rate" in err.lower() or "quota" in err.lower():
                _status.error("⏱️ 사용 한도 초과. 잠시 후 다시 시도해 주세요.")
            else:
                _status.error(f"블로그팀 오류: {_e}")
            continue

        saved_fname = auto_save_blog(kw, research_text, blog_text)
        char_count  = len(blog_text.replace(" ", "").replace("\n", ""))
        _status.success(f"✅ 완료 — {char_count:,}자")

        _results.append({
            "keyword":       kw,
            "fname":         saved_fname,
            "blog_text":     blog_text,
            "research_text": research_text,
            "rss_data":      rss_data,
            "news_data":     news_data,
            "web_data":      web_data,
            "char_count":    char_count,
        })

    if _results:
        st.markdown("<hr style='border:none; border-top:1px solid #E5E8EB; margin:24px 0 16px 0;'>", unsafe_allow_html=True)
        st.markdown(f"""
        <div class='toss-card' style='border-left:4px solid #1BB76E; padding:20px 24px;'>
            <div class='toss-tag-green'>완성</div>
            <div class='toss-h2'>🎉 {len(_results)}개 블로그 글 생성 완료</div>
            <div class='toss-body'>각 키워드별 txt 파일을 다운로드하세요</div>
        </div>
        """, unsafe_allow_html=True)

        for _r in _results:
            _kw = _r["keyword"]
            st.markdown(f"""
            <div style='font-size:14px; font-weight:800; color:#191F28; margin:16px 0 6px 0;'>
                📄 {_kw} <span style='font-size:12px; font-weight:400; color:#8B95A1;'>· {_r['char_count']:,}자 · {_r['fname']}</span>
            </div>
            """, unsafe_allow_html=True)
            _col1, _col2 = st.columns(2)
            with _col1:
                st.download_button(
                    "💾 블로그 글 (.txt)",
                    data=strip_markdown(_r["blog_text"]),
                    file_name=f"블로그_{_kw}.txt",
                    mime="text/plain",
                    key=f"dl_blog_{_kw}",
                    use_container_width=True,
                )
            with _col2:
                _full_report = (
                    f"[키워드: {_kw}]\n\n"
                    f"=== 수집 데이터 ===\n{format_research_data(_r['rss_data'], _r['news_data'], _r['web_data'])}\n\n"
                    f"=== 서치팀 분석 ===\n{strip_markdown(_r['research_text'])}\n\n"
                    f"=== 블로그 글 ===\n{strip_markdown(_r['blog_text'])}"
                )
                st.download_button(
                    "📋 전체 리포트 (.txt)",
                    data=_full_report,
                    file_name=f"리포트_{_kw}.txt",
                    mime="text/plain",
                    key=f"dl_report_{_kw}",
                    use_container_width=True,
                )
