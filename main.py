import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
import feedparser

# 1. 앱 설정
st.set_page_config(page_title="스윙 알리미 V7.8", page_icon="🚨", layout="centered")

if "my_tickers" not in st.session_state:
    st.session_state["my_tickers"] = []

st.title("🚨 스윙 매매 알리미 V7.8")

tab1, tab2 = st.tabs(["🔍 종목 스캐너", "💰 5분할 매수 계산기"])

# ==========================================
# 탭 1: 종목 스캐너 (분석 + 뉴스/공시 분리)
# ==========================================
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

    def get_stock_data(ticker):
        try:
            stock = yf.Ticker(ticker)
            hist = stock.history(period="6mo")
            info = stock.info
            if hist.empty: return None
            
            cur_price = hist['Close'].iloc[-1]
            avg_vol = hist['Volume'].iloc[-21:-1].mean()
            cur_vol = hist['Volume'].iloc[-1]
            ma20 = hist['Close'].iloc[-20:].mean()
            ma5 = hist['Close'].iloc[-5:].mean()
            mcap = info.get('marketCap', 0)
            
            return {
                "ticker": ticker, "price": round(cur_price, 2), "ratio": round(cur_vol / avg_vol, 2),
                "is_spike": cur_vol >= (avg_vol * 3) and cur_vol >= 1000000,
                "cond_price": 0.5 <= cur_price <= 5.0,
                "cond_mcap": mcap <= 300000000 if mcap > 0 else False,
                "cond_trend": (cur_price >= ma20) or (ma5 >= ma20),
                "website": info.get('website', '정보 없음'),
                "stock_obj": stock
            }
        except: return None

    def fetch_news_and_filings(ticker, stock_obj):
        news_list = []; filing_list = []; seen = set()
        
        # [A] 야후 파이낸스 데이터 (1차)
        try:
            raw = stock_obj.news
            for item in raw:
                title = item.get('title', '').strip()
                if not title or title in seen: continue
                seen.add(title)
                
                pub = item.get('providerPublishTime')
                dt = datetime.fromtimestamp(pub) if pub else None
                if dt and (datetime.now() - dt <= timedelta(days=90)):
                    time_s = dt.strftime('%Y-%m-%d %H:%M')
                    entry = {"title": title, "link": item.get('link', ''), "time": time_s}
                    
                    if any(x in title.upper() for x in ['FORM', 'SEC', '8-K', '10-Q', '10-K', 'FILING']):
                        filing_list.append(entry)
                    else:
                        news_list.append(entry)
        except: pass

        # [B] 구글 뉴스 RSS 백업 (2차 - 최근 3개월)
        try:
            feed = feedparser.parse(f"https://news.google.com/rss/search?q={ticker}+stock+when:90d&hl=en-US&gl=US&ceid=US:en")
            for entry in feed.entries[:8]:
                if entry.title not in seen:
                    seen.add(entry.title)
                    news_list.append({"title": entry.title, "link": entry.link, "time": "최근 3개월 (Google)"})
        except: pass
        
        return news_list[:10], filing_list[:10]

    if st.button("🚀 종합 스캔 시작", use_container_width=True):
        if not current_tickers: st.error("종목을 먼저 추가하세요.")
        else:
            for ticker in current_tickers:
                res = get_stock_data(ticker)
                if not res: continue
                
                # 결과 헤더
                if res['is_spike'] and (res['cond_price'] and res['cond_mcap'] and res['cond_trend']):
                    st.success(f"### 🌟 [{res['ticker']}] 완벽 타점! (거래량 {res['ratio']}배)")
                elif res['is_spike']:
                    st.warning(f"### 🔥 [{res['ticker']}] 거래량 급등 ({res['ratio']}배)")
                else:
                    st.info(f"### 💤 [{res['ticker']}] 관망 (${res['price']})")
                
                # 뉴스 & 공시
                n_data, f_data = fetch_news_and_filings(ticker, res['stock_obj'])
                c1, c2 = st.columns(2)
                with c1:
                    with st.expander(f"📰 뉴스 ({len(n_data)})", expanded=True):
                        for n in n_data: st.markdown(f"**[{n.get('time', '')}]**\n[{n['title']}]({n['link']})"); st.write("---")
                with c2:
                    with st.expander(f"📑 공시/SEC ({len(f_data)})", expanded=True):
                        for f in f_data: st.markdown(f"**[{f.get('time', '')}]**\n[{f['title']}]({f['link']})"); st.write("---")

                # 기업 홈페이지
                if res['website'] != '정보 없음':
                    st.markdown(f"🔗 [공식 홈페이지 방문하기]({res['website']})")
                st.write("---")

    # 세계 경제 뉴스
    st.write("### 🌍 세계 경제 주요 뉴스 (24H)")
    try:
        w_feed = feedparser.parse("https://news.google.com/rss/search?q=global+economy+market+news+when:24h&hl=en-US&gl=US&ceid=US:en")
        for e in w_feed.entries[:5]: st.markdown(f"- [{e.title}]({e.link})")
    except: st.write("뉴스 로딩 실패")

# 탭 2: 계산기 (생략 - 이전 버전과 동일)
with tab2:
    st.subheader("💰 5분할 매수 계산기")
    total = st.number_input("💵 목표 금액", value=310000)
    if total > 0:
        u = total / 31
        st.success(f"🎯 1차 진입 금액: **{int(u):,}** 원")
        st.write(f"1차:{int(u):,} / 2차:{int(u*2):,} / 3차:{int(u*4):,} / 4차:{int(u*8):,} / 5차:{int(u*16):,}")
