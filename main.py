import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import datetime
import feedparser

# 1. 앱 기본 설정
st.set_page_config(page_title="스윙 알리미 V9.0", page_icon="🚨", layout="wide")

if "my_tickers" not in st.session_state:
    st.session_state["my_tickers"] = []

st.title("🚨 실시간 스윙 스캐너 & 스마트 자금 관리")

tab1, tab2, tab3 = st.tabs(["🔍 종목 스캐너", "💰 스마트 분할 매수", "🌍 세계 경제 뉴스"])

# --- [엔진] 뉴스 수집 (3개월) ---
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
# 탭 1: 종목 스캐너 (기능 유지)
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
                info = stock.info
                if hist.empty: continue
                
                curr_price = hist['Close'].iloc[-1]
                st.info(f"### 📈 [{ticker}] 현재가: ${curr_price:.2f}")
                
                with st.expander(f"📊 {ticker} 뉴스 및 공시"):
                    st.markdown(f"🏛️ [SEC 공식 공시](https://www.sec.gov/cgi-bin/browse-edgar?CIK={ticker}&action=getcompany) | 📢 [IR 게시판](https://www.google.com/search?q={ticker}+Investor+Relations)")
                    st.write("---")
                    c_news = get_company_news_3mo(ticker)
                    for n in c_news:
                        st.markdown(f"- [{n['title']}]({n['link']})")
            except: st.error(f"{ticker} 분석 실패")

# ==========================================
# 탭 2: 스마트 분할 매수 계산기 (업그레이드)
# ==========================================
with tab2:
    st.subheader("💰 1:2 비율 5분할 물타기 계산기")
    
    # 설정 섹션
    col1, col2, col3 = st.columns(3)
    with col1:
        currency = st.radio("통화 선택", ["USD ($)", "KRW (원)"])
        symbol = "$" if currency == "USD ($)" else "원"
    with col2:
        total_budget = st.number_input(f"총 투입 금액 ({symbol})", value=1000.0 if symbol=="$" else 3100000.0, step=100.0)
    with col3:
        start_price = st.number_input(f"1차 진입 가격 ({symbol})", value=10.0 if symbol=="$" else 15000.0, step=0.1)

    drop_rate = st.slider("추가 매수 하락 폭 (%)", min_value=1.0, max_value=30.0, value=10.0, step=0.5)
    
    st.write("---")
    
    if total_budget > 0 and start_price > 0:
        # 1:2 비중 계산 (1, 2, 4, 8, 16 합계 31)
        base_unit = total_budget / 31
        
        data = []
        current_target_price = start_price
        
        for i in range(1, 6):
            weight = 2**(i-1)
            buy_amount = base_unit * weight
            
            # 1회차는 시작가, 이후는 하락률 적용
            if i > 1:
                current_target_price = current_target_price * (1 - (drop_rate / 100))
            
            data.append({
                "회차": f"{i}차 매수",
                "비중": f"{weight}배",
                "매수 목표가": f"{symbol} {current_target_price:,.2f}",
                "매수 금액": f"{symbol} {buy_amount:,.0f}",
                "조건": f"전회차 대비 -{drop_rate}%" if i > 1 else "시작가"
            })
        
        df = pd.DataFrame(data)
        st.table(df)
        
        # 요약 정보
        st.success(f"✅ **1차 진입 추천 금액:** {symbol} {int(base_unit):,}")
        st.caption(f"※ 위 표의 가격에 도달할 때마다 해당 금액만큼 추가 매수하여 평단가를 관리하세요.")

# ==========================================
# 탭 3: 세계 경제 뉴스 (기능 유지)
# ==========================================
with tab3:
    st.subheader("🌍 글로벌 경제 헤드라인")
    try:
        feed = feedparser.parse("https://news.google.com/rss/search?q=global+economy+market+when:24h&hl=en-US&gl=US&ceid=US:en")
        for entry in feed.entries[:10]:
            st.markdown(f"📍 [{entry.title}]({entry.link})")
            st.write("")
    except: st.write("뉴스를 불러올 수 없습니다.")

