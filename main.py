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
            sec_url = f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={ticker}&output=atom"
            sec_feed = feedparser.parse(sec_url)
            
            for entry in sec_feed.entries:
                # SEC 날짜 형식 처리 (예: 2024-03-15T12:00:00-04:00)
                updated_str = entry.updated if 'updated' in entry else ""
                if updated_str:
                    # 간단한 날짜 파싱 (ISO 형식 대응)
                    dt_str = updated_str.split('T')[0]
                    dt_obj = datetime.strptime(dt_str, '%Y-%m-%d')
                    
                    if dt_obj >= cutoff_date: # 최근 3개월 이내일 경우에만 추가 
                        filing_list.append({
                            "title": entry.title,
                            "link": entry.link,
                            "time": updated_str.replace('T', ' ').split('.')[0]
                        })
        except: pass
        
        return news_list, filing_list

    if st.button("🚀 종합 스캔 시작", use_container_width=True):
        if not current_tickers: st.error("종목을 먼저 추가하세요.")
        else:
            for ticker in current_tickers:
                res = get_stock_info(ticker)
                if not res: continue
                
                # 결과 헤더
                if res['is_spike'] and (res['cond_price'] and res['cond_mcap'] and res['cond_trend']):
                    st.success(f"### 🌟 [{res['ticker']}] 완벽 타점! (거래량 {res['ratio']}배)")
                elif res['is_spike']:
                    st.warning(f"### 🔥 [{res['ticker']}] 거래량 급등 ({res['ratio']}배)")
                else: st.info(f"### 💤 [{res['ticker']}] 관망 (${res['price']})")
                
                n_data, f_data = fetch_filtered_data(ticker)
                
                col1, col2 = st.columns(2)
                with col1:
                    with st.expander(f"📰 뉴스 ({len(n_data)})", expanded=True):
                        for n in n_data:
                            st.caption(f"📅 {n['time']}")
                            st.markdown(f"[{n['title']}]({n['link']})")
                            st.write("---")
                with col2:
                    with st.expander(f"📑 3개월 내 공시 ({len(f_data)})", expanded=True):
                        if f_data:
                            for f in f_data:
                                st.caption(f"🕒 {f['time']}")
                                st.markdown(f"**{f['title']}**")
                                st.markdown(f"[문서 보기]({f['link']})")
                                st.write("---")
                        else: st.write("최근 3개월 내 공시가 없습니다.")

                if res['website'] != '정보 없음':
                    st.markdown(f"🔗 [공식 홈페이지 방문하기]({res['website']})")
                st.write("---")

    st.write("### 🌍 글로벌 마켓 주요 소식 (24H)")
    w_feed = feedparser.parse("https://news.google.com/rss/search?q=global+stock+market+news+when:24h&hl=en-US&gl=US&ceid=US:en")
    for e in w_feed.entries[:5]: 
        st.markdown(f"- [{e.title}]({e.link})")

with tab2:
    st.subheader("💰 5분할 매수 계산기")
    total = st.number_input("💵 목표 금액", value=310000)
    if total > 0:
        u = total / 31
        st.success(f"🎯 1차 진입 금액: **{int(u):,}** 원")
        st.write(f"1차:{int(u):,} / 2차:{int(u*2):,} / 3차:{int(u*4):,} / 4차:{int(u*8):,} / 5차:{int(u*16):,}")
