import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import datetime
import feedparser
import matplotlib.pyplot as plt
import io

# 1. 앱 기본 설정
st.set_page_config(page_title="스윙 알리미 V12.1", page_icon="🚨", layout="wide")

if "my_tickers_us" not in st.session_state:
    st.session_state["my_tickers_us"] = []
if "my_tickers_kr" not in st.session_state:
    st.session_state["my_tickers_kr"] = []

st.title("🚨 실시간 글로벌 스캐너 & 정밀 매매 가이드")

# 탭 구성
tab1, tab2, tab3, tab4 = st.tabs(["🇺🇸 미국 종목", "🇰🇷 한국 종목", "💰 정밀 분할 매수", "🌍 세계 경제 뉴스"])

# --- [공통 함수] 뉴스 수집 ---
def get_stock_news(ticker, market="US"):
    news_list = []
    try:
        query = f"{ticker}+stock" if market == "US" else f"{ticker}+주식"
        url = f"https://news.google.com/rss/search?q={query}+when:90d&hl={'en-US' if market=='US' else 'ko-KR'}&gl={'US' if market=='US' else 'KR'}&ceid={'US:en' if market=='US' else 'KR:ko'}"
        feed = feedparser.parse(url)
        for entry in feed.entries[:8]:
            news_list.append({"title": entry.title, "link": entry.link})
    except: pass
    return news_list

# --- [공통 함수] 이미지 저장 로직 ---
def export_as_image(df, title):
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.axis('off')
    ax.set_title(title, fontsize=16, weight='bold', pad=20)
    table = ax.table(cellText=df.values, colLabels=df.columns, cellLoc='center', loc='center')
    table.auto_set_font_size(False)
    table.set_fontsize(11)
    table.scale(1.2, 2.5)
    buf = io.BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight', dpi=150)
    plt.close(fig) # 메모리 해제를 위해 추가
    buf.seek(0)
    return buf

# ==========================================
# 탭 1: 미국 종목 스캐너
# ==========================================
with tab1:
    st.subheader("🇺🇸 미국 시장 종목 분석")
    col_u1, col_u2 = st.columns([3, 1])
    with col_u1:
        new_us = st.text_input("미국 티커 입력", placeholder="예: TSLA, AAPL", key="us_in").upper()
    if col_u2.button("미국 종목 추가") and new_us:
        if new_us not in st.session_state["my_tickers_us"]:
            st.session_state["my_tickers_us"].append(new_us)
    
    sel_us = st.multiselect("미국 스캔 목록", options=st.session_state["my_tickers_us"], default=st.session_state["my_tickers_us"])
    if st.button("🚀 미국 종목 스캔 시작", key="start_us"):
        for t in sel_us:
            s = yf.Ticker(t)
            h = s.history(period="6mo")
            if not h.empty:
                st.info(f"**[{t}]** 현재가: ${h['Close'].iloc[-1]:.2f}")
                with st.expander("뉴스/공시 확인"):
                    st.markdown(f"🏛️ [SEC 공시](https://www.sec.gov/cgi-bin/browse-edgar?CIK={t}&action=getcompany)")
                    for n in get_stock_news(t, "US"): st.markdown(f"- [{n['title']}]({n['link']})")

# ==========================================
# 탭 2: 한국 종목 스캐너 (종목명 표시 보완)
# ==========================================
with tab2:
    st.subheader("🇰🇷 한국 시장 종목 분석")
    st.caption("숫자 코드를 입력하세요 (예: 005930).")
    
    col_k1, col_k2 = st.columns([3, 1])
    with col_k1:
        new_kr = st.text_input("한국 종목 코드 입력", placeholder="예: 005930", key="kr_in")
    if col_k2.button("한국 종목 추가") and new_kr:
        if new_kr.isdigit() and new_kr not in st.session_state["my_tickers_kr"]:
            st.session_state["my_tickers_kr"].append(new_kr)
    
    sel_kr = st.multiselect("한국 스캔 목록", options=st.session_state["my_tickers_kr"], default=st.session_state["my_tickers_kr"])
    
    if st.button("🚀 한국 종목 스캔 시작", key="start_kr"):
        for t in sel_kr:
            found = False
            for suffix in [".KS", ".KQ"]:
                full_ticker = t + suffix
                s = yf.Ticker(full_ticker)
                h = s.history(period="6mo")
                if not h.empty:
                    # [변경 포인트] 종목명(shortName 또는 longName) 가져오기
                    try:
                        stock_name = s.info.get('shortName') or s.info.get('longName') or t
                    except:
                        stock_name = t
                    
                    st.success(f"**[{stock_name} ({full_ticker})]** 현재가: {int(h['Close'].iloc[-1]):,} 원")
                    with st.expander("뉴스/공시 확인"):
                        st.markdown(f"🏛️ [네이버 증권 공시](https://finance.naver.com/item/news.naver?code={t})")
                        for n in get_stock_news(full_ticker, "KR"): st.markdown(f"- [{n['title']}]({n['link']})")
                    found = True
                    break
            if not found:
                st.error(f"[{t}] 데이터를 불러올 수 없습니다. 코드를 확인해 주세요.")

# ==========================================
# 탭 3: 정밀 분할 매수
# ==========================================
with tab3:
    st.subheader("💰 현재가 대비 지점별 정밀 계산기")
    
    c1, c2, c3 = st.columns(3)
    currency = c1.radio("통화", ["USD ($)", "KRW (원)"])
    symbol = "$" if currency == "USD ($)" else "원"
    total_budget = c2.number_input(f"총 예산 ({symbol})", value=1000.0 if symbol=="$" else 3000000.0)
    start_price = c3.number_input(f"현재가(1차 진입가) ({symbol})", value=10.0 if symbol=="$" else 50000.0)

    st.markdown("#### 📉 각 회차별 하락 목표치 설정")
    r_cols = st.columns(4)
    r2 = r_cols[0].number_input("2차 지점 하락(%)", value=5.0)
    r3 = r_cols[1].number_input("3차 지점 하락(%)", value=10.0)
    r4 = r_cols[2].number_input("4차 지점 하락(%)", value=15.0)
    r5 = r_cols[3].number_input("5차 지점 하락(%)", value=20.0)

    if total_budget > 0 and start_price > 0:
        base_unit = total_budget / 31
        rates = [0, r2, r3, r4, r5]
        data = []
        
        for i in range(1, 6):
            weight = 2**(i-1)
            target_p = start_price * (1 - (sum(rates[:i]) / 100))
            
            data.append({
                "회차": f"{i}차",
                "비중": f"{weight}배",
                "목표가": f"{symbol}{target_p:,.2f}" if symbol=="$" else f"{int(target_p):,}원",
                "매수금액": f"{symbol}{base_unit * weight:,.0f}",
                "현재가 대비": f"-{sum(rates[:i])}%"
            })
        
        df = pd.DataFrame(data)
        st.table(df)
        
        img_buf = export_as_image(df, "Trading Strategy Plan")
        st.download_button("📸 계산 결과 이미지로 저장", data=img_buf, file_name="plan.png", mime="image/png", use_container_width=True)

# ==========================================
# 탭 4: 세계 경제 뉴스
# ==========================================
with tab4:
    if st.button("🔄 실시간 뉴스 새로고침", key="refresh_news"): 
        st.rerun()
    feed = feedparser.parse("https://news.google.com/rss/search?q=global+economy+market+when:24h&hl=en-US&gl=US&ceid=US:en")
    for entry in feed.entries[:10]:
        st.markdown(f"📍 [{entry.title}]({entry.link})")
