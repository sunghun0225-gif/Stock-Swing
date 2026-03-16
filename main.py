import time
import streamlit as st
import yfinance as yf
import pandas as pd
import requests
import feedparser
import matplotlib.pyplot as plt
import io
from datetime import datetime

# ── 앱 기본 설정 ──────────────────────────────────────────────────────────────
st.set_page_config(page_title="스윙 알리미 V12.4", page_icon="🚨", layout="wide")

if "my_tickers_us" not in st.session_state:
    st.session_state["my_tickers_us"] = []
if "my_tickers_kr" not in st.session_state:
    st.session_state["my_tickers_kr"] = []
if "price_cache" not in st.session_state:
    st.session_state["price_cache"] = {}

CACHE_TTL = 300  # 5분 캐시

st.title("🚨 실시간 글로벌 스캐너 & 정밀 매매 가이드")

tab1, tab2, tab3, tab4 = st.tabs(
    ["🇺🇸 미국 종목", "🇰🇷 한국 종목", "💰 정밀 분할 매수", "🌍 세계 경제 뉴스"]
)

# ── 공시 레이블 ───────────────────────────────────────────────────────────────
FILING_LABELS = {
    "10-K": "📊 연간보고서",
    "20-F": "📊 연간보고서(외국)",
    "10-Q": "📋 분기보고서",
    "8-K":  "🔔 중요공시",
    "DEF 14A": "🗳️ 주주총회",
    "SC 13G": "📌 대량보유",
    "SC 13D": "📌 대량보유(적극)",
    "S-1":  "🚀 IPO신고",
    "4":    "👤 내부자거래",
    "3":    "👤 내부자최초",
    "5":    "👤 내부자연간",
}

def filing_label(form):
    for key, label in FILING_LABELS.items():
        if form == key or form.startswith(key):
            return label
    return f"📄 {form}"

# ── yfinance Rate Limit 대응: 재시도 + 점진적 대기 ───────────────────────────
def fetch_history_safe(ticker_obj, period="5d", retries=3, base_delay=2):
    """Rate limit 발생 시 점진적 대기 후 재시도 (2초 → 4초 → 6초)"""
    for attempt in range(retries):
        try:
            h = ticker_obj.history(period=period)
            if not h.empty:
                return h
        except Exception as e:
            msg = str(e).lower()
            if any(k in msg for k in ["rate", "429", "too many", "limit"]):
                if attempt < retries - 1:
                    wait = base_delay * (attempt + 1)
                    time.sleep(wait)
                    continue
            break
    return None

def fetch_ticker_cached(ticker: str):
    """
    session_state 캐시에서 가격 반환.
    캐시 만료(5분) 또는 미존재 시 yfinance 새 요청.
    반환: (price, info_dict, from_cache)
    """
    now = time.time()
    cache = st.session_state["price_cache"]

    if ticker in cache:
        price, ts, info_cached = cache[ticker]
        if now - ts < CACHE_TTL:
            return price, info_cached, True

    try:
        s = yf.Ticker(ticker)
        h = fetch_history_safe(s, period="5d")
        if h is not None and not h.empty:
            price = h["Close"].iloc[-1]
            try:
                info = s.info
            except Exception:
                info = {}
            cache[ticker] = (price, now, info)
            return price, info, False
    except Exception:
        pass
    return None, {}, False

# ── 네이버 금융에서 한글 종목명 조회 ─────────────────────────────────────────
@st.cache_data(ttl=86400)
def get_kr_stock_name(code: str) -> str:
    """네이버 금융 API로 한글 종목명 반환. 실패 시 빈 문자열."""
    try:
        url = f"https://finance.naver.com/item/main.naver?code={code}"
        headers = {"User-Agent": "Mozilla/5.0"}
        res = requests.get(url, headers=headers, timeout=6)
        if res.status_code == 200:
            # <title>종목명 : 네이버 금융</title> 패턴에서 추출
            import re
            match = re.search(r"<title>\s*([^:]+?)\s*:", res.text)
            if match:
                name = match.group(1).strip()
                if name and name != "네이버 금융":
                    return name
    except Exception:
        pass
    return ""

