import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import datetime
import feedparser

# 1. 앱 기본 설정
st.set_page_config(page_title="스윙 알리미 V10.0", page_icon="🚨", layout="wide")

if "my_tickers" not in st.session_state:
    st.session_state["my_tickers"] = []

st.title("🚨 실시간 스윙 스캐너 & 정밀 자금 관리")

tab1, tab2, tab3 = st.tabs(["🔍 종목 스캐너", "💰 정밀 분할 매수", "🌍 세계 경제 뉴스"])

# --- [엔진] 뉴스 수집 ---
def get_company_news_3mo(ticker):
    news_list = []
    try:
        q = f"{ticker}+stock+when:90d"
        url = f"https://news.google.com/rss/search?q={q}&hl=en-US&gl=US&ceid=US:en"
        feed = feedparser.parse(url)
        for entry in feed.entries[:8]:
            news_list.append({"title": entry.title, "link": entry.link})
    except: pass
    return news_list

# ==========================================
# 탭 1: 종목 스캐너
# ==========================================
with tab1:
    st.subheader("📝 종목 분석")
    col_in, col_bt = st.columns([3, 1])
    with col_in:
        new_tk = st.text_input("티커 입력", placeholder="예: ALVO, AAPL").upper()
    with col_bt:
        st.write(""); st.write("")
        if st.button("추가"):
            if new_tk and new_tk not in st.session_state["my_tickers"]:
                st.session_state["my_tickers"].append(new_tk)
                
    selected_tickers = st.multiselect("스캔 목록", options=st.session_state["my_tickers"], default=st.session_state["my_tickers"])
    
    if st.button("🚀 종합 스캔 시작", use_container_width=True):
        for ticker in selected_tickers:
            try:
                stock = yf.Ticker(ticker)
                hist = stock.history(period="6mo")
                if hist.empty: continue
                curr_price = hist['Close'].iloc[-1]
                st.info(f"### 📈 [{ticker}] 현재가: ${curr_price:.2f}")
                with st.expander(f"📊 {ticker} 뉴스 및 공시"):
                    st.markdown(f"🏛️ [SEC 공식 공시](https://www.sec.gov/cgi-bin/browse-edgar?CIK={ticker}&action=getcompany) | 📢 [IR 게시판](https://www.google.com/search?q={ticker}+Investor+Relations)")
                    st.write("---")
                    for n in get_company_news_3mo(ticker):
                        st.markdown(f"- [{n['title']}]({n['link']})")
            except: st.error(f"{ticker} 분석 실패")

# ==========================================
# 탭 2: 정밀 분할 매수 계산기 (회차별 하락폭 설정)
# ==========================================
with tab2:
    st.subheader("💰 회차별 하락폭 지정형 5분할 계산기")
    
    # 1. 기본 설정
    st.markdown("#### ⚙️ 기본 설정")
    c_set1, c_set2, c_set3 = st.columns(3)
    with c_set1:
        currency = st.radio("통화", ["USD ($)", "KRW (원)"])
        symbol = "$" if currency == "USD ($)" else "원"
    with c_set2:
        total_budget = st.number_input(f"총 예산 ({symbol})", value=1000.0 if symbol=="$" else 3100000.0, step=100.0)
    with c_set3:
        start_price = st.number_input(f"1차 진입가 ({symbol})", value=10.0 if symbol=="$" else 15000.0, step=0.1)

    st.write("---")

    # 2. 회차별 하락폭 설정
    st.markdown("#### 📉 회차별 추가 매수 조건 (전회차 대비 하락률)")
    c_rate1, c_rate2, c_rate3, c_rate4 = st.columns(4)
    with c_rate1:
        r2 = st.number_input("2차 매수 하락폭 (%)", value=5.0, step=0.5)
    with c_rate2:
        r3 = st.number_input("3차 매수 하락폭 (%)", value=10.0, step=0.5)
    with c_rate3:
        r4 = st.number_input("4차 매수 하락폭 (%)", value=15.0, step=0.5)
    with c_rate4:
        r5 = st.number_input("5차 매수 하락폭 (%)", value=20.0, step=0.5)

    st.write("---")
    
    if total_budget > 0 and start_price > 0:
        # 비중은 1:2 마틴게일 유지 (합계 31)
        base_unit = total_budget / 31
        
        rates = [0, r2, r3, r4, r5] # 1차는 0% 하락
        data = []
        target_price = start_price
        
        for i in range(1, 6):
            weight = 2**(i-1)
            buy_amount = base_unit * weight
            
            # 2차부터는 사용자가 입력한 해당 회차의 하락률 적용
            if i > 1:
                target_price = target_price * (1 - (rates[i-1] / 100))
            
            data.append({
                "회차": f"{i}차 매수",
                "비중": f"{weight}배",
                "매수 목표가": f"{symbol} {target_price:,.2f}",
                "매수 금액": f"{symbol} {buy_amount:,.0f}",
                "하락 조건": f"전회차 대비 -{rates[i-1]}%" if i > 1 else "진입가"
            })
        
        # 결과 표 출력
        df = pd.DataFrame(data)
        st.table(df)
        
        # 하단 요약
        st.success(f"✅ **초기 진입(1차) 추천 금액:** {symbol} {int(base_unit):,}")
        st.warning(f"⚠️ **전략 가이드:** 하락 폭을 크게 잡을수록 공격적인 물타기가 가능하며, 작게 잡을수록 평단가가 촘촘해집니다.")

# ==========================================
# 탭 3: 세계 경제 뉴스
# ==========================================
with tab3:
    st.subheader("🌍 글로벌 경제 실시간 헤드라인")
    try:
        feed = feedparser.parse("https://news.google.com/rss/search?q=global+economy+market+when:24h&hl=en-US&gl=US&ceid=US:en")
        for entry in feed.entries[:10]:
            st.markdown(f"📍 [{entry.title}]({entry.link})")
            st.write("")
    except: st.write("뉴스를 불러올 수 없습니다.")

