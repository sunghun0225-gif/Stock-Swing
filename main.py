import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import datetime
import feedparser
import matplotlib.pyplot as plt
import io

# 1. 앱 기본 설정
st.set_page_config(page_title="스윙 알리미 V13.1", page_icon="🚨", layout="wide")

# 세션 상태 초기화 (중복 방지용 키 설정)
if "my_tickers_us" not in st.session_state:
    st.session_state["my_tickers_us"] = []
if "my_tickers_kr" not in st.session_state:
    st.session_state["my_tickers_kr"] = []

st.title("🚨 실시간 글로벌 스캐너 & 전략 매매 가이드")

# 탭 구성
tab1, tab2, tab3, tab4 = st.tabs(["🇺🇸 미국 종목", "🇰🇷 한국 종목", "💰 전략 분할 매수", "🌍 세계 경제 뉴스"])

# --- [함수] 뉴스 수집 ---
def get_stock_news(ticker, market="US"):
    news_list = []
    try:
        query = f"{ticker}+stock" if market == "US" else f"{ticker}+주식"
        hl, gl, ceid = ('en-US', 'US', 'US:en') if market == 'US' else ('ko-KR', 'KR', 'KR:ko')
        url = f"https://news.google.com/rss/search?q={query}+when:90d&hl={hl}&gl={gl}&ceid={ceid}"
        feed = feedparser.parse(url)
        for entry in feed.entries[:8]:
            raw_date = entry.published_parsed if 'published_parsed' in entry else None
            date_str = datetime(*raw_date[:6]).strftime('%m-%d %H:%M') if raw_date else "날짜미상"
            news_list.append({"title": entry.title, "link": entry.link, "date": date_str})
    except: pass
    return news_list

# --- [함수] 차트 및 분할 매수 라인 시각화 ---
def plot_strategy_chart(ticker, levels, symbol):
    try:
        data = yf.download(ticker, period="3mo", interval="1d")
        if data.empty: return None
        fig, ax = plt.subplots(figsize=(12, 6))
        ax.plot(data.index, data['Close'], label='Price', color='black', alpha=0.6)
        colors = ['#2ecc71', '#f1c40f', '#e67e22', '#e74c3c', '#c0392b']
        for i, (name, price) in enumerate(levels.items()):
            ax.axhline(y=price, color=colors[i], linestyle='--', alpha=0.8, label=f"{name}: {symbol}{price:,.2f}")
        ax.set_title(f"{ticker} Entry Strategy Chart", fontsize=15, pad=15)
        ax.legend(loc='upper right')
        ax.grid(axis='y', alpha=0.3)
        buf = io.BytesIO()
        plt.savefig(buf, format='png', bbox_inches='tight')
        plt.close(fig)
        buf.seek(0)
        return buf
    except: return None

# ==========================================
# 탭 1: 미국 종목 스캐너
# ==========================================
with tab1:
    st.subheader("🇺🇸 미국 시장 종목 분석")
    col_u1, col_u2 = st.columns([3, 1])
    with col_u1:
        new_us = st.text_input("미국 티커 입력", placeholder="예: TSLA", key="us_input_field").upper()
    if col_u2.button("미국 종목 추가", key="us_add_button") and new_us:
        if new_us not in st.session_state["my_tickers_us"]:
            st.session_state["my_tickers_us"].append(new_us)
    
    sel_us = st.multiselect("미국 스캔 목록", options=st.session_state["my_tickers_us"], default=st.session_state["my_tickers_us"], key="us_multi_select")
    st.session_state["my_tickers_us"] = sel_us

    if st.button("🚀 미국 종목 스캔 시작", key="us_scan_trigger", use_container_width=True):
        for t in sel_us:
            s = yf.Ticker(t); h = s.history(period="5d")
            if not h.empty:
                st.info(f"**[{t}]** 현재가: ${h['Close'].iloc[-1]:.2f}")
                with st.expander(f"📊 {t} 상세 정보", key=f"exp_us_{t}"):
                    st.markdown(f"🏛️ [SEC 공시](https://www.sec.gov/cgi-bin/browse-edgar?CIK={t}&action=getcompany)")
                    for n in get_stock_news(t, "US"): 
                        st.markdown(f"- [{n['title']}]({n['link']}) `[{n['date']}]` ")
                    if s.info.get('website'): st.markdown(f"🔗 [공식 홈페이지]({s.info['website']})")
            st.write("---")