# ── SEC EDGAR CIK 조회 ────────────────────────────────────────────────────────
@st.cache_data(ttl=86400)
def get_cik(ticker: str):
    try:
        headers = {"User-Agent": "SwingScanner/1.0 contact@example.com"}
        res = requests.get(
            "https://www.sec.gov/files/company_tickers.json",
            headers=headers, timeout=10
        )
        for entry in res.json().values():
            if entry["ticker"].upper() == ticker.upper():
                return str(entry["cik_str"])
    except Exception:
        pass
    return None

# ── SEC EDGAR 실시간 공시 목록 ────────────────────────────────────────────────
def get_sec_filings(ticker: str, limit: int = 12):
    cik = get_cik(ticker)
    if not cik:
        return None, "CIK를 찾을 수 없습니다."
    try:
        headers = {"User-Agent": "SwingScanner/1.0 contact@example.com"}
        url = f"https://data.sec.gov/submissions/CIK{cik.zfill(10)}.json"
        res = requests.get(url, headers=headers, timeout=10)
        sub = res.json()
        recent = sub.get("filings", {}).get("recent", {})
        if not recent:
            return None, "공시 데이터가 없습니다."

        forms = recent.get("form", [])
        dates = recent.get("filingDate", [])

        filings = []
        for i in range(min(len(forms), limit)):
            filing_url = (
                f"https://www.sec.gov/cgi-bin/browse-edgar"
                f"?action=getcompany&CIK={cik}"
                f"&type={forms[i]}&dateb=&owner=include&count=10"
            )
            filings.append({
                "form":  forms[i],
                "date":  dates[i],
                "label": filing_label(forms[i]),
                "url":   filing_url,
                "cik":   cik,
            })
        return filings, None
    except Exception as e:
        return None, f"오류: {e}"

# ── 뉴스 수집 ─────────────────────────────────────────────────────────────────
def get_stock_news(ticker, market="US"):
    news_list = []
    try:
        query = f"{ticker}+stock" if market == "US" else f"{ticker}+주식"
        hl, gl, ceid = (
            ("en-US", "US", "US:en") if market == "US"
            else ("ko-KR", "KR", "KR:ko")
        )
        url = (
            f"https://news.google.com/rss/search"
            f"?q={query}+when:90d&hl={hl}&gl={gl}&ceid={ceid}"
        )
        feed = feedparser.parse(url)
        for entry in feed.entries[:8]:
            raw = entry.get("published_parsed")
            date_str = (
                datetime(*raw[:6]).strftime("%m-%d %H:%M") if raw else "날짜미상"
            )
            news_list.append(
                {"title": entry.title, "link": entry.link, "date": date_str}
            )
    except Exception:
        pass
    return news_list

# ── 이미지 저장 ───────────────────────────────────────────────────────────────
def export_as_image(df, title):
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.axis("off")
    ax.set_title(title, fontsize=16, weight="bold", pad=20)
    table = ax.table(
        cellText=df.values, colLabels=df.columns,
        cellLoc="center", loc="center"
    )
    table.auto_set_font_size(False)
    table.set_fontsize(11)
    table.scale(1.2, 2.5)
    buf = io.BytesIO()
    plt.savefig(buf, format="png", bbox_inches="tight", dpi=150)
    plt.close(fig)
    buf.seek(0)
    return buf

