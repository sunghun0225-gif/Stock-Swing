import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import datetime

# 1. 앱 화면 기본 설정
st.set_page_config(page_title="나만의 스윙 알리미", page_icon="🚨", layout="centered")

# 세션 상태 초기화 (종목 리스트 저장용)
if "my_tickers" not in st.session_state:
    st.session_state["my_tickers"] = []

st.title("🚨 스윙 매매 알리미 V7.2")

# 화면을 2개의 탭으로 분리
tab1, tab2 = st.tabs(["🔍 종목 스캐너", "💰 5분할 매수 계산기"])

# ==========================================
# 탭 1: 종목 스캐너 (분석 + 뉴스)
# ==========================================
with tab1:
    st.markdown("내가 원하는 종목만 자유롭게 담아서 스캔하세요!")
    
    st.subheader("📝 관심 종목 관리")
    col1, col2 = st.columns([3, 1])
    with col1:
        new_ticker = st.text_input("➕ 추가할 종목의 티커를 입력하세요", placeholder="예: TSLA, AAPL, NVDA")
    with col2:
        st.write("") 
        st.write("")
        if st.button("종목 추가"):
            if new_ticker:
                t = new_ticker.strip().upper()
                if t not in st.session_state["my_tickers"]:
                    st.session_state["my_tickers"].append(t)
                    st.success(f"[{t}] 추가 완료!")
                else:
                    st.warning("이미 등록된 종목입니다.")

    current_tickers = st.multiselect(
        "현재 스캔 대기 중인 종목 (X를 눌러 삭제)",
        options=st.session_state["my_tickers"],
        default=st.session_state["my_tickers"]
    )
    st.session_state["my_tickers"] = current_tickers
    st.write("---")

    # --- 분석 로직 ---
    def check_stock_conditions(ticker, volume_multiplier=3, min_volume=1000000):
        try:
            stock = yf.Ticker(ticker)
            # 데이터 수집 시도 (안정성을 위해 6개월치 호출)
            hist = stock.history(period="6mo")
            info = stock.info
            
            if hist.empty or 'Volume' not in hist.columns:
                return {"status": "error", "message": f"[{ticker}] 데이터를 불러올 수 없습니다."}
            if len(hist) < 20:
                return {"status": "error", "message": f"[{ticker}] 상장 기간이 짧아 분석이 불가능합니다."}
                
            current_volume = hist['Volume'].iloc[-1]
            current_price = hist['Close'].iloc[-1]
            market_cap = info.get('marketCap', 0)
            
            # 기술적 지표 계산 (20일선, 5일선)
            ma20 = hist['Close'].iloc[-20:].mean()
            ma5 = hist['Close'].iloc[-5:].mean()
            
            # 평균 거래량 계산
            avg_volume_20d = hist['Volume'].iloc[-21:-1].mean()
            if pd.isna(avg_volume_20d) or avg_volume_20d == 0: avg_volume_20d = 1 
            
            # 조건 판별
            is_volume_spike = (current_volume >= avg_volume_20d * volume_multiplier) and (current_volume >= min_volume)
            cond_price = 0.5 <= current_price <= 5.0
            cond_mcap = market_cap <= 300000000 if market_cap > 0 else False
            cond_trend = (current_price >= ma20) or (ma5 >= ma20)
            
            return {
                "status": "success", "ticker": ticker, "is_spike": is_volume_spike,
                "current_volume": int(current_volume), "ratio": round(current_volume / avg_volume_20d, 2),
                "current_price": round(current_price, 2), "cond_price": cond_price,
                "cond_mcap": cond_mcap, "cond_trend": cond_trend,
                "all_conditions_met": cond_price and cond_mcap and cond_trend 
            }
        except Exception as e:
            return {"status": "error", "message": f"[{ticker}] 분석 중 오류 발생: {str(e)}"}

    # --- 뉴스 수집 로직 (보강 버전) ---
    def get_unique_news(ticker, limit=5):
        try:
            stock = yf.Ticker(ticker)
            # yfinance 내부 뉴스 객체 호출
            raw_news = getattr(stock, 'news', [])
            
            if not raw_news:
                return []
                
            unique_news = []
            seen_titles = set()
            
            for item in raw_news:
                title = item.get('title', '').strip()
                link = item.get('link', '')
                
                # 빈 제목 및 중복 제목 필터링
                if title and title not in seen_titles:
                    seen_titles.add(title)
                    pub_time = item.get('providerPublishTime')
                    time_str = datetime.fromtimestamp(pub_time).strftime('%m-%d %H:%M') if pub_time else "시간 정보 없음"
                    unique_news.append({"title": title, "link": link, "time": time_str})
                
                if len(unique_news) >= limit:
                    break
            return unique_news
        except:
            return []

    # --- 스캔 실행 ---
    if st.button("🚀 종합 스캔 시작 (거래량 + 조건 + 뉴스)", use_container_width=True):
        if not current_tickers:
            st.error("🚨 스캔할 종목이 없습니다! 위에서 종목을 먼저 추가해 주세요.")
        else:
            with st.spinner('실시간 분석 중... (최대 1분 소요)'):
                for ticker in current_tickers:
                    result = check_stock_conditions(ticker)
                    
                    if result.get("status") == "error":
                        st.error(result["message"])
                        continue
                    
                    # 1. 메인 결과 박스
                    if result['is_spike'] and result['all_conditions_met']:
                        st.success(f"### 🌟 [{result['ticker']}] 완벽 타점! (거래량 {result['ratio']}배)")
                    elif result['is_spike']:
                        st.warning(f"### 🔥 [{result['ticker']}] 거래량 급등 ({result['ratio']}배)")
                    else:
                        st.info(f"### 💤 [{result['ticker']}] 관망 (현재가: ${result['current_price']})")
                    
                    # 2. 사진 조건 체크리스트
                    with st.expander(f"✅ [{ticker}] 사진 조건 검증 결과 보기"):
                        st.markdown(f"- **주가 범위 ($0.5 ~ $5.0):** {'🟢 통과' if result['cond_price'] else '🔴 미달'}")
                        st.markdown(f"- **시가총액 (소형주 기준):** {'🟢 통과' if result['cond_mcap'] else '🔴 무거움/데이터 없음'}")
                        st.markdown(f"- **이평선 추세 (20일선 위):** {'🟢 통과' if result['cond_trend'] else '🔴 역배열/하강추세'}")
                    
                    # 3. 보강된 뉴스 출력
                    news_list = get_unique_news(ticker)
                    with st.expander(f"📰 [{ticker}] 최신 뉴스 및 공시 보기"):
                        if news_list:
                            for news in news_list:
                                st.markdown(f"- [{news['title']}]({news['link']}) `[{news['time']}]`")
                        else:
                            st.write("최근 뉴스가 없거나 수집에 실패했습니다 (AAPL 등 대형주로 먼저 테스트해보세요).")
                    
                    st.write("---")