# ==========================================
# 탭 2: 한국 종목 스캐너
# ==========================================
with tab2:
    st.subheader("🇰🇷 한국 시장 종목 분석")
    col_k1, col_k2 = st.columns([3, 1])
    with col_k1:
        new_kr = st.text_input("한국 종목 코드 입력", placeholder="예: 005930", key="kr_input_field")
    if col_k2.button("한국 종목 추가", key="kr_add_button") and new_kr:
        if new_kr.isdigit() and new_kr not in st.session_state["my_tickers_kr"]:
            st.session_state["my_tickers_kr"].append(new_kr)
    
    sel_kr = st.multiselect("한국 스캔 목록", options=st.session_state["my_tickers_kr"], default=st.session_state["my_tickers_kr"], key="kr_multi_select")
    st.session_state["my_tickers_kr"] = sel_kr
    
    if st.button("🚀 한국 종목 스캔 시작", key="kr_scan_trigger", use_container_width=True):
        for t in sel_kr:
            found = False
            for suffix in [".KS", ".KQ"]:
                full_ticker = t + suffix
                s = yf.Ticker(full_ticker); h = s.history(period="5d")
                if not h.empty:
                    name = s.info.get('shortName') or s.info.get('longName') or t
                    st.success(f"**[{name} ({full_ticker})]** 현재가: {int(h['Close'].iloc[-1]):,} 원")
                    with st.expander(f"📊 {name} 상세 정보", key=f"exp_kr_{t}"):
                        st.markdown(f"🏛️ [네이버 증권 공시](https://finance.naver.com/item/news.naver?code={t})")
                        for n in get_stock_news(full_ticker, "KR"): 
                            st.markdown(f"- [{n['title']}]({n['link']}) `[{n['date']}]` ")
                    found = True; break
            st.write("---")

# ==========================================
# 탭 3: 전략 분할 매수
# ==========================================
with tab3:
    st.subheader("💰 차트 기반 전략 시뮬레이션")
    c_set1, c_set2 = st.columns([1, 2])
    with c_set1:
        calc_ticker = st.text_input("분석할 티커 (예: TSLA, 005930.KS)", value="TSLA", key="strat_ticker_input").upper()
        currency = st.radio("통화 선택", ["USD ($)", "KRW (원)"], key="strat_currency_radio")
        symbol = "$" if currency == "USD ($)" else "원"
        total_budget = st.number_input(f"총 예산 ({symbol})", value=1000.0 if symbol=="$" else 3000000.0, key="strat_budget_input")
    
    with c_set2:
        st.markdown("#### 📉 회차별 하락 목표 (%)")
        r_cols = st.columns(4)
        r2 = r_cols[0].number_input("2차 하락", value=5.0, key="rate_r2")
        r3 = r_cols[1].number_input("3차 하락", value=10.0, key="rate_r3")
        r4 = r_cols[2].number_input("4차 하락", value=15.0, key="rate_r4")
        r5 = r_cols[3].number_input("5차 하락", value=20.0, key="rate_r5")

    if st.button("📊 전략 차트 및 시나리오 생성", key="strat_generate_btn", use_container_width=True):
        try:
            stock = yf.Ticker(calc_ticker)
            current_price = stock.history(period="1d")['Close'].iloc[-1]
            base_unit = total_budget / 31
            rates = [0, r2, r3, r4, r5]
            levels = {}
            data_rows = []
            for i in range(1, 6):
                weight = 2**(i-1)
                target_p = current_price * (1 - (rates[i-1] / 100))
                levels[f"{i}차 매수"] = target_p
                data_rows.append({"회차": f"{i}차", "비중": f"{weight}배", "목표가": f"{symbol}{target_p:,.2f}" if symbol=="$" else f"{int(target_p):,}원", "매수금액": f"{symbol}{base_unit * weight:,.0f}", "하락률": f"-{rates[i-1]}%"})
            
            img = plot_strategy_chart(calc_ticker, levels, symbol)
            if img: st.image(img, caption="전략 매수 지점 시각화")
            st.table(pd.DataFrame(data_rows))
        except: st.error("티커를 확인해 주세요. (한국 종목은 .KS 혹은 .KQ 필수)")

# ==========================================
# 탭 4: 세계 경제 뉴스
# ==========================================
with tab4:
    if st.button("🔄 실시간 뉴스 새로고침", key="news_refresh_btn", use_container_width=True): st.rerun()
    feed = feedparser.parse("https://news.google.com/rss/search?q=global+economy+market+when:24h&hl=en-US&gl=US&ceid=US:en")
    for entry in feed.entries[:10]:
        st.markdown(f"📍 [{entry.title}]({entry.link})  `[{entry.published[:16] if 'published' in entry else ''}]` ")