# ══════════════════════════════════════════════════════════════════════════════
# 탭 1: 미국 종목
# ══════════════════════════════════════════════════════════════════════════════
with tab1:
    st.subheader("🇺🇸 미국 시장 종목 분석")
    col_u1, col_u2 = st.columns([3, 1])
    with col_u1:
        new_us = st.text_input(
            "미국 티커 입력", placeholder="예: TSLA, AAPL", key="us_in"
        ).upper()
    if col_u2.button("미국 종목 추가") and new_us:
        if new_us not in st.session_state["my_tickers_us"]:
            st.session_state["my_tickers_us"].append(new_us)

    sel_us = st.multiselect(
        "미국 스캔 목록",
        options=st.session_state["my_tickers_us"],
        default=st.session_state["my_tickers_us"],
    )

    if st.button("🚀 미국 종목 스캔 시작", key="start_us", use_container_width=True):
        for idx, t in enumerate(sel_us):
            # 종목 간 1.5초 간격으로 Rate Limit 방지
            if idx > 0:
                time.sleep(1.5)

            with st.spinner(f"[{t}] 데이터 조회 중..."):
                price, info, from_cache = fetch_ticker_cached(t)

            if price is not None:
                cache_note = "  `캐시`" if from_cache else ""
                st.info(f"**[{t}]** 현재가: ${price:.2f}{cache_note}")

                with st.expander(f"📋 {t} SEC 실시간 공시", expanded=True):
                    with st.spinner("SEC EDGAR 공시 불러오는 중..."):
                        filings, err = get_sec_filings(t)
                    if err:
                        st.warning(err)
                        st.markdown(
                            f"🏛️ [SEC 공시 직접 검색]"
                            f"(https://www.sec.gov/cgi-bin/browse-edgar"
                            f"?CIK={t}&action=getcompany)"
                        )
                    else:
                        for f in filings:
                            col_a, col_b, col_c = st.columns([3, 2, 2])
                            col_a.markdown(f"**{f['label']}**")
                            col_b.caption(f["date"])
                            col_c.markdown(f"[원문 보기 ↗]({f['url']})")
                        st.markdown("---")
                        cik = get_cik(t)
                        st.markdown(
                            f"🏛️ [SEC EDGAR 전체 공시 보기]"
                            f"(https://www.sec.gov/cgi-bin/browse-edgar"
                            f"?action=getcompany&CIK={cik}"
                            f"&type=&dateb=&owner=include&count=40)"
                        )

                with st.expander(f"📰 {t} 뉴스 & 홈페이지"):
                    for n in get_stock_news(t, "US"):
                        st.markdown(
                            f"- [{n['title']}]({n['link']}) `[{n['date']}]`"
                        )
                    website = info.get("website")
                    st.markdown("---")
                    if website:
                        st.markdown(f"🔗 **[공식 홈페이지 바로가기]({website})**")
                    else:
                        st.caption("공식 홈페이지 정보를 찾을 수 없습니다.")
            else:
                st.error(
                    f"**[{t}]** 데이터를 불러오지 못했습니다. "
                    "잠시 후 다시 시도해 주세요. (Rate Limit)"
                )
            st.write("---")

# ══════════════════════════════════════════════════════════════════════════════
# 탭 2: 한국 종목
# ══════════════════════════════════════════════════════════════════════════════
with tab2:
    st.subheader("🇰🇷 한국 시장 종목 분석")
    st.caption("6자리 숫자 코드를 입력하세요 (예: 005930).")

    col_k1, col_k2 = st.columns([3, 1])
    with col_k1:
        new_kr = st.text_input(
            "한국 종목 코드 입력", placeholder="예: 005930", key="kr_in"
        )
    if col_k2.button("한국 종목 추가") and new_kr:
        if new_kr.isdigit() and new_kr not in st.session_state["my_tickers_kr"]:
            st.session_state["my_tickers_kr"].append(new_kr)

    sel_kr = st.multiselect(
        "한국 스캔 목록",
        options=st.session_state["my_tickers_kr"],
        default=st.session_state["my_tickers_kr"],
    )

    if st.button("🚀 한국 종목 스캔 시작", key="start_kr", use_container_width=True):
        for idx, t in enumerate(sel_kr):
            if idx > 0:
                time.sleep(1.5)

            found = False
            for suffix in [".KS", ".KQ"]:
                full_ticker = t + suffix
                with st.spinner(f"[{full_ticker}] 데이터 조회 중..."):
                    price, info, from_cache = fetch_ticker_cached(full_ticker)

                if price is not None:
                    # 1순위: 네이버 금융 한글명, 2순위: yfinance명, 3순위: 코드
                    kr_name = get_kr_stock_name(t)
                    stock_name = (
                        kr_name
                        or info.get("shortName")
                        or info.get("longName")
                        or info.get("symbol")
                        or t
                    )
                    market_label = suffix.replace(".", "")  # KS 또는 KQ
                    cache_note = "  `캐시`" if from_cache else ""
                    st.success(
                        f"**{stock_name}** `{t}` ({market_label})  |  "
                        f"현재가: {int(price):,} 원{cache_note}"
                    )

                    with st.expander("📋 DART 공시", expanded=True):
                        name_query = stock_name.split(" ")[0] if stock_name else t
                        col1, col2, col3 = st.columns(3)
                        col1.markdown(
                            f"[🏛️ DART 공시 검색]"
                            f"(https://dart.fss.or.kr/dsab001/search.ax"
                            f"?textCrpNm={name_query})"
                        )
                        col2.markdown(
                            f"[📊 네이버 공시]"
                            f"(https://finance.naver.com/item/news.naver?code={t})"
                        )
                        col3.markdown(
                            f"[📑 KIND 공시]"
                            f"(https://kind.krx.co.kr/disclosure/searchtotalinfo.do"
                            f"?method=searchTotalInfoMain&repIsuSrtCd={t})"
                        )
                        st.caption(
                            "💡 DART Open API 키를 발급받으면 실시간 공시 목록 연동이 가능합니다."
                        )

                    with st.expander("📰 뉴스 확인"):
                        for n in get_stock_news(full_ticker, "KR"):
                            st.markdown(
                                f"- [{n['title']}]({n['link']}) `[{n['date']}]`"
                            )

                    found = True
                    break

            if not found:
                st.error(
                    f"**[{t}]** 데이터를 불러오지 못했습니다. "
                    "잠시 후 다시 시도해 주세요. (Rate Limit)"
                )
            st.write("---")

