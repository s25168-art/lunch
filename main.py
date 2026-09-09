"""
우리 학교 급식 달력
- NEIS(나이스) 오픈API에서 한 달치 급식 정보를 한 번에 가져와 달력으로 보여 줍니다.
- 학교 이름으로 검색해서 코드를 자동으로 채울 수 있고, 오늘 급식은 맨 위에 따로 보여 줍니다.
- 실행 방법: streamlit run main.py
"""

import calendar
import datetime as dt
import html
import re

import requests
import streamlit as st

# ---------------------------------------------------------------------------
# 1. 기본 설정값
# ---------------------------------------------------------------------------

# NEIS 오픈API 주소 두 가지
MEAL_URL = "https://open.neis.go.kr/hub/mealServiceDietInfo"   # 급식식단정보
SCHOOL_URL = "https://open.neis.go.kr/hub/schoolInfo"          # 학교기본정보(이름으로 코드 찾기)

# 처음 켰을 때 채워 둘 기본 학교 (사이드바에서 언제든 바꿀 수 있습니다)
DEFAULT_ATPT_CODE = "B10"        # 시도교육청코드 (B10 = 서울특별시교육청)
DEFAULT_SCHOOL_CODE = "7010084"  # 표준학교코드
DEFAULT_SCHOOL_NAME = "학교를 검색해 주세요"

# 알레르기 유발 식품 번호(1~19)와 실제 식재료 이름 대응표
ALLERGY_TABLE = {
    "1": "난류", "2": "우유", "3": "메밀", "4": "땅콩", "5": "대두",
    "6": "밀", "7": "고등어", "8": "게", "9": "새우", "10": "돼지고기",
    "11": "복숭아", "12": "토마토", "13": "아황산류", "14": "호두", "15": "닭고기",
    "16": "쇠고기", "17": "오징어", "18": "조개류", "19": "잣",
}

# 급식 종류별 색상 (중식=파랑, 석식=빨강, 그 외=초록)
MEAL_COLORS = {"중식": "#3182F6", "석식": "#F04452"}
ETC_MEAL_COLOR = "#00B26B"

# 달력에 표시할 요일 이름 (월~금만 사용)
WEEKDAY_NAMES = ["월", "화", "수", "목", "금"]

MEAL_FILTER_OPTIONS = ["전체 보기", "중식만 보기", "석식만 보기"]


# ---------------------------------------------------------------------------
# 2. 페이지 설정과 스타일
# ---------------------------------------------------------------------------

st.set_page_config(page_title="우리 학교 급식 달력", page_icon="🍚", layout="wide")

