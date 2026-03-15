import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
import feedparser
import requests

# 1. 앱 기본 설정
st.set_page_config(page_title="스윙 알리미 V8.2", page_icon="🚨", layout="wide")

if "my_tickers" not in st.session_state:
    st.session_state["my_tickers"] = []

st.title("🚨 실시간 스윙 스캐너 & 글로벌 뉴스 센터")

# 탭 구성 (경제 뉴스 탭 추가)
tab1, tab2, tab3 = st.tabs(["🔍 종목 스캐너", "💰 5분할 계산기", "🌍 세계 경제 뉴스"])

# --- [엔진] 3개월 종목 뉴스 수집 ---
def get_company_news_3mo(ticker):
    news_list = []
    seen_links = set()
    try:
        # 구글 뉴스 RSS (3개월 범위: when:90d)
        q = f"{ticker}+stock+when:90d"
        url = f"https://news.google.com/rss/search?q={q}&hl=en-US&gl=US&ceid=US:en"
        feed = feedparser.parse(url)
        for entry in feed.entries[:8]:
            if entry.link not in seen_links:
                seen_links.add(entry.link)
                news_list.append({"title": entry.title, "link": entry.link, "time": "최근 3개월", "source": "Google"})
    except: pass
    return news_list

# --- [엔진] 세계 경제 주요 뉴스 수집 ---
def get_global_economy_news():
    global_news = []
    try:
        url = "https://news.google.com/rss/search?q=global+economy+market+breaking+when:24h&hl=en-US&gl=US&ceid=US:en"
        feed = feedparser.parse(url)
        for entry in feed.entries[:10]:
            global_news.append({"title": entry.title, "link": entry.link, "time": entry.published if 'published' in entry else ""})
    except: pass
    return global_news

# ==========================================
# 탭 1: 종목 스캐너 (복구된 3개월 뉴스 포함)
# ==========================================
with tab1:
    st.subheader("📝 종목 관리 및 분석")
    col_input, col_btn = st.columns([3, 1])
    with col_input:
        new_tk = st.text_input("티커 입력", placeholder="예: ALVO, AAPL, XPON").upper()
    with col_btn:
        st.write(""); st.write("")
        if st.button("추가"):
            if new_tk and new_tk not in st.session_state["my_tickers"]:
                st.session_state["my_tickers"].append(new_tk)
                
    selected_tickers = st.multiselect("스캔 목록", options=st.session_state["my_tickers"], default=st.session_state["my_tickers"])
    st.session_state["my_tickers"] = selected_tickers

    if st.button("🚀 종합 스캔 시작", use_container_width=True):
        if not selected_tickers:
            st.warning("종목을 먼저 추가해 주세요.")
        else:
            for ticker in selected_tickers:
                try:
                    stock = yf.Ticker(ticker)
                    hist = stock.history(period="6mo")
                    info = stock.info
                    
                    if hist.empty: continue
                    
                    curr_price = hist['Close'].iloc[-1]
                    curr_vol = hist['Volume'].iloc[-1]
                    avg_vol = hist['Volume'].iloc[-21:-1].mean()
                    
                    # 분석 결과 알림
                    vol_ratio = round(curr_vol / avg_vol, 1)
                    if (curr_vol >= avg_vol * 3) and (curr_vol >= 1000000):
                        st.success(f"### 🌟 [{ticker}] 거래량 폭발! ({vol_ratio}배)")
                    else:
                        st.info(f"### 💤 [{ticker}] 분석 중 (현재가 ${curr_price:.2f})")
                    
                    # 상세 익스팬더
                    with st.expander(f"📊 {ticker} 상세 데이터 및 뉴스/공시"):
                        col_a, col_b = st.columns(2)
                        with col_a:
                            st.write(f"**현재가:** ${curr_price:.2f}")
                            st.write(f"**거래량:** {curr_vol/1000000:.1f}M")
                            # 공식 링크들
                            st.write("---")
                            st.markdown(f"🏛️ [SEC 공식 공시 원문](https://www.sec.gov/cgi-bin/browse-edgar?CIK={ticker}&action=getcompany)")
                            st.markdown(f"📢 [IR 게시판 찾기](https://www.google.com/search?q={ticker}+Investor+Relations)")
                        
                        with col_b:
                            st.markdown("**📰 최근 3개월 종목 뉴스**")
                            c_news = get_company_news_3mo(ticker)
                            if c_news:
                                for n in c_news:
                                    st.markdown(f"- [{n['title']}]({n['link']})")
                            else:
                                st.write("관련 뉴스가 없습니다.")
                except:
                    st.error(f"{ticker} 분석 실패")
                st.write("---")

# ==========================================
# 탭 2: 5분할 계산기
# ==========================================
with tab2:
    st.subheader("💰 5분할 물타기 계산기")
    budget = st.number_input("💵 총 투입 예정 금액", value=310000, step=10000)
    if budget > 0:
        unit = budget / 31
        st.success(f"### 🎯 1차 진입 금액: **{int(unit):,}** 원")
        st.write("---")
        c1, c2, c3 = st.columns(3)
        c1.metric("1차 (1배)", f"{int(unit):,}원")
        c2.metric("2차 (2배)", f"{int(unit*2):,}원")
        c3.metric("3차 (4배)", f"{int(unit*4):,}원")
        c4, c5 = st.columns(2)
        c4.metric("4차 (8배)", f"{int(unit*8):,}원", delta="주의", delta_color="inverse")
        c5.metric("5차 (16배)", f"{int(unit*16):,}원", delta="최후방어", delta_color="inverse")

# ==========================================
# 탭 3: 세계 경제 뉴스 (신규 추가)
# ==========================================
with tab3:
    st.subheader("🌍 글로벌 경제 실시간 헤드라인")
    st.write("전 세계 금융 시장의 주요 소식을 실시간으로 확인하세요.")
    if st.button("🔄 뉴스 새로고침"):
        st.rerun()
    
    g_news = get_global_economy_news()
    if g_news:
        for gn in g_news:
            st.markdown(f"📍 [{gn['title']}]({gn['link']})")
            st.caption(f"발행시간: {gn['time']}")
            st.write("")
    else:
        st.write("경제 뉴스를 불러오는 중입니다...")
