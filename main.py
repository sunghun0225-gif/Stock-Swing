import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import datetime
import feedparser
import matplotlib.pyplot as plt
import io

# 1. 앱 기본 설정
st.set_page_config(page_title="스윙 알리미 V12.2", page_icon="🚨", layout="wide")

# 세션 상태 초기화 (목록 관리용)
for key in ["my_tickers_us", "my_tickers_kr"]:
    if key not in st.session_state:
        st.session_state[key] = []

st.title("🚨 글로벌 스윙 스캐너 & 정밀 매매 가이드")

tab1, tab2, tab3, tab4 = st.tabs(["🇺🇸 미국 종목", "🇰🇷 한국 종목", "💰 정밀 분할 매수", "🌍 세계 경제 뉴스"])

# --- [유틸리티] 뉴스 수집 함수 ---
def get_stock_news(ticker, market="US"):
    news_list = []
    try:
        query = f"{ticker}+stock" if market == "US" else f"{ticker}+주식"
        hl, gl, ceid = ('en-US', 'US', 'US:en') if market == 'US' else ('ko-KR', 'KR', 'KR:ko')
        url = f"https://news.google.com/rss/search?q={query}+when:90d&hl={hl}&gl={gl}&ceid={ceid}"
        feed = feedparser.parse(url)
        for entry in feed.entries[:8]:
            news_list.append({"title": entry.title, "link": entry.link})
    except: pass
    return news_list

# --- [유틸리티] 이미지 변환 (메모리 관리 포함) ---
def export_as_image(df, title):
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.axis('off')
    ax.set_title(title, fontsize=16, weight='bold', pad=20)
    table = ax.table(cellText=df.values, colLabels=df.columns, cellLoc='center', loc='center')
    table.auto_set_font_size(False)
    table.set_fontsize(11)
    table.scale(1.2, 2.5)
    
    buf = io.BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight', dpi=150)
    plt.close(fig) # 메모리 효율을 위해 차트 객체 닫기
    buf.seek(0)
    return buf

# ==========================================
# 탭 1: 미국 종목 스캐너
# ==========================================
with tab1:
    st.subheader("🇺🇸 미국 시장 종목 분석")
    u_col1, u_col2, u_col3 = st.columns([3, 1, 1])
    with u_col1:
        new_us = st.text_input("미국 티커 입력", placeholder="예: TSLA, AAPL", key="us_in").upper()
    if u_col2.button("종목 추가", key="us_add") and new_us:
        if new_us not in st.session_state["my_tickers_us"]:
            st.session_state["my_tickers_us"].append(new_us)
    if u_col3.button("목록 초기화", key="us_clear"):
        st.session_state["my_tickers_us"] = []
    
    sel_us = st.multiselect("스캔 목록", options=st.session_state["my_tickers_us"], default=st.session_state["my_tickers_us"])
    st.session_state["my_tickers_us"] = sel_us

    if st.button("🚀 미국 종목 스캔 시작", use_container_width=True):
        for t in sel_us:
            s = yf.Ticker(t)
            h = s.history(period="5d")
            if not h.empty:
                curr_p = h['Close'].iloc[-1]
                prev_p = h['Close'].iloc[-2] if len(h) > 1 else curr_p
                delta = curr_p - prev_p
                st.metric(label=f"Ticker: {t}", value=f"${curr_p:.2f}", delta=f"{delta:.2f}")
                with st.expander("뉴스 및 공시"):
                    st.markdown(f"🏛️ [SEC 공식 공시](https://www.sec.gov/cgi-bin/browse-edgar?CIK={t}&action=getcompany)")
                    for n in get_stock_news(t, "US"): st.markdown(f"- [{n['title']}]({n['link']})")
            st.write("---")

