# =============================================================================
# 전 세계 자연재해 현황 대시보드 (NASA EONET API 활용)
#
# 이 애플리케이션을 실행하려면 먼저 다음 라이브러리를 설치해야 합니다.
# pip install streamlit pandas requests folium streamlit-folium
#
# 터미널에서 다음 명령어를 실행하여 앱을 시작하세요:
# streamlit run app.py
# =============================================================================

import streamlit as st
import pandas as pd
import requests
from streamlit_folium import folium_static
import folium

# --- 페이지 설정 ---
st.set_page_config(
    page_title="자연재해 현황 대시보드",
    page_icon="🌍",
    layout="wide"
)

# --- 제목 ---
st.title("🌍 전 세계 자연재해 현황 대시보드")
st.markdown("NASA EONET(Earth Observatory Natural Event Tracker) API를 사용하여 특정 기간의 자연재해 데이터를 시각화합니다.")

# --- 데이터 로딩 및 캐싱 ---
@st.cache_data(ttl=3600)  # 1시간 동안 데이터 캐싱
def get_eonet_data(days=3650):
    """
    NASA EONET API에서 지난 지정된 일수 동안의 자연재해 데이터를 가져옵니다.
    'closed' 상태의 이벤트만 가져와 이미 종료된 재해를 대상으로 합니다.
    """
    api_url = f"https://eonet.gsfc.nasa.gov/api/v3/events?days={days}&status=closed"
    try:
        response = requests.get(api_url)
        response.raise_for_status()  # HTTP 오류 발생 시 예외 처리
        data = response.json()
        return data.get('events', [])
    except requests.exceptions.RequestException as e:
        st.error(f"API에서 데이터를 가져오는 데 실패했습니다: {e}")
        return None

# 데이터 로드
events_data = get_eonet_data()

# --- 데이터 처리 ---
if events_data:
    # JSON 데이터를 Pandas DataFrame으로 변환
    df = pd.json_normalize(events_data)

    # 필요한 컬럼만 선택 및 이름 정리
    df = df[['id', 'title', 'categories', 'geometry']]
    df['category'] = df['categories'].apply(lambda x: x[0]['title'] if x else 'N/A')
    
    # 시간 및 좌표 정보 추출
    # geometry 리스트의 첫 번째 요소에서 날짜와 좌표를 가져옵니다.
    df['date'] = df['geometry'].apply(lambda geoms: geoms[0].get('date') if geoms else None)
    df['latitude'] = df['geometry'].apply(lambda geoms: geoms[0]['coordinates'][1] if geoms and len(geoms[0].get('coordinates', [])) > 1 else None)
    df['longitude'] = df['geometry'].apply(lambda geoms: geoms[0]['coordinates'][0] if geoms and len(geoms[0].get('coordinates', [])) > 0 else None)
    
    # 데이터 정제
    df.dropna(subset=['latitude', 'longitude', 'date'], inplace=True)
    df['date'] = pd.to_datetime(df['date'])
    df['year'] = df['date'].dt.year

    st.success(f"최근 10년간 총 {len(df)}개의 자연재해 데이터를 성공적으로 불러왔습니다.")

    # --- 사이드바 필터 ---
    st.sidebar.header("🔍 필터 설정")

    # 연도 선택
    # unique()로 고유 연도를 가져오고, sorted()로 정렬합니다.
    available_years = sorted(df['year'].unique(), reverse=True)
    selected_year = st.sidebar.selectbox(
        '연도를 선택하세요',
        options=available_years
    )

    # 재해 유형 선택 (다중 선택 가능)
    all_categories = sorted(df['category'].unique())
    selected_categories = st.sidebar.multiselect(
        '재해 유형을 선택하세요 (다중 선택 가능)',
        options=all_categories,
        default=all_categories # 기본적으로 모든 유형 선택
    )

    # --- 데이터 필터링 ---
    filtered_df = df[
        (df['year'] == selected_year) &
        (df['category'].isin(selected_categories))
    ].copy() # SettingWithCopyWarning 방지를 위해 .copy() 사용

    # --- 메인 콘텐츠 표시 ---
    st.header(f"📅 {selected_year}년 | {', '.join(selected_categories) if selected_categories else '모든'} 재해 현황")

    if not filtered_df.empty:
        # 1. 요약 정보
        st.metric(label="선택된 재해 건수", value=f"{len(filtered_df)} 건")
        
        # 2. 데이터 테이블
        with st.expander("데이터 테이블 보기"):
            # 날짜 형식을 'YYYY-MM-DD'로 변경하여 가독성 향상
            filtered_df['date_str'] = filtered_df['date'].dt.strftime('%Y-%m-%d')
            st.dataframe(filtered_df[['title', 'category', 'date_str', 'latitude', 'longitude']])
            
        # 3. Folium을 사용한 지도 시각화
        st.subheader("🗺️ 재해 발생 위치 지도")
        
        # 지도의 중심점을 필터링된 데이터의 평균 위치로 설정
        map_center = [filtered_df['latitude'].mean(), filtered_df['longitude'].mean()]
        m = folium.Map(location=map_center, zoom_start=4)

        # 각 재해 위치에 마커 추가
        for idx, row in filtered_df.iterrows():
            popup_html = f"""
            <h5>{row['title']}</h5><hr>
            <b>유형:</b> {row['category']}<br>
            <b>날짜:</b> {row['date'].strftime('%Y-%m-%d')}
            """
            folium.Marker(
                location=[row['latitude'], row['longitude']],
                popup=folium.Popup(popup_html, max_width=300),
                tooltip=row['title'],
                icon=folium.Icon(color='red', icon='info-sign')
            ).add_to(m)

        # 스트림릿에 Folium 지도 표시
        folium_static(m, width=900, height=600)

    else:
        st.warning("선택하신 조건에 해당하는 재해 데이터가 없습니다.")

else:
    st.error("데이터를 불러오는 데 실패했습니다. 잠시 후 다시 시도해주세요.")