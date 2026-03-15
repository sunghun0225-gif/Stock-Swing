import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
import feedparser
import time

st.set_page_config(page_title="스윙 알리미 V8.0", page_icon="🚨", layout="centered")

if "my_tickers" not in st.session_state:
    st.session_state["my_tickers"] = []

st.title("🚨 스윙 매매 알리미 V8.0")

tab1, tab2 = st.tabs(["🔍 종목 스캐너", "💰 5분할 매수 계산기"])

with tab1:
    st.subheader("📝 관심 종목 관리")
    col1, col2 = st.columns([3, 1])
    with col1:
        new_ticker = st.text_input("➕ 추가할 티커", placeholder="예: TSLA, AAPL")
    with col2:
        st.write(""); st.write("")
        if st.button("종목 추가"):
            if new_ticker:
                t = new_ticker.strip().upper()
                if t not in st.session_state["my_tickers"]:
                    st.session_state["my_tickers"].append(t)
    
    current_tickers = st.multiselect("스캔 대상", options=st.session_state["my_tickers"], default=st.session_state["my_tickers"])
    st.session_state["my_tickers"] = current_tickers

    def get_stock_info(ticker):
        try:
            stock = yf.Ticker(ticker)
            hist = stock.history(period="6mo")
            info = stock.info
            if hist.empty: return None
            
            cp = hist['Close'].iloc[-1]
            av = hist['Volume'].iloc[-21:-1].mean()
            cv = hist['Volume'].iloc[-1]
            mcap = info.get('marketCap', 0)
            
            return {
                "ticker": ticker, "price": round(cp, 2), "ratio": round(cv / av, 2),
                "is_spike": cv >= (av * 3) and cv >= 1000000,
                "cond_price": 0.5 <= cp <= 5.0,
                "cond_mcap": mcap <= 300000000 if mcap > 0 else False,
                "cond_trend": (cp >= hist['Close'].iloc[-20:].mean()) or (hist['Close'].iloc[-5:].mean() >= hist['Close'].iloc[-20:].mean()),
                "website": info.get('website', '정보 없음'),
                "stock_obj": stock
            }
        except: return None

    def fetch_filtered_data(ticker):
        news_list = []
        filing_list = []
        cutoff_date = datetime.now() - timedelta(days=90) # 최근 90일 기준

        # 1. 뉴스 (최근 90일)
        try:
            news_feed = feedparser.parse(f"https://news.google.com/rss/search?q={ticker}+stock+when:90d&hl=en-US&gl=US&ceid=US:en")
            for entry in news_feed.entries[:10]:
                news_list.append({
                    "title": entry.title,
                    "link": entry.link,
                    "time": entry.published if 'published' in entry else "최근 3개월"
                })
        except: pass

        # 2. SEC 공시 (최근 90일 필터링)
        try:
            sec_url = f"
