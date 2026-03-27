import streamlit as st
from PIL import Image, ImageDraw, ImageFont
import os
import io

# ── 페이지 설정 ──────────────────────────────────────────────────────────────
st.set_page_config(page_title="자동 썸네일 생성기", page_icon="🖼️", layout="wide")
st.title("🖼️ 자동 썸네일 생성기")
st.caption("배경 이미지와 텍스트를 넣어 전문가 수준의 썸네일을 자동으로 만듭니다.")

# ── 유틸 함수 ────────────────────────────────────────────────────────────────
def create_thumbnail(bg_image, title, subtitle, logo_path=None, theme_color="#FF4B4B"):
    """이미지 위에 텍스트와 로고를 합성하여 썸네일 생성"""
    img = Image.open(bg_image).convert("RGBA")
    # 16:9 비율로 크롭 및 리사이즈 (1280x720)
    target_ratio = 16/9
    width, height = img.size
    current_ratio = width / height
    
    if current_ratio > target_ratio:
        # 가로가 김 -> 가로 크롭
        new_width = int(height * target_ratio)
        offset = (width - new_width) // 2
        img = img.crop((offset, 0, offset + new_width, height))
    else:
        # 세로가 김 -> 세로 크롭
        new_height = int(width / target_ratio)
        offset = (height - new_height) // 2
        img = img.crop((0, offset, width, offset + new_height))
    
    img = img.resize((1280, 720), Image.LANCZOS)
    
    # 오버레이 (텍스트 가독성을 위해 어둡게)
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 100))
    img = Image.alpha_composite(img, overlay)
    
    draw = ImageDraw.Draw(img)
    
    # 폰트 설정 (기본 폰트 사용, 한글 지원을 위해 NanumGothic 등 시스템 폰트 경로 확인 필요)
    # 윈도우 기본 폰트 경로 사용 시도
    font_path = "C:/Windows/Fonts/malgun.ttf" # 맑은 고딕
    if not os.path.exists(font_path):
        font_path = None # 기본 폰트 사용
        
    try:
        title_font = ImageFont.truetype(font_path, 80) if font_path else ImageFont.load_default()
        sub_font = ImageFont.truetype(font_path, 40) if font_path else ImageFont.load_default()
    except:
        title_font = ImageFont.load_default()
        sub_font = ImageFont.load_default()

    # 텍스트 그리기 (가운데 정렬)
    title_bbox = draw.textbbox((0, 0), title, font=title_font)
    sub_bbox = draw.textbbox((0, 0), subtitle, font=sub_font)
    
    t_w, t_h = title_bbox[2] - title_bbox[0], title_bbox[3] - title_bbox[1]
    s_w, s_h = sub_bbox[2] - sub_bbox[0], sub_bbox[3] - sub_bbox[1]
    
    draw.text(((1280-t_w)//2, 300), title, font=title_font, fill="white")
    draw.text(((1280-s_w)//2, 400), subtitle, font=sub_font, fill="#CCCCCC")
    
    # 로고 삽입
    if logo_path and os.path.exists(logo_path):
        logo = Image.open(logo_path).convert("RGBA")
        logo.thumbnail((150, 150))
        img.paste(logo, (50, 50), logo)
        
    # 하단 포인트 바
    draw.rectangle([0, 710, 1280, 720], fill=theme_color)
    
    return img.convert("RGB")

# ── 사이드바 설정 ─────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("🎨 스타일 설정")
    bg_file = st.file_uploader("배경 이미지 업로드", type=["jpg", "png", "jpeg"])
    logo_file = st.file_uploader("로고 이미지 업로드 (선택)", type=["png"])
    
    theme_color = st.color_picker("포인트 색상", "#FF4B4B")
    
    st.markdown("---")
    st.markdown("💡 **팁**: 배경 이미지는 명도가 낮은 사진이 텍스트 가독성이 좋습니다.")

# ── 메인 UI ──────────────────────────────────────────────────────────────────
col1, col2 = st.columns([1, 1])

with col1:
    title = st.text_input("메인 타이틀", "여기에 제목을 입력하세요")
    subtitle = st.text_input("서브 타이틀", "부제목 또는 설명을 입력하세요")

    if st.button("🚀 썸네일 생성", type="primary", use_container_width=True):
        if bg_file:
            # 기본 로고 경로 (이전에 만든 로고가 있다면 사용)
            default_logo = "logo.png" if os.path.exists("logo.png") else None
            logo_to_use = logo_file if logo_file else default_logo
            
            with st.spinner("이미지를 생성하는 중..."):
                result_img = create_thumbnail(bg_file, title, subtitle, logo_to_use, theme_color)
                st.session_state["result_img"] = result_img
        else:
            st.warning("배경 이미지를 먼저 업로드해 주세요.")

with col2:
    if "result_img" in st.session_state:
        st.subheader("미리보기")
        st.image(st.session_state["result_img"], use_container_width=True)
        
        # 다운로드 버튼
        buf = io.BytesIO()
        st.session_state["result_img"].save(buf, format="JPEG")
        st.download_button(
            label="💾 썸네일 다운로드",
            data=buf.getvalue(),
            file_name="thumbnail.jpg",
            mime="image/jpeg",
            use_container_width=True
        )
    else:
        st.info("왼쪽에서 배경 이미지를 넣고 생성 버튼을 눌러주세요.")

# ── 추가 안내 ────────────────────────────────────────────────────────────────
st.markdown("---")
st.markdown("""
### 🛠️ 사용 방법
1. **배경 이미지**를 업로드합니다.
2. 보여줄 **메인 타이틀**과 **서브 타이틀**을 입력합니다.
3. 로고가 있다면 업로드하거나, 기본 로고를 사용합니다.
4. **포인트 색상**을 선택하여 하단 바의 색을 결정합니다.
5. **썸네일 생성** 버튼을 클릭하고 결과를 다운로드합니다.
""")
