import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import datetime
import feedparser
import matplotlib.pyplot as plt
import io

# 1. 앱 기본 설정
st.set_page_config(page_title="스윙 알리미 V11.0", page_icon="🚨", layout="wide")

if "my_tickers" not in st.session_state:
    st.session_state["my_tickers"] = []

st.title("🚨 실시간 스윙 스캐너 & 스마트 매매 가이드")

tab1, tab2, tab3 = st.tabs(["🔍 종목 스캐너", "💰 정밀 분할 매수", "🌍 세계 경제 뉴스"])

# --- [함수] 표를 이미지로 변환하는 로직 ---
def export_table_as_image(df, title_text):
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.axis('off')
    ax.set_title(title_text, fontsize=18, weight='bold', pad=20)
    
    # 테이블 생성
    table = ax.table(cellText=df.values, colLabels=df.columns, cellLoc='center', loc='center', colColours=["#f2f2f2"]*len(df.columns))
    table.auto_set_font_size(False)
    table.set_fontsize(12)
    table.scale(1.2, 2.5)
    
    # 이미지를 바이트로 변환
    buf = io.BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight', dpi=150)
    buf.seek(0)
    return buf

# ==========================================
# 탭 1: 종목 스캐너
# ==========================================
with tab1:
    st.subheader("📝 종목 분석")
    col_in, col_bt = st.columns([3, 1])
    with col_in:
        new_tk = st.text_input("티커 입력", placeholder="예: ALVO, AAPL").upper()
    with col_bt:
        st.write(""); st.write("")
        if st.button("추가"):
            if new_tk and new_tk not in st.session_state["my_tickers"]:
                st.session_state["my_tickers"].append(new_tk)
                
    selected_tickers = st.multiselect("스캔 목록", options=st.session_state["my_tickers"], default=st.session_state["my_tickers"])
    
    if st.button("🚀 종합 스캔 시작", use_container_width=True):
        for ticker in selected_tickers:
            try:
                stock = yf.Ticker(ticker)
                hist = stock.history(period="6mo")
                if hist.empty: continue
                curr_price = hist['Close'].iloc[-1]
                st.info(f"### 📈 [{ticker}] 현재가: ${curr_price:.2f}")
                with st.expander(f"📊 {ticker} 정보 및 공시"):
                    st.markdown(f"🏛️ [SEC 공식 공시](https://www.sec.gov/cgi-bin/browse-edgar?CIK={ticker}&action=getcompany) | 📢 [IR 게시판](https://www.google.com/search?q={ticker}+Investor+Relations)")
            except: st.error(f"{ticker} 분석 실패")

# ==========================================
# 탭 2: 정밀 분할 매수 (그림 저장 기능 추가)
# ==========================================
with tab2:
    st.subheader("💰 회차별 하락폭 지정형 5분할 계산기")
    
    c_set1, c_set2, c_set3 = st.columns(3)
    with c_set1:
        currency = st.radio("통화", ["USD ($)", "KRW (원)"])
        symbol = "$" if currency == "USD ($)" else "원"
    with c_set2:
        total_budget = st.number_input(f"총 예산 ({symbol})", value=1000.0 if symbol=="$" else 3100000.0, step=100.0)
    with c_set3:
        start_price = st.number_input(f"1차 진입가 ({symbol})", value=10.0 if symbol=="$" else 15000.0, step=0.1)

    st.markdown("#### 📉 회차별 하락률 설정")
    r_cols = st.columns(4)
    r2 = r_cols[0].number_input("2차 하락(%)", value=5.0)
    r3 = r_cols[1].number_input("3차 하락(%)", value=10.0)
    r4 = r_cols[2].number_input("4차 하락(%)", value=15.0)
    r5 = r_cols[3].number_input("5차 하락(%)", value=20.0)

    if total_budget > 0 and start_price > 0:
        base_unit = total_budget / 31
        rates = [0, r2, r3, r4, r5]
        data = []
        target_price = start_price
        
        for i in range(1, 6):
            weight = 2**(i-1)
            buy_amt = base_unit * weight
            if i > 1: target_price = target_price * (1 - (rates[i-1] / 100))
            
            data.append({
                "회차": f"{i}차",
                "비중": f"{weight}배",
                "목표가": f"{symbol}{target_price:,.2f}",
                "매수금액": f"{symbol}{buy_amt:,.0f}",
                "조건": f"-{rates[i-1]}%" if i > 1 else "시작가"
            })
        
        df = pd.DataFrame(data)
        st.table(df)
        
        # --- 그림으로 저장 버튼 ---
        title_name = f"Split Purchase Strategy ({datetime.now().strftime('%Y-%m-%d')})"
        img_buf = export_table_as_image(df, title_name)
        
        st.download_button(
            label="📸 계산 결과 그림으로 저장 (PNG)",
            data=img_buf,
            file_name=f"trading_plan_{datetime.now().strftime('%Y%m%d_%H%M')}.png",
            mime="image/png",
            use_container_width=True
        )

# ==========================================
# 탭 3: 세계 경제 뉴스 (새로고침 버튼)
# ==========================================
with tab3:
    st.subheader("🌍 글로벌 경제 실시간 뉴스")
    
    # 새로고침 버튼
    if st.button("🔄 뉴스 실시간 새로고침", use_container_width=True):
        st.rerun()
        
    st.write("---")
    try:
        feed = feedparser.parse("https://news.google.com/rss/search?q=global+economy+market+when:24h&hl=en-US&gl=US&ceid=US:en")
        for entry in feed.entries[:12]:
            st.markdown(f"📍 [{entry.title}]({entry.link})")
            st.caption(f"출처: {entry.source.get('title', 'Google News')} | {entry.published if 'published' in entry else ''}")
            st.write("")
    except: st.write("뉴스를 불러올 수 없습니다.")

