import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo


# ---------------------------------------
# 1. 기본 설정
# ---------------------------------------

st.set_page_config(
    page_title="어제의 박스오피스",
    page_icon="🎬",
    layout="wide"
)

st.title("🎬 어제의 박스오피스")
st.write("한국 시간 기준 어제의 일일 박스오피스를 보여줍니다.")


# ---------------------------------------
# 2. 한국 시간 기준으로 '어제' 계산
# ---------------------------------------
# Streamlit Cloud 서버의 시간이 한국 시간이 아닐 수 있으므로
# 반드시 한국 시간(KST)을 기준으로 날짜를 계산합니다.

KST = ZoneInfo("Asia/Seoul")

now_kst = datetime.now(KST)
yesterday = now_kst.date() - timedelta(days=1)

# KOBIS API가 요구하는 날짜 형식: YYYYMMDD
target_dt = yesterday.strftime("%Y%m%d")

# 화면에 보여줄 날짜
display_date = yesterday.strftime("%Y년 %m월 %d일")


# ---------------------------------------
# 3. KOBIS API에서 데이터를 가져오는 함수
# ---------------------------------------
# @st.cache_data를 사용하면 같은 날짜를 다시 요청했을 때
# 약 1시간 동안 기존 결과를 재사용합니다.
#
# 따라서 같은 날짜에 API를 계속 호출하지 않습니다.

@st.cache_data(ttl=3600)
def get_boxoffice(target_date):
    try:
        # Streamlit Cloud의 Secrets에서 인증키를 가져옵니다.
        # 실제 인증키를 코드에 직접 적지 않습니다.
        api_key = st.secrets["KOBIS_KEY"]

    except Exception:
        return {
            "success": False,
            "message": (
                "KOBIS 인증키를 불러오지 못했습니다.\n\n"
                "Streamlit Cloud의 Secrets에 `KOBIS_KEY`가 "
                "정확히 등록되어 있는지 확인하세요."
            ),
            "data": None
        }

    url = (
        "https://www.kobis.or.kr/"
        "kobisopenapi/webservice/rest/boxoffice/"
        "searchDailyBoxOfficeList.json"
    )

    params = {
        "key": api_key,
        "targetDt": target_date
    }

    try:
        # API 요청
        response = requests.get(
            url,
            params=params,
            timeout=10
        )

        # HTTP 오류가 있는 경우
        response.raise_for_status()

        # JSON으로 변환
        result = response.json()

    except requests.exceptions.Timeout:
        return {
            "success": False,
            "message": (
                "KOBIS API 요청 시간이 초과되었습니다.\n\n"
                "잠시 후 다시 실행해 보거나 "
                "인터넷 연결 및 KOBIS API 상태를 확인하세요."
            ),
            "data": None
        }

    except requests.exceptions.RequestException as e:
        return {
            "success": False,
            "message": (
                "KOBIS API에 요청하지 못했습니다.\n\n"
                "인터넷 연결이나 KOBIS API 주소가 정상인지 확인하세요.\n\n"
                f"오류 내용: {e}"
            ),
            "data": None
        }

    except ValueError:
        return {
            "success": False,
            "message": (
                "KOBIS API에서 정상적인 JSON 데이터를 받지 못했습니다.\n\n"
                "잠시 후 다시 시도해 주세요."
            ),
            "data": None
        }

    # ---------------------------------------
    # 4. 인증키 오류 등 faultInfo 확인
    # ---------------------------------------
    # KOBIS는 인증키가 틀려도 HTTP 상태코드가 200일 수 있습니다.
    # 따라서 faultInfo가 있는지 반드시 확인합니다.

    if "faultInfo" in result:
        fault_info = result["faultInfo"]

        # faultInfo 안의 오류 메시지를 최대한 찾아서 보여줍니다.
        error_message = (
            fault_info.get("message")
            or fault_info.get("errorMessage")
            or "KOBIS API에서 오류가 발생했습니다."
        )

        return {
            "success": False,
            "message": (
                "KOBIS API에서 오류가 발생했습니다.\n\n"
                f"{error_message}\n\n"
                "확인할 사항:\n"
                "• Streamlit Secrets의 KOBIS_KEY가 정확한지 확인\n"
                "• KOBIS Open API 사용이 가능한 인증키인지 확인\n"
                "• 조회 날짜가 올바른지 확인"
            ),
            "data": None
        }

    # ---------------------------------------
    # 5. boxOfficeResult 확인
    # ---------------------------------------

    box_office = result.get("boxOfficeResult")

    if not box_office:
        return {
            "success": False,
            "message": (
                "박스오피스 결과를 찾을 수 없습니다.\n\n"
                "KOBIS API 응답 형식이나 API 상태를 확인해 주세요."
            ),
            "data": None
        }

    # 영화 목록 가져오기
    movie_list = box_office.get("dailyBoxOfficeList", [])

    # 영화 목록이 비어 있는 경우
    if not movie_list:
        return {
            "success": False,
            "message": (
                f"{target_date} 날짜의 영화 목록이 없습니다.\n\n"
                "확인할 사항:\n"
                "• KOBIS에서 해당 날짜의 일일 박스오피스가 집계되었는지 확인\n"
                "• 조회 날짜가 정상적으로 계산되었는지 확인\n"
                "• KOBIS API가 정상적으로 응답하고 있는지 확인"
            ),
            "data": None
        }

    return {
        "success": True,
        "message": "",
        "data": movie_list
    }


