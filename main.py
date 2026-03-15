import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
import feedparser
import matplotlib.pyplot as plt
import io

# 1. 앱 기본 설정
st.set_page_config(page_title="스윙 알리미 V13.0", page_icon="🚨", layout="wide")

if "my_tickers_us" not in st.session_state:
    st.session_state["my_tickers_us"] = []
if "my_tickers_kr" not in st.session_state:
    st.session_state["my_tickers_kr"] = []

st.title("🚨 실시간 글로벌 스캐너 & 전략 차트 가이드")

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

# --- [핵심 함수] 차트 및 분할 매수 라인 시각화 ---
def plot_strategy_chart(ticker, levels, symbol):
    try:
        # 최근 3개월 데이터 수집
        data = yf.download(ticker, period="3mo", interval="1d")
        if data.empty: return None
        
        fig, ax = plt.subplots(figsize=(12, 6))
        ax.plot(data.index, data['Close'], label='Price', color='black', alpha=0.6)
        
        colors = ['#2ecc71', '#f1c40f', '#e67e22', '#e74c3c', '#c0392b']
        for i, (name, price) in enumerate(levels.items()):
            ax.axhline(y=price, color=colors[i], linestyle='--', alpha=0.8, label=f"{name}: {symbol}{price:,.2f}")
            ax.text(data.index[0], price, f" {name}", color=colors[i], va='bottom', fontweight='bold')

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
# 탭 1 & 2: 종목 스캐너 (기존 V12.4 로직 유지)
# ==========================================
# (중략 - 기존 스캐너 코드는 V12.4와 동일하게 유지됩니다)
with tab1:
    st.subheader("🇺🇸 미국 시장 분석")
    col_u1, col_u2 = st.columns([3, 1])
    with col_u1: new_us = st.text_input("미국 티커", key="us_in").upper()
    if col_u2.button("추가", key="u_add") and new_us:
        if new_us not in st.session_state["my_tickers_us"]: st.session_state["my_tickers_us"].append(new_us)
    sel_us = st.multiselect("목록", options=st.session_state["my_tickers_us"], default=st.session_state["my_tickers_us"])
    if st.button("🚀 스캔", key="u_go"):
        for t in sel_us:
            s = yf.Ticker(t); h = s.history(period="5d")
            if not h.empty:
                st.info(f"**[{t}]** ${h['Close'].iloc[-1]:.2f}")
                with st.expander("뉴스/홈페이지"):
                    for n in get_stock_news(t, "US"): st.markdown(f"- [{n['title']}]({n['link']}) `[{n['date']}]`")
                    if s.info.get('website'): st.markdown(f"🔗 [홈페이지]({s.info['website']})")

with tab2:
    st.subheader("🇰🇷 한국 시장 분석")
    col_k1, col_k2 = st.columns([3, 1])
    with col_k1: new_kr = st.text_input("한국 코드", key="kr_in")
    if col_k2.button("추가", key="k_add") and new_kr:
        if new_kr not in st.session_state["my_tickers_kr"]: st.session_state["my_tickers_kr"].append(new_kr)
    sel_kr = st.multiselect("목록", options=st.session_state["my_tickers_kr"], default=st.session_state["my_tickers_kr"])
    if st.button("🚀 스캔", key="k_go"):
        for t in sel_kr:
            for sfx in [".KS", ".KQ"]:
                s = yf.Ticker(t+sfx); h = s.history(period="5d")
                if not h.empty:
                    name = s.info.get('shortName', t)
                    st.success(f"**[{name} ({t}{sfx})]** {int(h['Close'].iloc[-1]):,}원")
                    break

# ==========================================
# 탭 3: 전략 분할 매수 (차트 시각화 추가)
# ==========================================
with tab3:
    st.subheader("💰 현재 차트 기반 진입 지점 시각화")
    
    # 설정 섹션
    c_set1, c_set2 = st.columns([1, 2])
    with c_set1:
        calc_ticker = st.text_input("분석할 티커 입력 (예: TSLA, 005930.KS)", value="TSLA").upper()
        currency = st.radio("통화", ["USD ($)", "KRW (원)"])
        symbol = "$" if currency == "USD ($)" else "원"
        total_budget = st.number_input(f"총 예산 ({symbol})", value=1000.0 if symbol=="$" else 3000000.0)
    
    with c_set2:
        st.markdown("#### 📉 회차별 하락 목표 (%)")
        r_cols = st.columns(4)
        r2 = r_cols[0].number_input("2차 하락", value=5.0)
        r3 = r_cols[1].number_input("3차 하락", value=10.0)
        r4 = r_cols[2].number_input("4차 하락", value=15.0)
        r5 = r_cols[3].number_input("5차 하락", value=20.0)

    if st.button("📊 전략 차트 생성 및 가격 계산", use_container_width=True):
        try:
            stock = yf.Ticker(calc_ticker)
            current_price = stock.history(period="1d")['Close'].iloc[-1]
            
            # 가격 계산
            base_unit = total_budget / 31
            rates = [0, r2, r3, r4, r5]
            levels = {}
            data_rows = []
            
            for i in range(1, 6):
                weight = 2**(i-1)
                target_p = current_price * (1 - (rates[i-1] / 100))
                levels[f"{i}차 매수"] = target_p
                data_rows.append({
                    "회차": f"{i}차", "비중": f"{weight}배",
                    "목표가": f"{symbol}{target_p:,.2f}" if symbol=="$" else f"{int(target_p):,}원",
                    "매수금액": f"{symbol}{base_unit * weight:,.0f}",
                    "하락률": f"-{rates[i-1]}%"
                })

            # 1. 차트 표시
            chart_img = plot_strategy_chart(calc_ticker, levels, symbol)
            if chart_img:
                st.image(chart_img, caption=f"{calc_ticker} 전략 매수 지점 시각화 (최근 3개월 차트 기준)")
            
            # 2. 테이블 표시
            st.table(pd.DataFrame(data_rows))
            
        except Exception as e:
            st.error(f"데이터를 불러올 수 없습니다: {e}")

# ==========================================
# 탭 4: 세계 경제 뉴스 (기존 유지)
# ==========================================
with tab4:
    if st.button("🔄 뉴스 새로고침"): st.rerun()
    feed = feedparser.parse("https://news.google.com/rss/search?q=global+economy+market+when:24h&hl=en-US&gl=US&ceid=US:en")
    for entry in feed.entries[:10]:
        st.markdown(f"📍 [{entry.title}]({entry.link})")