# ══════════════════════════════════════════════════════════════════════════════
# 탭 3: 정밀 분할 매수 계산기
# ══════════════════════════════════════════════════════════════════════════════
with tab3:
    st.subheader("💰 현재가 대비 지점별 정밀 계산기")
    c1, c2, c3 = st.columns(3)
    currency = c1.radio("통화", ["USD ($)", "KRW (원)"])
    symbol = "$" if currency == "USD ($)" else "원"
    total_budget = c2.number_input(
        f"총 예산 ({symbol})",
        value=1000.0 if symbol == "$" else 3000000.0,
    )
    start_price = c3.number_input(
        f"현재가(1차 진입가) ({symbol})",
        value=10.0 if symbol == "$" else 50000.0,
    )

    st.markdown("#### 📉 각 회차별 하락 목표치 설정 (%)")
    r_cols = st.columns(4)
    r2 = r_cols[0].number_input("2차 지점 하락", value=5.0)
    r3 = r_cols[1].number_input("3차 지점 하락", value=10.0)
    r4 = r_cols[2].number_input("4차 지점 하락", value=15.0)
    r5 = r_cols[3].number_input("5차 지점 하락", value=20.0)

    if total_budget > 0 and start_price > 0:
        base_unit = total_budget / 31
        rates = [0, r2, r3, r4, r5]
        data = []
        for i in range(1, 6):
            weight = 2 ** (i - 1)
            target_p = start_price * (1 - (rates[i - 1] / 100))
            data.append({
                "회차": f"{i}차",
                "비중": f"{weight}배",
                "목표가": (
                    f"${target_p:,.2f}" if symbol == "$"
                    else f"{int(target_p):,}원"
                ),
                "매수금액": (
                    f"${base_unit * weight:,.0f}" if symbol == "$"
                    else f"{int(base_unit * weight):,}원"
                ),
                "현재가 대비": f"-{rates[i-1]}%",
            })
        df = pd.DataFrame(data)
        st.table(df)
        img_buf = export_as_image(df, "Trading Strategy Plan")
        st.download_button(
            "📸 계산 결과 이미지로 저장",
            data=img_buf,
            file_name="plan.png",
            mime="image/png",
            use_container_width=True,
        )

# ══════════════════════════════════════════════════════════════════════════════
# 탭 4: 세계 경제 뉴스
# ══════════════════════════════════════════════════════════════════════════════
with tab4:
    if st.button(
        "🔄 실시간 뉴스 새로고침", key="refresh_news", use_container_width=True
    ):
        st.rerun()
    feed = feedparser.parse(
        "https://news.google.com/rss/search"
        "?q=global+economy+market+when:24h&hl=en-US&gl=US&ceid=US:en"
    )
    for entry in feed.entries[:10]:
        pub_date = entry.published[:16] if "published" in entry else "최근"
        st.markdown(
            f"📍 [{entry.title}]({entry.link})  `[{pub_date}]`"
        )
        st.write("")

