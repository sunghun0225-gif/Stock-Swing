import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
import feedparser
import re

st.set_page_config(page_title="스윙 알리미 V7.9", page_icon="🚨", layout="centered")

if "my_tickers" not in st.session_state:
    st.session_state["my_tickers"] = []

st.title("🚨 스윙 매매 알리미 V7.9")

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
                "website": info.get('website', '정보 없음')
            }
        except: return None

    # --- [핵심] 뉴스 및 SEC.gov 공시 수집 엔진 ---
    def fetch_data_v79(ticker):
        news_list = []
        filing_list = []
        seen = set()

        # 1. 뉴스 수집 (Google News RSS - 최근 3개월)
        try:
            news_feed = feedparser.parse(f"https://news.google.com/rss/search?q={ticker}+stock+when:90d&hl=en-US&gl=US&ceid=US:en")
            for entry in news_feed.entries[:10]:
                title = entry.title
                # 공시 키워드가 포함된 기사는 뉴스 섹션에서 제외
                if not any(x in title.upper() for x in ['SEC FILING', 'FORM 8-K', 'FORM 4', '10-Q']):
                    news_list.append({
                        "title": title,
                        "link": entry.link,
                        "time": entry.published if 'published' in entry else "최근 3개월"
                    })
        except: pass

        # 2. 공시 수집 (SEC.gov EDGAR 공식 실시간 RSS)
        try:
            # SEC의 특정 티커 공시 피드 주소
            sec_url = f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={ticker}&type=&dateb=&owner=include&start=0&count=10&output=atom"
            # SEC 서버 접근을 위해 User-Agent 설정 (필수)
            sec_feed = feedparser.parse(sec_url)
            
            for entry in sec_feed.entries:
                # 제목에서 Form 종류 추출 (예: 8-K, 4, 10-Q 등)
                title = entry.title
                pub_date = entry.updated if 'updated' in entry else "최근 공시"
                # 날짜 형식 정리 (T 및 시간대 제거)
                clean_date = pub_date.replace('T', ' ').split('.')[0] if 'T' in pub_date else pub_date
                
                filing_list.append({
                    "title": title,
                    "link": entry.link,
                    "time": clean_date
                })
        except: pass
        
        return news_list[:10], filing_list[:10]

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
                
                # 뉴스 & 공시 호출
                n_data, f_data = fetch_data_v79(ticker)
                
                col1, col2 = st.columns(2)
                with col1:
                    with st.expander(f"📰 최신 뉴스 ({len(n_data)})", expanded=True):
                        for n in n_data:
                            st.caption(f"📅 {n['time']}")
                            st.markdown(f"[{n['title']}]({n['link']})")
                            st.write("---")
                with col2:
                    with st.expander(f"📑 SEC.gov 공식 공시 ({len(f_data)})", expanded=True):
                        if f_data:
                            for f in f_data:
                                st.caption(f"🕒 {f['time']}")
                                st.markdown(f"**{f['title']}**")
                                st.markdown(f"[공식 문서 보기]({f['link']})")
                                st.write("---")
                        else: st.write("SEC에 등록된 최근 공시가 없습니다.")

                if res['website'] != '정보 없음':
                    st.markdown(f"🔗 [공식 홈페이지 방문하기]({res['website']})")
                st.write("---")

    # 세계 경제 뉴스
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