# ---------------------------------------
# 6. API 호출
# ---------------------------------------

result = get_boxoffice(target_dt)


# ---------------------------------------
# 7. 요청 실패 시 안내
# ---------------------------------------

if not result["success"]:
    st.error(result["message"])
    st.stop()


# ---------------------------------------
# 8. 영화 데이터를 표 형태로 만들기
# ---------------------------------------

movie_list = result["data"]

df = pd.DataFrame(movie_list)


# ---------------------------------------
# 9. 숫자 데이터를 숫자형으로 변환
# ---------------------------------------
# KOBIS API에서는 숫자도 문자열로 전달됩니다.
# 그래프와 정렬에 사용할 수 있도록 숫자로 변환합니다.

numeric_columns = [
    "rank",
    "audiCnt",
    "audiAcc",
    "scrnCnt"
]

for column in numeric_columns:
    df[column] = pd.to_numeric(
        df[column],
        errors="coerce"
    ).fillna(0).astype(int)


# ---------------------------------------
# 10. 순위 기준으로 정렬
# ---------------------------------------

df = df.sort_values("rank").reset_index(drop=True)


# ---------------------------------------
# 11. 조회 날짜 표시
# ---------------------------------------

st.subheader(f"📅 {display_date} 박스오피스")

st.caption(
    "KOBIS 일일 박스오피스 기준 · 한국 시간으로 자동 계산된 어제 날짜"
)


# ---------------------------------------
# 12. 1위 영화 표시
# ---------------------------------------

if len(df) > 0:

    first_movie = df.iloc[0]

    st.subheader("🥇 1위 영화")

    st.markdown(
        f"## {first_movie['movieNm']}"
    )

    # 1위 영화의 주요 지표 3개를 크게 보여줍니다.
    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric(
            "어제 관객수",
            f"{first_movie['audiCnt']:,}명"
        )

    with col2:
        st.metric(
            "누적 관객수",
            f"{first_movie['audiAcc']:,}명"
        )

    with col3:
        st.metric(
            "스크린수",
            f"{first_movie['scrnCnt']:,}개"
        )


# ---------------------------------------
# 13. 전체 박스오피스 표
# ---------------------------------------

st.subheader("📊 전체 박스오피스")

# 사용자에게 보여줄 열만 선택합니다.
table_df = df[
    [
        "rank",
        "movieNm",
        "openDt",
        "audiCnt",
        "audiAcc",
        "scrnCnt"
    ]
].copy()

# 표의 열 이름을 한국어로 변경합니다.
table_df.columns = [
    "순위",
    "영화명",
    "개봉일",
    "관객수",
    "누적관객",
    "스크린수"
]

# 숫자를 보기 좋게 쉼표로 표시합니다.
# 실제 데이터는 이미 숫자로 변환했기 때문에
# 정렬과 그래프에는 숫자값이 사용됩니다.
display_df = table_df.copy()

display_df["관객수"] = display_df["관객수"].map(
    lambda x: f"{x:,}"
)

display_df["누적관객"] = display_df["누적관객"].map(
    lambda x: f"{x:,}"
)

display_df["스크린수"] = display_df["스크린수"].map(
    lambda x: f"{x:,}"
)

st.dataframe(
    display_df,
    use_container_width=True,
    hide_index=True
)


# ---------------------------------------
# 14. 관객수 상위 5편 막대그래프
# ---------------------------------------

st.subheader("📈 관객수 상위 5편")

# 숫자형 관객수를 기준으로 상위 5편을 선택합니다.
top5 = (
    df.sort_values(
        "audiCnt",
        ascending=False
    )
    .head(5)
    .copy()
)

# 영화명을 인덱스로 설정합니다.
chart_df = top5.set_index("movieNm")[["audiCnt"]]

# Streamlit의 기본 막대그래프를 사용합니다.
st.bar_chart(
    chart_df,
    y="audiCnt",
    x_label="영화",
    y_label="관객수"
)


# ---------------------------------------
# 15. 안내 문구
# ---------------------------------------

st.caption(
    "※ 관객수·누적관객·스크린수는 KOBIS API의 값을 숫자로 변환하여 표시합니다."
)

st.caption(
    "※ 같은 조회 날짜의 결과는 약 1시간 동안 캐시되어 API를 다시 호출하지 않습니다."
)
