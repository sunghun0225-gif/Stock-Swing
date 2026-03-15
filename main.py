import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import datetime
import feedparser

# 1. 앱 설정
st.set_page_config(page_title="스윙 알리미 V8.1", page_icon="🚨", layout="centered")

if "my_tickers" not in st.session_state:
    st.session_state["my_tickers"] = []

st.title("🚨 실시간 스윙 스캐너 & 공시 허브")

tab1, tab2 = st.tabs(["🔍 종목 스캐너", "💰 5분할 계산기"])

# --- [엔진] 뉴스 수집 (보조 용도) ---
def get_recent_news(ticker):
    news_data = []
    seen_links = set()
    try:
        # 야후 파이낸스 뉴스
        stock = yf.Ticker(ticker)
        for item in stock.news:
            link = item.get('link', '')
            if link not in seen_links:
                seen_links.add(link)
                pub_time = item.get('providerPublishTime')
                time_str = datetime.fromtimestamp(pub_time).strftime('%m-%d') if pub_time else ""
                news_data.append({"title": item.get('title', ''), "link": link, "time": time_str})
    except: pass
    return news_data[:7]

# ==========================================
# 탭 1: 스캐너 기능 (공시 링크 강화)
# ==========================================
with tab1:
    st.subheader("📝 종목 관리")
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

    if st.button("🚀 종합 스캔 및 공시 추적", use_container_width=True):
        if not selected_tickers:
            st.warning("종목을 먼저 추가해 주세요.")
        else:
            for ticker in selected_tickers:
                try:
                    stock = yf.Ticker(ticker)
                    hist = stock.history(period="6mo")
                    info = stock.info
                    
                    if hist.empty:
                        st.error(f"[{ticker}] 데이터를 불러올 수 없습니다.")
                        continue
                    
                    # 지표 계산
                    curr_price = hist['Close'].iloc[-1]
                    curr_vol = hist['Volume'].iloc[-1]
                    avg_vol = hist['Volume'].iloc[-21:-1].mean()
                    mkt_cap = info.get('marketCap', 0)
                    company_name = info.get('longName', ticker)
                    
                    # 분석 결과 알림
                    vol_ratio = round(curr_vol / avg_vol, 1)
                    if (curr_vol >= avg_vol * 3) and (curr_vol >= 1000000):
                        st.success(f"### 🌟 [{ticker}] 거래량 {vol_ratio}배 폭발! (타점 포착)")
                    else:
                        st.info(f"### 💤 [{ticker}] 현재가 ${curr_price:.2f} (거래량 {vol_ratio}배)")
                    
                    # --- 핵심: 공시 및 기업 정보 허브 섹션 ---
                    with st.expander(f"📑 {ticker} 공식 공시 및 IR 게시판 바로가기", expanded=True):
                        st.markdown(f"#### 🔍 {company_name} 공식 자료 창구")
                        
                        # 1. SEC 공식 공시 (EDGAR) 링크
                        sec_url = f"https://www.sec.gov/cgi-bin/browse-edgar?CIK={ticker}&action=getcompany"
                        st.info(f"🏛️ **[SEC EDGAR 공식 공시 원문 전체보기]({sec_url})**")
                        
                        # 2. 회사 IR/공시 게시판 구글 검색 링크 (가장 정확하게 IR 페이지를 찾아줌)
                        ir_search_url = f"https://www.google.com/search?q={company_name.replace(' ', '+')}+Investor+Relations+disclosures"
                        st.warning(f"📢 **[회사 공식 IR/공시 게시판 찾기]({ir_search_url})**")
                        
                        # 3. 공식 홈페이지
                        if info.get('website'):
                            st.success(f"🌐 **[공식 홈페이지 방문하기]({info['website']})**")
                        
                        st.write("---")
                        
                        # 4. 보조용 뉴스 리스트
                        st.markdown("**📰 최근 시장 뉴스**")
                        news_items = get_recent_news(ticker)
                        if news_items:
                            for n in news_items:
                                st.markdown(f"- [{n['title']}]({n['link']}) `[{n['time']}]`")
                        else:
                            st.write("최근 기사가 없습니다.")

                except Exception as e:
                    st.error(f"{ticker} 분석 중 오류: {e}")
                st.write("---")

# ==========================================
# 탭 2: 5분할 매수 계산기
# ==========================================
with tab2:
    st.subheader("💰 5분할 물타기 계산기 (1:2 비율)")
    budget = st.number_input("💵 총 투입 예정 금액", value=310000, step=10000)
    if budget > 0:
        unit = budget / 31
        st.success(f"### 🎯 1차 진입 금액: **{int(unit):,}** 원")
        st.write("---")
        c1, c2, c3 = st.columns(3)
        c1.info(f"**1차 (1배)**\n\n{int(unit):,}원")
        c2.info(f"**2차 (2배)**\n\n{int(unit*2):,}원")
        c3.info(f"**3차 (4배)**\n\n{int(unit*4):,}원")
        c4, c5 = st.columns(2)
        c4.warning(f"**4차 (8배)**\n\n{int(unit*8):,}원")
        c5.error(f"**5차 (16배)**\n\n{int(unit*16):,}원")
