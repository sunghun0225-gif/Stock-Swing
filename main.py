import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
import feedparser

st.set_page_config(page_title="나만의 스윙 알리미", page_icon="🚨", layout="centered")

if "my_tickers" not in st.session_state:
    st.session_state["my_tickers"] = []

st.title("🚨 스윙 매매 알리미 V7.6")

tab1, tab2 = st.tabs(["🔍 종목 스캐너", "💰 5분할 매수 계산기"])

with tab1:
    st.subheader("📝 관심 종목 관리")
    col1, col2 = st.columns([3, 1])
    with col1:
        new_ticker = st.text_input("➕ 추가할 종목의 티커", placeholder="예: TSLA, AAPL")
    with col2:
        st.write(""); st.write("")
        if st.button("종목 추가"):
            if new_ticker:
                t = new_ticker.strip().upper()
                if t not in st.session_state["my_tickers"]:
                    st.session_state["my_tickers"].append(t)
    
    current_tickers = st.multiselect("스캔 대기 중인 종목", options=st.session_state["my_tickers"], default=st.session_state["my_tickers"])
    st.session_state["my_tickers"] = current_tickers

    def check_stock_conditions(ticker):
        try:
            stock = yf.Ticker(ticker)
            hist = stock.history(period="6mo")
            info = stock.info
            if hist.empty: return {"status": "error"}
            
            current_volume = hist['Volume'].iloc[-1]
            current_price = hist['Close'].iloc[-1]
            market_cap = info.get('marketCap', 0)
            ma20 = hist['Close'].iloc[-20:].mean()
            ma5 = hist['Close'].iloc[-5:].mean()
            avg_vol = hist['Volume'].iloc[-21:-1].mean()
            
            return {
                "status": "success", "ticker": ticker, "ratio": round(current_volume / avg_vol, 2),
                "is_spike": current_volume >= (avg_vol * 3) and current_volume >= 1000000,
                "current_price": round(current_price, 2),
                "cond_price": 0.5 <= current_price <= 5.0,
                "cond_mcap": market_cap <= 300000000 if market_cap > 0 else False,
                "cond_trend": (current_price >= ma20) or (ma5 >= ma20),
                "website": info.get('website', '정보 없음')
            }
        except: return {"status": "error"}

    def get_separated_data(ticker):
        news_items = []
        filing_items = []
        seen_titles = set()
        
        try:
            stock = yf.Ticker(ticker)
            yf_data = stock.news
            for item in yf_data:
                title = item.get('title', '').strip()
                if not title or title in seen_titles: continue
                seen_titles.add(title)
                
                pub_time = item.get('providerPublishTime')
                time_str = datetime.fromtimestamp(pub_time).strftime('%Y-%m-%d
