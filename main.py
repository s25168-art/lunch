"""
우리 학교 급식 달력
- NEIS(나이스) 오픈API에서 한 달치 급식 정보를 한 번에 가져와 달력으로 보여 줍니다.
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

# NEIS 급식식단정보 엔드포인트
NEIS_URL = "https://open.neis.go.kr/hub/mealServiceDietInfo"

# 사이드바 입력창에 미리 채워 둘 기본값입니다. 본인 학교 코드로 바꿔서 쓰세요.
DEFAULT_ATPT_CODE = "B10"       # 시도교육청코드 (B10 = 서울특별시교육청)
DEFAULT_SCHOOL_CODE = "7010084" # 표준학교코드

# 알레르기 유발 식품 번호(1~19)와 실제 식재료 이름 대응표
ALLERGY_TABLE = {
    "1": "난류",
    "2": "우유",
    "3": "메밀",
    "4": "땅콩",
    "5": "대두",
    "6": "밀",
    "7": "고등어",
    "8": "게",
    "9": "새우",
    "10": "돼지고기",
    "11": "복숭아",
    "12": "토마토",
    "13": "아황산류",
    "14": "호두",
    "15": "닭고기",
    "16": "쇠고기",
    "17": "오징어",
    "18": "조개류",
    "19": "잣",
}

# 급식 종류별 색상 (중식=파랑, 석식=빨강, 그 외=초록)
MEAL_COLORS = {
    "중식": "#3182F6",
    "석식": "#F04452",
}
ETC_MEAL_COLOR = "#00B26B"

# 달력에 표시할 요일 이름 (월~금만 사용)
WEEKDAY_NAMES = ["월", "화", "수", "목", "금"]


# ---------------------------------------------------------------------------
# 2. 페이지 설정과 스타일
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="우리 학교 급식 달력",
    page_icon="🍚",
    layout="wide",
)

# 토스처럼 여백이 넉넉하고 군더더기 없는 화면을 만들기 위한 CSS입니다.
st.markdown(
    """
    <style>
    @import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/static/pretendard.css');

    html, body, [class*="css"] {
        font-family: 'Pretendard', -apple-system, BlinkMacSystemFont, sans-serif;
    }

    /* 상단 여백 줄이기 */
    .block-container { padding-top: 2.5rem; padding-bottom: 3rem; max-width: 1400px; }

    /* 페이지 제목 */
    .app-title {
        font-size: 26px;
        font-weight: 700;
        color: #191F28;
        letter-spacing: -0.4px;
        margin-bottom: 4px;
    }
    .app-subtitle {
        font-size: 14px;
        color: #8B95A1;
        margin-bottom: 24px;
    }

    /* 요일 머리글 */
    .weekday-head {
        font-size: 13px;
        font-weight: 600;
        color: #8B95A1;
        text-align: center;
        padding: 10px 0 6px 0;
    }

    /* 날짜 카드 */
    .day-card {
        border: 1px solid #F2F4F6;
        border-radius: 16px;
        background: #FFFFFF;
        padding: 14px 14px 16px 14px;
        min-height: 190px;
        margin-bottom: 12px;
    }
    .day-card.today {
        border: 1px solid #3182F6;
    }
    .day-card.empty {
        background: #FAFBFC;
    }

    .day-head {
        display: flex;
        align-items: center;
        gap: 6px;
        margin-bottom: 10px;
    }
    .day-num {
        font-size: 17px;
        font-weight: 700;
        color: #191F28;
        letter-spacing: -0.3px;
    }
    .day-dow {
        font-size: 12px;
        color: #B0B8C1;
    }
    .today-badge {
        margin-left: auto;
        font-size: 10px;
        font-weight: 700;
        color: #FFFFFF;
        background: #3182F6;
        border-radius: 999px;
        padding: 3px 8px;
        letter-spacing: 0.3px;
    }

    .meal-block { margin-bottom: 12px; }
    .meal-title {
        font-size: 12px;
        font-weight: 700;
        margin-bottom: 4px;
    }
    .menu-line {
        font-size: 13px;
        color: #4E5968;
        line-height: 1.65;
        word-break: keep-all;
    }
    .empty-text {
        font-size: 13px;
        color: #C9CDD2;
    }

    /* 사이드바 */
    section[data-testid="stSidebar"] { background: #FBFCFD; }
    .allergy-item { font-size: 13px; color: #4E5968; line-height: 1.8; }
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


@st.cache_data(ttl=1800, show_spinner=False)
def fetch_month_meals(api_key: str, atpt_code: str, school_code: str, year: int, month: int):
    """
    한 달치 급식 정보를 한 번에 가져옵니다.

    반환값: (급식자료 딕셔너리, 오류메시지)
    - 급식자료는 {"20260401": [{"name": "중식", "menus": [...]}, ...]} 형태입니다.
    - 오류가 없으면 오류메시지는 None 입니다.
    """
    # 그 달의 말일을 계산합니다. monthrange는 (1일의 요일, 그 달의 일수)를 돌려줍니다.
    last_day = calendar.monthrange(year, month)[1]
    from_ymd = f"{year}{month:02d}01"
    to_ymd = f"{year}{month:02d}{last_day:02d}"

    params = {
        "KEY": api_key,
        "Type": "json",
        "pIndex": 1,
        "pSize": 1000,
        "ATPT_OFCDC_SC_CODE": atpt_code,
        "SD_SCHUL_CODE": school_code,
        "MLSV_FROM_YMD": from_ymd,
        "MLSV_TO_YMD": to_ymd,
    }

    try:
        response = requests.get(NEIS_URL, params=params, timeout=10)
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
            # 데이터가 없는 것은 오류가 아니라 '급식이 없는 달'입니다.
            return {}, None
        return {}, f"나이스에서 받은 안내: {message} (코드: {code})"

    rows = []
    for block in data["mealServiceDietInfo"]:
        if "row" in block:
            rows = block["row"]

    meals_by_date = {}
    for row in rows:
        date_key = row.get("MLSV_YMD", "")
        meal_name = row.get("MMEAL_SC_NM", "급식")
        dish = row.get("DDISH_NM", "")
        # 메뉴는 <br/>로 구분되어 옵니다. 줄 단위로 나눠 둡니다.
        menus = [line.strip() for line in re.split(r"<br\s*/?>", dish) if line.strip()]
        meals_by_date.setdefault(date_key, []).append(
            {"name": meal_name, "code": row.get("MMEAL_SC_CODE", "9"), "menus": menus}
        )

    # 하루 안에서 조식 → 중식 → 석식 순서로 정렬합니다.
    for date_key in meals_by_date:
        meals_by_date[date_key].sort(key=lambda m: m["code"])

    return meals_by_date, None


# ---------------------------------------------------------------------------
# 5. 사이드바 - 학교 정보와 표시 옵션
# ---------------------------------------------------------------------------

with st.sidebar:
    st.markdown("### 학교 정보")
    atpt_code = st.text_input("시도교육청코드", value=DEFAULT_ATPT_CODE)
    school_code = st.text_input("표준학교코드", value=DEFAULT_SCHOOL_CODE)
    st.caption("코드는 나이스 오픈API 학교기본정보에서 확인할 수 있습니다.")

    st.markdown("---")
    st.markdown("### 표시 옵션")
    convert_allergy = st.toggle("알레르기 식품명으로 변환", value=True)
    st.caption("끄면 메뉴 옆에 번호가 그대로 표시됩니다.")

    with st.expander("알레르기 번호 대응표 보기"):
        for number, name in ALLERGY_TABLE.items():
            st.markdown(
                f'<div class="allergy-item">{number}. {name}</div>',
                unsafe_allow_html=True,
            )


# ---------------------------------------------------------------------------
# 6. API 키 확인
# ---------------------------------------------------------------------------

api_key = st.secrets.get("NEIS_KEY", "") if hasattr(st, "secrets") else ""

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
# 7. 상단 - 연도 / 월 / 급식 종류 선택
# ---------------------------------------------------------------------------

today = dt.date.today()

st.markdown('<div class="app-title">우리 학교 급식 달력</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="app-subtitle">한 달 급식을 한눈에 확인하세요.</div>',
    unsafe_allow_html=True,
)

col_year, col_month, col_type = st.columns([1, 1, 2])

with col_year:
    year_options = list(range(today.year - 2, today.year + 2))
    year = st.selectbox("연도", year_options, index=year_options.index(today.year))

with col_month:
    month = st.selectbox("월", list(range(1, 13)), index=today.month - 1)

with col_type:
    meal_filter = st.radio(
        "급식 종류",
        ["전체 보기", "중식만 보기", "석식만 보기"],
        horizontal=True,
    )

st.write("")


# ---------------------------------------------------------------------------
# 8. 급식 정보 불러오기
# ---------------------------------------------------------------------------

with st.spinner("급식 정보를 불러오는 중입니다."):
    meals_by_date, api_error = fetch_month_meals(api_key, atpt_code, school_code, year, month)

if api_error:
    st.error(f"통신 오류: {api_error}")
    st.stop()


# ---------------------------------------------------------------------------
# 9. 달력 그리기
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
        f"{badge}"
        "</div>"
    )

    day_meals = meals_by_date.get(date_key, [])

    # 급식 자료 자체가 없는 날 (주말이나 방학)
    if not day_meals:
        return f'<div class="{card_class} empty">{head}<div class="empty-text">급식 없음</div></div>'

    # 선택한 급식 종류로 걸러 냅니다.
    if meal_filter == "중식만 보기":
        day_meals = [m for m in day_meals if m["name"] == "중식"]
    elif meal_filter == "석식만 보기":
        day_meals = [m for m in day_meals if m["name"] == "석식"]

    if not day_meals:
        return f'<div class="{card_class}">{head}<div class="empty-text">해당 식단 없음</div></div>'

    blocks = []
    for meal in day_meals:
        color = MEAL_COLORS.get(meal["name"], ETC_MEAL_COLOR)
        lines = []
        for menu in meal["menus"]:
            text = convert_allergy_numbers(menu) if convert_allergy else menu
            lines.append(f'<div class="menu-line">{html.escape(text)}</div>')
        blocks.append(
            f'<div class="meal-block">'
            f'<div class="meal-title" style="color:{color}">{html.escape(meal["name"])}</div>'
            f'{"".join(lines)}'
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
    # 그중 앞 5칸(평일)만 사용합니다. 그 달에 속하지 않는 날은 0으로 채워져 있습니다.
    for week in calendar.monthcalendar(year, month):
        weekdays = week[:5]
        if not any(weekdays):
            continue  # 평일이 하나도 없는 주는 건너뜁니다.

        week_cols = st.columns(5)
        for index, day in enumerate(weekdays):
            if day == 0:
                week_cols[index].markdown(
                    '<div class="day-card empty"></div>', unsafe_allow_html=True
                )
            else:
                week_cols[index].markdown(build_day_card(day, index), unsafe_allow_html=True)

except Exception as error:  # noqa: BLE001
    st.error(f"화면 구성 오류: 달력을 그리는 중 문제가 생겼습니다. ({error})")

st.caption("자료 출처: 나이스 교육정보 개방 포털")
