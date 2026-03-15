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
                time_str = datetime.fromtimestamp(pub_time).strftime('%Y-%m-%d %H:%M') if pub_time else "날짜미상"
                link = item.get('link', '')

                # 제목에 'Form', 'SEC', '8-K', '10-Q' 등이 포함되면 공시로 분류
                if any(x in title.upper() for x in ['FORM', 'SEC', '8-K', '10-Q', '10-K', 'FILING']):
                    filing_items.append({"title": title, "link": link, "time": time_str})
                else:
                    news_items.append({"title": title, "link": link, "time": time_str})
        except: pass

        # 구글 뉴스 백업 (최근 3개월)
        try:
            rss_url = f"https://news.google.com/rss/search?q={ticker}+stock+when:90d&hl=en-US&gl=US&ceid=US:en"
            feed = feedparser.parse(rss_url)
            for entry in feed.entries[:10]:
                if entry.title not in seen_titles:
                    seen_titles.add(entry.title)
                    news_items.append({"title": entry.title, "link": entry.link, "time": "최근 3개월 (Google)"})
        except: pass
            
        return news_items[:10], filing_items[:10]

    if st.button("🚀 종합 스캔 시작", use_container_width=True):
        if not current_tickers: st.error("종목을 추가해 주세요.")
        else:
            with st.spinner('거래량, 뉴스, 공시 데이터 정밀 분석 중...'):
                for ticker in current_tickers:
                    res = check_stock_conditions(ticker)
                    if res["status"] == "error": continue
                    
                    # 결과 헤더
                    if res['is_spike'] and (res['cond_price'] and res['cond_mcap'] and res['cond_trend']):
                        st.success(f"### 🌟 [{res['ticker']}] 완벽 타점! (거래량 {res['ratio']}배)")
                    elif res['is_spike']:
                        st.warning(f"### 🔥 [{res['ticker']}] 거래량 급등 ({res['ratio']}배)")
                    else:
                        st.info(f"### 💤 [{res['ticker']}] 관망 (${res['current_price']})")
                    
                    # 1. 뉴스 & 공시 분리 표시
                    news_data, filing_data = get_separated_data(ticker)
                    
                    col_n, col_f = st.columns(2)
                    with col_n:
                        with st.expander(f"📰 뉴스 ({len(news_data)})", expanded=True):
                            if news_data:
                                for n in news_data:
                                    st.markdown(f"**[{n['time']}]**\n[{n['title']}]({n['link']})")
                                    st.write("---")
                            else: st.write("최근 뉴스가 없습니다.")
                            
                    with col_f:
                        with st.expander(f"📑 공시/SEC ({len(filing_data)})", expanded=True):
                            if filing_data:
                                for f in filing_data:
                                    st.markdown(f"**[{f['time']}]**\n[{f['title']}]({f['link']})")
                                    st.write("---")
                            else: st.write("최근 공시 데이터가 없습니다.")

                    # 2. 홈페이지 및 상세 조건
                    with st.expander(f"🔍 [{ticker}] 상세 정보 및 조건 확인"):
                        st.write(f"- 주가($0.5~5): {'🟢' if res['cond_price'] else '🔴'}")
                        st.write(f"- 시총(소형주): {'🟢' if res['cond_mcap'] else '🔴'}")
                        st.write(f"- 이평선(추세): {'🟢' if res['cond_trend'] else '🔴'}")
                        if res['website'] != '정보 없음':
                            st.markdown(f"🔗 [공식 홈페이지 방문하기]({res['website']})")
                    
                    st.write("---")

# 탭 2: 계산기 (이전과 동일)
with tab2:
    st.subheader("💰 5분할 물타기 계산기")
    total_budget = st.number_input("💵 최종 목표 금액", value=310000, step=10000)
    if total_budget > 0:
        u = total_budget / 31
        st.success(f"### 🎯 1차 진입 금액: **{int(u):,}** 원")
        st.write("1차:{:,} / 2차:{:,} / 3차:{:,} / 4차:{:,} / 5차:{:,}".format(int(u), int(u*2), int(u*4), int(u*8), int(u*16)))