# ==========================================
# 탭 2: 한국 종목 스캐너 (최적화)
# ==========================================
with tab2:
    st.subheader("🇰🇷 한국 시장 종목 분석")
    k_col1, k_col2, k_col3 = st.columns([3, 1, 1])
    with k_col1:
        new_kr = st.text_input("한국 코드 입력", placeholder="예: 005930", key="kr_in")
    if k_col2.button("종목 추가", key="kr_add") and new_kr:
        if new_kr not in st.session_state["my_tickers_kr"]:
            st.session_state["my_tickers_kr"].append(new_kr)
    if k_col3.button("목록 초기화", key="kr_clear"):
        st.session_state["my_tickers_kr"] = []

    sel_kr = st.multiselect("스캔 목록", options=st.session_state["my_tickers_kr"], default=st.session_state["my_tickers_kr"])
    st.session_state["my_tickers_kr"] = sel_kr
    
    if st.button("🚀 한국 종목 스캔 시작", use_container_width=True):
        for t in sel_kr:
            # 접미사가 없으면 .KS부터 시도
            found = False
            check_list = [t] if "." in t else [t + ".KS", t + ".KQ"]
            for full_t in check_list:
                s = yf.Ticker(full_t)
                h = s.history(period="5d")
                if not h.empty:
                    name = s.info.get('shortName', t)
                    curr_p = h['Close'].iloc[-1]
                    prev_p = h['Close'].iloc[-2] if len(h) > 1 else curr_p
                    st.metric(label=f"{name} ({full_t})", value=f"{int(curr_p):,} 원", delta=f"{int(curr_p-prev_p):,} 원")
                    with st.expander("뉴스 및 공시"):
                        st.markdown(f"🏛️ [네이버 증권 공시](https://finance.naver.com/item/news.naver?code={t.split('.')[0]})")
                        for n in get_stock_news(full_t, "KR"): st.markdown(f"- [{n['title']}]({n['link']})")
                    found = True
                    break
            if not found: st.error(f"[{t}] 데이터를 찾을 수 없습니다.")
            st.write("---")

# ==========================================
# 탭 3: 정밀 분할 매수 계산기
# ==========================================
with tab3:
    st.subheader("💰 현재가 대비 지점별 정밀 계산기")
    
    c1, c2, c3 = st.columns(3)
    currency = c1.radio("통화 선택", ["USD ($)", "KRW (원)"])
    symbol = "$" if currency == "USD ($)" else "원"
    total_budget = c2.number_input(f"총 투입 예산 ({symbol})", value=1000.0 if symbol=="$" else 3000000.0)
    start_price = c3.number_input(f"현재 진입가 ({symbol})", value=10.0 if symbol=="$" else 50000.0)

    st.markdown("#### 📉 진입가 대비 누적 하락 목표치 (%)")
    r_cols = st.columns(4)
    rates = [0, 
             r_cols[0].number_input("2차 하락(%)", value=5.0),
             r_cols[1].number_input("3차 하락(%)", value=10.0),
             r_cols[2].number_input("4차 하락(%)", value=15.0),
             r_cols[3].number_input("5차 하락(%)", value=20.0)]

    if total_budget > 0 and start_price > 0:
        base = total_budget / 31
        calc_data = []
        for i in range(1, 6):
            w = 2**(i-1)
            tp = start_price * (1 - (rates[i-1] / 100))
            calc_data.append({
                "회차": f"{i}차 매수",
                "비중": f"{w}배",
                "목표가": f"{symbol}{tp:,.2f}" if symbol=="$" else f"{int(tp):,}원",
                "금액": f"{symbol}{base * w:,.0f}",
                "누적 하락": f"-{rates[i-1]}%"
            })
        
        df_res = pd.DataFrame(calc_data)
        st.table(df_res)
        
        img = export_as_image(df_res, "Trading Plan Strategy")
        st.download_button("📸 계산 결과 이미지 저장", data=img, file_name="trading_plan.png", mime="image/png", use_container_width=True)

# ==========================================
# 탭 4: 세계 경제 뉴스
# ==========================================
with tab4:
    if st.button("🔄 뉴스 새로고침", use_container_width=True): st.rerun()
    feed = feedparser.parse("https://news.google.com/rss/search?q=global+economy+market+when:24h&hl=en-US&gl=US&ceid=US:en")
    for e in feed.entries[:12]:
        st.markdown(f"📍 [{e.title}]({e.link})")
        st.write("")