# 토스처럼 여백이 넉넉하고 군더더기 없는 화면을 만들기 위한 CSS입니다.
st.markdown(
    """
    <style>
    @import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/static/pretendard.css');

    :root {
        --gray-900: #191F28;
        --gray-700: #333D4B;
        --gray-600: #4E5968;
        --gray-500: #6B7684;
        --gray-400: #8B95A1;
        --gray-300: #B0B8C1;
        --gray-200: #D1D6DB;
        --gray-100: #F2F4F6;
        --gray-50:  #F9FAFB;
        --blue:     #3182F6;
        --red:      #F04452;
        --green:    #00B26B;
    }

    html, body, [class*="css"], button, input, select, textarea {
        font-family: 'Pretendard', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    }

    .block-container { padding-top: 2.2rem; padding-bottom: 4rem; max-width: 1440px; }
    #MainMenu, footer { visibility: hidden; }

    /* ---------- 헤더 ---------- */
    .app-title {
        font-size: 27px; font-weight: 700; color: var(--gray-900);
        letter-spacing: -0.6px; margin-bottom: 2px;
    }
    .app-school {
        font-size: 14px; color: var(--gray-400); margin-bottom: 22px;
    }
    .app-school b { color: var(--gray-600); font-weight: 600; }

    /* ---------- 오늘 급식 ---------- */
    .today-wrap {
        background: linear-gradient(180deg, #FFFFFF 0%, #FBFCFD 100%);
        border: 1px solid var(--gray-100);
        border-radius: 20px;
        padding: 22px 24px;
        margin-bottom: 28px;
    }
    .today-label {
        font-size: 12px; font-weight: 700; color: var(--blue);
        letter-spacing: 0.2px; margin-bottom: 2px;
    }
    .today-date {
        font-size: 20px; font-weight: 700; color: var(--gray-900);
        letter-spacing: -0.4px; margin-bottom: 16px;
    }
    .today-grid { display: flex; flex-wrap: wrap; gap: 12px; }
    .today-meal {
        flex: 1 1 240px;
        background: #FFFFFF;
        border: 1px solid var(--gray-100);
        border-left: 3px solid var(--gray-200);
        border-radius: 12px;
        padding: 14px 16px;
    }
    .today-meal-name { font-size: 13px; font-weight: 700; margin-bottom: 6px; }
    .today-menu {
        font-size: 14px; color: var(--gray-600);
        line-height: 1.7; word-break: keep-all;
    }
    .today-cal { font-size: 12px; color: var(--gray-300); margin-top: 8px; }
    .today-none {
        font-size: 14px; color: var(--gray-300); padding: 6px 0 2px 0;
    }

    /* ---------- 달력 ---------- */
    .month-title {
        font-size: 19px; font-weight: 700; color: var(--gray-900);
        letter-spacing: -0.3px; text-align: center; padding-top: 4px;
    }
    .weekday-head {
        font-size: 12px; font-weight: 600; color: var(--gray-400);
        text-align: center; padding: 14px 0 8px 0;
    }
    .day-card {
        border: 1px solid var(--gray-100);
        border-radius: 16px;
        background: #FFFFFF;
        padding: 14px 14px 16px 14px;
        min-height: 196px;
        margin-bottom: 12px;
        transition: border-color .15s ease;
    }
    .day-card:hover { border-color: var(--gray-200); }
    .day-card.today { border: 1.5px solid var(--blue); }
    .day-card.blank {
        background: transparent; border: 1px dashed var(--gray-100);
        min-height: 196px;
    }
    .day-card.off { background: var(--gray-50); }

    .day-head { display: flex; align-items: center; gap: 6px; margin-bottom: 12px; }
    .day-num {
        font-size: 17px; font-weight: 700; color: var(--gray-900); letter-spacing: -0.3px;
    }
    .day-dow { font-size: 12px; color: var(--gray-300); }
    .today-badge {
        margin-left: auto; font-size: 10px; font-weight: 700; color: #FFFFFF;
        background: var(--blue); border-radius: 999px; padding: 3px 8px; letter-spacing: 0.3px;
    }
    .meal-block { margin-bottom: 13px; }
    .meal-block:last-child { margin-bottom: 0; }
    .meal-title {
        font-size: 11px; font-weight: 700; margin-bottom: 5px;
        display: inline-block; padding: 2px 7px; border-radius: 6px;
    }
    .menu-line {
        font-size: 13px; color: var(--gray-600); line-height: 1.65; word-break: keep-all;
    }
    .empty-text { font-size: 13px; color: var(--gray-300); }

    /* ---------- 사이드바 ---------- */
    section[data-testid="stSidebar"] { background: #FBFCFD; }
    section[data-testid="stSidebar"] .block-container { padding-top: 1.5rem; }
    .side-head {
        font-size: 13px; font-weight: 700; color: var(--gray-900);
        margin: 4px 0 8px 0;
    }
    .side-school {
        background: #FFFFFF; border: 1px solid var(--gray-100); border-radius: 12px;
        padding: 12px 14px; margin-bottom: 4px;
    }
    .side-school-name { font-size: 14px; font-weight: 700; color: var(--gray-900); }
    .side-school-code { font-size: 12px; color: var(--gray-400); margin-top: 3px; }
    .allergy-item { font-size: 13px; color: var(--gray-600); line-height: 1.85; }

    /* ---------- 버튼 ---------- */
    div.stButton > button {
        border-radius: 10px; border: 1px solid var(--gray-100);
        background: #FFFFFF; color: var(--gray-700);
        font-weight: 600; font-size: 14px; transition: background .15s ease;
    }
    div.stButton > button:hover {
        background: var(--gray-50); border-color: var(--gray-200); color: var(--gray-900);
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------------------
# 3. 알레르기 번호 → 식재료 이름 변환
# ---------------------------------------------------------------------------

# "(5.6.10.)" 처럼 숫자와 점이 이어진 부분을 찾는 정규식입니다.
ALLERGY_PATTERN = re.compile(r"\(?(?:\d{1,2}\.)+\)?")


def convert_allergy_numbers(text: str) -> str:
    """메뉴 이름 뒤의 알레르기 번호를 실제 식재료 이름으로 바꿔 줍니다."""

    def replace(match: re.Match) -> str:
        numbers = re.findall(r"\d{1,2}", match.group(0))
        names = [ALLERGY_TABLE[n] for n in numbers if n in ALLERGY_TABLE]
        # 표에 없는 숫자가 섞여 있으면 원래 글자를 그대로 둡니다.
        if not names or len(names) != len(numbers):
            return match.group(0)
        return "(" + ", ".join(names) + ")"

    return ALLERGY_PATTERN.sub(replace, text)


# ---------------------------------------------------------------------------
# 4. NEIS API 호출
# ---------------------------------------------------------------------------


def read_api_key() -> str:
    """secrets.toml에서 인증키를 읽습니다. 파일이 없어도 오류가 나지 않게 감쌉니다."""
    try:
        return st.secrets.get("NEIS_KEY", "")
    except Exception:
        return ""


@st.cache_data(ttl=3600, show_spinner=False)
def search_schools(api_key: str, keyword: str):
    """학교 이름으로 검색해서 (학교목록, 오류메시지)를 돌려줍니다."""
    params = {
        "KEY": api_key, "Type": "json", "pIndex": 1, "pSize": 50,
        "SCHUL_NM": keyword,
    }
    try:
        response = requests.get(SCHOOL_URL, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
    except requests.exceptions.Timeout:
        return [], "나이스 서버 응답이 너무 늦습니다. 잠시 후 다시 시도해 주세요."
    except requests.exceptions.ConnectionError:
        return [], "인터넷 연결을 확인해 주세요."
    except requests.exceptions.HTTPError as error:
        return [], f"나이스 서버가 오류를 돌려주었습니다. (상태 코드: {error.response.status_code})"
    except ValueError:
        return [], "나이스 응답을 읽지 못했습니다."
    except requests.exceptions.RequestException as error:
        return [], f"학교를 찾는 중 문제가 생겼습니다. ({error})"

    if "schoolInfo" not in data:
        code = data.get("RESULT", {}).get("CODE", "")
        if code == "INFO-200":
            return [], None  # 검색 결과가 없는 것은 오류가 아닙니다.
        return [], data.get("RESULT", {}).get("MESSAGE", "알 수 없는 응답입니다.")

    rows = []
    for block in data["schoolInfo"]:
        if "row" in block:
            rows = block["row"]

    schools = [
        {
            "name": row.get("SCHUL_NM", ""),
            "atpt": row.get("ATPT_OFCDC_SC_CODE", ""),
            "code": row.get("SD_SCHUL_CODE", ""),
            "address": row.get("ORG_RDNMA", ""),
        }
        for row in rows
    ]
    return schools, None


@st.cache_data(ttl=1800, show_spinner=False)
def fetch_month_meals(api_key: str, atpt_code: str, school_code: str, year: int, month: int):
    """
    한 달치 급식 정보를 한 번에 가져옵니다.

    반환값: (급식자료 딕셔너리, 오류메시지)
    - 급식자료는 {"20260401": [{"name": "중식", "menus": [...], "cal": "..."}]} 형태입니다.
    """
    # 그 달의 말일을 계산합니다. monthrange는 (1일의 요일, 그 달의 일수)를 돌려줍니다.
    last_day = calendar.monthrange(year, month)[1]

    params = {
        "KEY": api_key, "Type": "json", "pIndex": 1, "pSize": 1000,
        "ATPT_OFCDC_SC_CODE": atpt_code,
        "SD_SCHUL_CODE": school_code,
        "MLSV_FROM_YMD": f"{year}{month:02d}01",
        "MLSV_TO_YMD": f"{year}{month:02d}{last_day:02d}",
    }

    try:
        response = requests.get(MEAL_URL, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
    except requests.exceptions.Timeout:
        return {}, "나이스 서버 응답이 너무 늦습니다. 잠시 후 다시 시도해 주세요."
    except requests.exceptions.ConnectionError:
        return {}, "인터넷 연결을 확인해 주세요. 나이스 서버에 접속하지 못했습니다."
    except requests.exceptions.HTTPError as error:
        return {}, f"나이스 서버가 오류를 돌려주었습니다. (상태 코드: {error.response.status_code})"
    except ValueError:
        return {}, "나이스 응답을 읽지 못했습니다. 응답 형식이 예상과 다릅니다."
    except requests.exceptions.RequestException as error:
        return {}, f"급식 정보를 불러오는 중 문제가 생겼습니다. ({error})"

    # 조회 결과가 없거나 인증키에 문제가 있으면 RESULT 항목만 돌아옵니다.
    if "mealServiceDietInfo" not in data:
        code = data.get("RESULT", {}).get("CODE", "")
        message = data.get("RESULT", {}).get("MESSAGE", "알 수 없는 응답입니다.")
        if code == "INFO-200":
            return {}, None  # 데이터가 없는 것은 '급식이 없는 달'입니다.
        return {}, f"나이스에서 받은 안내: {message} (코드: {code})"

    rows = []
    for block in data["mealServiceDietInfo"]:
        if "row" in block:
            rows = block["row"]

    meals_by_date = {}
    for row in rows:
        dish = row.get("DDISH_NM", "")
        # 메뉴는 <br/>로 구분되어 옵니다. 줄 단위로 나눠 둡니다.
        menus = [line.strip() for line in re.split(r"<br\s*/?>", dish) if line.strip()]
        meals_by_date.setdefault(row.get("MLSV_YMD", ""), []).append(
            {
                "name": row.get("MMEAL_SC_NM", "급식"),
                "code": row.get("MMEAL_SC_CODE", "9"),
                "menus": menus,
                "cal": row.get("CAL_INFO", "").strip(),
            }
        )

    # 하루 안에서 조식 → 중식 → 석식 순서로 정렬합니다.
    for date_key in meals_by_date:
        meals_by_date[date_key].sort(key=lambda meal: meal["code"])

    return meals_by_date, None


# ---------------------------------------------------------------------------
# 5. 화면 상태 준비 (연도/월/학교 정보를 기억해 둡니다)
# ---------------------------------------------------------------------------

today = dt.date.today()
YEAR_OPTIONS = list(range(today.year - 2, today.year + 3))

# session_state는 버튼을 눌러 화면이 다시 그려져도 값을 기억하는 저장소입니다.
st.session_state.setdefault("year", today.year)
st.session_state.setdefault("month", today.month)
st.session_state.setdefault("atpt_code", DEFAULT_ATPT_CODE)
st.session_state.setdefault("school_code", DEFAULT_SCHOOL_CODE)
st.session_state.setdefault("school_name", DEFAULT_SCHOOL_NAME)
st.session_state.setdefault("found_schools", [])


def shift_month(step: int) -> None:
    """◀ ▶ 버튼을 눌렀을 때 달을 앞뒤로 옮깁니다."""
    year = st.session_state.year
    month = st.session_state.month + step
    if month < 1:
        year, month = year - 1, 12
    elif month > 12:
        year, month = year + 1, 1
    # 선택할 수 있는 연도 범위를 벗어나면 옮기지 않습니다.
    if year in YEAR_OPTIONS:
        st.session_state.year, st.session_state.month = year, month


def go_today() -> None:
    """'오늘' 버튼: 이번 달로 되돌아옵니다."""
    st.session_state.year, st.session_state.month = today.year, today.month


def apply_school(school: dict) -> None:
    """검색 결과에서 고른 학교를 현재 학교로 설정합니다."""
    st.session_state.atpt_code = school["atpt"]
    st.session_state.school_code = school["code"]
    st.session_state.school_name = school["name"]


# ---------------------------------------------------------------------------
# 6. 인증키 확인
# ---------------------------------------------------------------------------

api_key = read_api_key()

if not api_key:
    st.markdown('<div class="app-title">우리 학교 급식 달력</div>', unsafe_allow_html=True)
    st.warning("나이스 인증키가 없어서 급식을 불러올 수 없습니다.")
    st.markdown(
        """
        아래 순서대로 인증키를 넣어 주세요.

        1. [나이스 오픈API](https://open.neis.go.kr)에서 회원가입 후 인증키를 발급받습니다.
        2. 프로젝트 폴더에 `.streamlit/secrets.toml` 파일을 만듭니다.
        3. 파일 안에 아래 한 줄을 적고 저장한 뒤 앱을 다시 실행합니다.
        """
    )
    st.code('NEIS_KEY = "여기에_발급받은_인증키를_붙여넣기"', language="toml")
    st.stop()


# ---------------------------------------------------------------------------
# 7. 사이드바 - 학교 검색과 표시 옵션
# ---------------------------------------------------------------------------

with st.sidebar:
    st.markdown('<div class="side-head">학교 찾기</div>', unsafe_allow_html=True)

    # 지금 선택된 학교를 카드로 보여 줍니다.
    st.markdown(
        f'<div class="side-school">'
        f'<div class="side-school-name">{html.escape(st.session_state.school_name)}</div>'
        f'<div class="side-school-code">{html.escape(st.session_state.atpt_code)} · '
        f'{html.escape(st.session_state.school_code)}</div>'
        f"</div>",
        unsafe_allow_html=True,
    )

    keyword = st.text_input("학교 이름", placeholder="예: 한빛중학교", label_visibility="collapsed")

    if st.button("학교 검색", use_container_width=True):
        if len(keyword.strip()) < 2:
            st.session_state.found_schools = []
            st.warning("학교 이름을 두 글자 이상 입력해 주세요.")
        else:
            schools, search_error = search_schools(api_key, keyword.strip())
            if search_error:
                st.session_state.found_schools = []
                st.error(f"통신 오류: {search_error}")
            else:
                st.session_state.found_schools = schools

    found = st.session_state.found_schools
    if found:
        # 같은 이름의 학교가 여러 곳일 수 있어 주소를 함께 보여 줍니다.
        labels = [f'{s["name"]} · {s["address"]}' for s in found]
        picked = st.selectbox("검색 결과", range(len(found)), format_func=lambda i: labels[i])
        st.button(
            "이 학교로 보기",
            use_container_width=True,
            on_click=apply_school,
            args=(found[picked],),
        )
    elif keyword.strip():
        st.caption("검색 결과가 없으면 이름을 조금 더 짧게 입력해 보세요.")

    with st.expander("코드 직접 입력"):
        st.text_input("시도교육청코드", key="atpt_code")
        st.text_input("표준학교코드", key="school_code")

    st.markdown("---")
    st.markdown('<div class="side-head">표시 옵션</div>', unsafe_allow_html=True)

    convert_allergy = st.toggle("알레르기 식품명으로 변환", value=True)
    st.caption("끄면 메뉴 옆에 번호가 그대로 표시됩니다.")

    with st.expander("알레르기 번호 대응표 보기"):
        for number, name in ALLERGY_TABLE.items():
            st.markdown(
                f'<div class="allergy-item">{number}. {name}</div>', unsafe_allow_html=True
            )

    st.markdown("---")
    if st.button("급식 정보 새로 받기", use_container_width=True):
        st.cache_data.clear()
        st.rerun()


# 자주 쓰는 값을 짧은 이름으로 꺼내 둡니다.
atpt_code = st.session_state.atpt_code
school_code = st.session_state.school_code
year = st.session_state.year
month = st.session_state.month


# ---------------------------------------------------------------------------
# 8. 헤더와 오늘 급식 요약
# ---------------------------------------------------------------------------

st.markdown('<div class="app-title">우리 학교 급식 달력</div>', unsafe_allow_html=True)
st.markdown(
    f'<div class="app-school">지금 보는 학교 · <b>{html.escape(st.session_state.school_name)}</b></div>',
    unsafe_allow_html=True,
)


def render_menu_lines(menus: list, css_class: str) -> str:
    """메뉴 목록을 HTML 줄로 바꿉니다. (알레르기 변환 여부를 반영)"""
    lines = []
    for menu in menus:
        text = convert_allergy_numbers(menu) if convert_allergy else menu
        lines.append(f'<div class="{css_class}">{html.escape(text)}</div>')
    return "".join(lines)


# 오늘 급식은 어떤 달을 보고 있든 항상 위에 보여 줍니다.
today_meals_map, today_error = fetch_month_meals(
    api_key, atpt_code, school_code, today.year, today.month
)
today_meals = today_meals_map.get(today.strftime("%Y%m%d"), [])

today_label = f"{today.month}월 {today.day}일 {WEEKDAY_NAMES[today.weekday()] if today.weekday() < 5 else ['토', '일'][today.weekday() - 5]}요일"

if today_error:
    body = f'<div class="today-none">오늘 급식을 불러오지 못했습니다. {html.escape(today_error)}</div>'
elif not today_meals:
    body = '<div class="today-none">오늘은 급식이 없습니다.</div>'
else:
    cards = []
    for meal in today_meals:
        color = MEAL_COLORS.get(meal["name"], ETC_MEAL_COLOR)
        cal = f'<div class="today-cal">{html.escape(meal["cal"])}</div>' if meal["cal"] else ""
        cards.append(
            f'<div class="today-meal" style="border-left-color:{color}">'
            f'<div class="today-meal-name" style="color:{color}">{html.escape(meal["name"])}</div>'
            f'<div class="today-menu">{render_menu_lines(meal["menus"], "today-menu-line")}</div>'
            f"{cal}</div>"
        )
    body = f'<div class="today-grid">{"".join(cards)}</div>'

st.markdown(
    f'<div class="today-wrap">'
    f'<div class="today-label">오늘의 급식</div>'
    f'<div class="today-date">{today_label}</div>'
    f"{body}</div>",
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------------------
# 9. 달 이동과 급식 종류 선택
# ---------------------------------------------------------------------------

col_prev, col_title, col_next, col_today, col_gap, col_filter = st.columns(
    [0.6, 2.0, 0.6, 0.9, 0.4, 4.0], vertical_alignment="center"
)

col_prev.button("◀", use_container_width=True, on_click=shift_month, args=(-1,), help="이전 달")
col_title.markdown(f'<div class="month-title">{year}년 {month}월</div>', unsafe_allow_html=True)
col_next.button("▶", use_container_width=True, on_click=shift_month, args=(1,), help="다음 달")
col_today.button("오늘", use_container_width=True, on_click=go_today)

with col_filter:
    # 최신 스트림릿에는 세그먼트 버튼이 있어 더 깔끔합니다. 없으면 라디오로 대체합니다.
    if hasattr(st, "segmented_control"):
        meal_filter = st.segmented_control(
            "급식 종류", MEAL_FILTER_OPTIONS, default="전체 보기", label_visibility="collapsed"
        ) or "전체 보기"
    else:
        meal_filter = st.radio(
            "급식 종류", MEAL_FILTER_OPTIONS, horizontal=True, label_visibility="collapsed"
        )

# 연도와 월을 직접 고르고 싶을 때를 위한 선택창입니다.
with st.expander("연도·월 직접 고르기"):
    pick_year, pick_month = st.columns(2)
    pick_year.selectbox("연도", YEAR_OPTIONS, key="year")
    pick_month.selectbox("월", list(range(1, 13)), key="month")


# ---------------------------------------------------------------------------
# 10. 이번 달 급식 불러오기
# ---------------------------------------------------------------------------

with st.spinner("급식 정보를 불러오는 중입니다."):
    meals_by_date, api_error = fetch_month_meals(api_key, atpt_code, school_code, year, month)

if api_error:
    st.error(f"통신 오류: {api_error}")
    st.stop()


# ---------------------------------------------------------------------------
# 11. 달력 그리기
# ---------------------------------------------------------------------------


def build_day_card(day: int, weekday_index: int) -> str:
    """하루치 카드 HTML을 만들어 돌려줍니다."""
    date_key = f"{year}{month:02d}{day:02d}"
    is_today = (year == today.year and month == today.month and day == today.day)

    card_class = "day-card today" if is_today else "day-card"
    badge = '<span class="today-badge">TODAY</span>' if is_today else ""
    head = (
        '<div class="day-head">'
        f'<span class="day-num">{day}</span>'
        f'<span class="day-dow">{WEEKDAY_NAMES[weekday_index]}</span>'
        f"{badge}</div>"
    )

    day_meals = meals_by_date.get(date_key, [])

    # 급식 자료 자체가 없는 날 (주말이나 방학)
    if not day_meals:
        return f'<div class="{card_class} off">{head}<div class="empty-text">급식 없음</div></div>'

    # 선택한 급식 종류로 걸러 냅니다.
    if meal_filter == "중식만 보기":
        day_meals = [meal for meal in day_meals if meal["name"] == "중식"]
    elif meal_filter == "석식만 보기":
        day_meals = [meal for meal in day_meals if meal["name"] == "석식"]

    if not day_meals:
        return f'<div class="{card_class}">{head}<div class="empty-text">해당 식단 없음</div></div>'

    blocks = []
    for meal in day_meals:
        color = MEAL_COLORS.get(meal["name"], ETC_MEAL_COLOR)
        blocks.append(
            f'<div class="meal-block">'
            f'<div class="meal-title" style="color:{color};background:{color}14">'
            f'{html.escape(meal["name"])}</div>'
            f'{render_menu_lines(meal["menus"], "menu-line")}'
            f"</div>"
        )

    return f'<div class="{card_class}">{head}{"".join(blocks)}</div>'


try:
    # 요일 머리글 (월~금)
    header_cols = st.columns(5)
    for index, name in enumerate(WEEKDAY_NAMES):
        header_cols[index].markdown(
            f'<div class="weekday-head">{name}</div>', unsafe_allow_html=True
        )

    # monthcalendar는 한 주를 [월,화,수,목,금,토,일] 7칸으로 돌려줍니다.
    # 그중 앞 5칸(평일)만 사용하고, 그 달에 속하지 않는 날은 0으로 채워져 있습니다.
    for week in calendar.monthcalendar(year, month):
        weekdays = week[:5]
        if not any(weekdays):
            continue  # 평일이 하나도 없는 주는 건너뜁니다.

        week_cols = st.columns(5)
        for index, day in enumerate(weekdays):
            if day == 0:
                week_cols[index].markdown(
                    '<div class="day-card blank"></div>', unsafe_allow_html=True
                )
            else:
                week_cols[index].markdown(build_day_card(day, index), unsafe_allow_html=True)

except Exception as error:  # noqa: BLE001
    st.error(f"화면 구성 오류: 달력을 그리는 중 문제가 생겼습니다. ({error})")

st.caption("자료 출처: 나이스 교육정보 개방 포털")