# ==========================================
# 탭 2: 5분할 매수 계산기
# ==========================================
with tab2:
    st.subheader("💰 5분할 물타기 (1:2 비율) 계산기")
    st.markdown("최종 금액을 입력하면 **1차 초기 진입 금액**을 바로 알려드립니다.")
    st.write("---")
    
    total_budget = st.number_input("💵 해당 종목에 투입할 '최종 목표 금액'을 입력하세요", min_value=0, value=310000, step=10000)
    
    if total_budget > 0:
        base_unit = total_budget / 31
        st.success(f"### 🎯 1차 진입(초기) 금액: **{int(base_unit):,}** 원")
        
        st.write("---")
        st.markdown("#### 📉 단계별 매수 비중 (마틴게일)")
        c1, c2, c3 = st.columns(3)
        c1.info(f"**1차 (1배)**\n\n{int(base_unit * 1):,} 원")
        c2.info(f"**2차 (2배)**\n\n{int(base_unit * 2):,} 원")
        c3.info(f"**3차 (4배)**\n\n{int(base_unit * 4):,} 원")
        
        c4, c5 = st.columns(2)
        c4.warning(f"**4차 (8배)**\n\n{int(base_unit * 8):,} 원")
        c5.error(f"**5차 (16배)**\n\n{int(base_unit * 16):,} 원")
