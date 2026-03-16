import time
import streamlit as st
import streamlit.components.v1 as components
import yfinance as yf
import pandas as pd
import requests
import feedparser
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
def get_stock_news(query_name, market="US"):
    import urllib.parse
    news_list = []
    try:
        if market == "US":
            raw_q = f"{query_name} stock"
            hl, gl, ceid = "en-US", "US", "US:en"
        else:
            # 한글 종목명으로 검색 (종목코드.KS 대신 "삼성전자 주가" 형태)
            raw_q = f"{query_name} 주가"
            hl, gl, ceid = "ko-KR", "KR", "KR:ko"

        query = urllib.parse.quote(raw_q)
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

                    with st.expander(f"📋 {stock_name} DART 공시", expanded=True):
                        name_query = kr_name.split(" ")[0] if kr_name else (stock_name.split(" ")[0] if stock_name else t)
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

                    with st.expander(f"📰 {stock_name} 뉴스 확인"):
                        # 한글 종목명으로 검색해야 뉴스가 잘 나옴
                        news_query = kr_name or stock_name or t
                        for n in get_stock_news(news_query, "KR"):
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

    # ── 기본 설정 행 ──────────────────────────────────────────────────────────
    c1, c2, c3, c4 = st.columns([1.5, 2, 2, 1.5])
    currency = c1.radio("통화", ["USD ($)", "KRW (원)"])
    symbol = "$" if currency == "USD ($)" else "원"
    total_budget = c2.number_input(
        f"총 예산 ({symbol})",
        value=1000.0 if symbol == "$" else 3000000.0,
        min_value=0.0,
    )
    start_price = c3.number_input(
        f"현재가(1차 진입가) ({symbol})",
        value=10.0 if symbol == "$" else 50000.0,
        min_value=0.0,
    )
    num_rounds = c4.number_input(
        "총 분할 횟수",
        min_value=1, max_value=10, value=5, step=1,
    )
    num_rounds = int(num_rounds)

    # ── 회차별 하락률 입력 (2차부터, 한 행에 최대 4개씩) ─────────────────────
    if num_rounds > 1:
        st.markdown("#### 📉 각 회차별 하락 목표치 설정 (%)")
        # 기본 하락률 제안값: 5% 간격
        default_drops = [round(i * (20 / (num_rounds - 1)), 1) if num_rounds > 1 else 5.0
                         for i in range(1, num_rounds)]

        drop_rates = []  # 2차 ~ num_rounds차 하락률
        remaining = num_rounds - 1  # 입력받을 개수
        idx = 0
        while idx < remaining:
            batch = min(4, remaining - idx)  # 한 행에 최대 4개
            cols = st.columns(batch)
            for j in range(batch):
                round_no = idx + j + 2  # 2차, 3차, ...
                default_val = default_drops[idx + j] if (idx + j) < len(default_drops) else 5.0
                val = cols[j].number_input(
                    f"{round_no}차 하락 %",
                    min_value=0.0, max_value=99.0,
                    value=float(default_val),
                    step=0.5,
                    key=f"drop_{round_no}",
                )
                drop_rates.append(val)
            idx += batch
    else:
        drop_rates = []

    # ── 계산 및 테이블 출력 ───────────────────────────────────────────────────
    if total_budget > 0 and start_price > 0:
        rates = [0.0] + drop_rates          # 1차는 0% (현재가)
        total_weight = sum(2 ** i for i in range(num_rounds))  # 1+2+4+...
        base_unit = total_budget / total_weight

        data = []
        cum_amount = 0.0   # 누적 투입 금액
        cum_shares = 0.0   # 누적 매수 수량
        prev_avg = start_price  # 직전 누적 평균단가 (1차 기준은 현재가)

        for i in range(num_rounds):
            weight = 2 ** i
            amount = base_unit * weight

            if i == 0:
                # 1차: 현재가 그대로 진입
                target_p = start_price
            else:
                # 2차~: 직전 누적 평균단가에 하락률 적용
                target_p = prev_avg * (1 - rates[i] / 100)

            # 누적 평균단가 갱신
            cum_amount += amount
            cum_shares += amount / target_p
            avg_price = cum_amount / cum_shares
            prev_avg = avg_price  # 다음 회차 기준값으로 전달

            shares = amount / target_p  # 해당 회차 매수 수량

            data.append({
                "회차": f"{i + 1}차",
                "비중": f"{weight}배",
                "매수가": (
                    f"${target_p:,.2f}" if symbol == "$"
                    else f"{int(target_p):,}원"
                ),
                "매수량(주)": (
                    f"{shares:,.4f}" if symbol == "$"
                    else f"{shares:,.2f}"
                ),
                "매수금액": (
                    f"${amount:,.0f}" if symbol == "$"
                    else f"{int(amount):,}원"
                ),
                "누적 평균단가": (
                    f"${avg_price:,.2f}" if symbol == "$"
                    else f"{int(avg_price):,}원"
                ),
                "평단 대비": "기준가" if i == 0 else f"-{rates[i]}%",
            })

        df = pd.DataFrame(data)

        # ── html2canvas 방식으로 브라우저에서 직접 캡처 ──────────────────────
        meta_text = (
            f"총 {num_rounds}회 분할  |  비중 합계 {total_weight}배  |  "
            + (f"기준단위 ${base_unit:,.2f}" if symbol == "$" else f"기준단위 {int(base_unit):,}원")
        )
        title_text = f"분할 매수 전략  ({num_rounds}회)"

        # 테이블 HTML 생성
        thead = "".join(f"<th>{c}</th>" for c in df.columns)
        tbody_rows = ""
        accent_map = {
            "매수가":       "#2f9e44",
            "누적 평균단가": "#1971c2",
            "매수금액":      "#d9480f",
            "매수량(주)":    "#e67700",
            "평단 대비":     "#c92a2a",
            "회차":         "#495057",
            "비중":         "#495057",
        }
        for _, row in df.iterrows():
            cells = ""
            for col in df.columns:
                color = accent_map.get(col, "#2d3436")
                cells += f'<td style="color:{color}">{row[col]}</td>'
            tbody_rows += f"<tr>{cells}</tr>"

        # 합계 행: 총 매수량, 총 매수금액, 최종 평균단가
        total_shares_val = cum_shares
        total_amount_val = cum_amount
        final_avg_val    = avg_price
        tfoot_cells = ""
        for col in df.columns:
            if col == "회차":
                tfoot_cells += "<td>합계</td>"
            elif col == "비중":
                tfoot_cells += f"<td>{total_weight}배</td>"
            elif col == "매수가":
                tfoot_cells += "<td>—</td>"
            elif col == "매수량(주)":
                val = f"{total_shares_val:,.4f}" if symbol == "$" else f"{total_shares_val:,.2f}"
                tfoot_cells += f"<td>{val}</td>"
            elif col == "매수금액":
                val = f"${total_amount_val:,.0f}" if symbol == "$" else f"{int(total_amount_val):,}원"
                tfoot_cells += f"<td>{val}</td>"
            elif col == "누적 평균단가":
                val = f"${final_avg_val:,.2f}" if symbol == "$" else f"{int(final_avg_val):,}원"
                tfoot_cells += f"<td>{val}</td>"
            elif col == "평단 대비":
                tfoot_cells += "<td>—</td>"
            else:
                tfoot_cells += "<td>—</td>"
        tfoot_row = tfoot_cells

        # 동적 높이 계산: 헤더 + 행 수 + 여백
        component_height = 160 + len(data) * 46 + 80  # 제목+메타+버튼 여백

        html_component = f"""
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <script src="https://cdn.jsdelivr.net/npm/html2canvas@1.4.1/dist/html2canvas.min.js"></script>
  <link href="https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;600;700&display=swap" rel="stylesheet">
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      background: #f0f2f5;
      font-family: 'Noto Sans KR', 'Apple SD Gothic Neo', sans-serif;
      padding: 12px;
    }}
    #captureArea {{
      background: #ffffff;
      border-radius: 12px;
      padding: 22px 24px 18px;
      box-shadow: 0 2px 16px rgba(0,0,0,0.10);
    }}
    .title {{
      font-size: 17px; font-weight: 700; color: #1a1a2e;
      text-align: center; margin-bottom: 3px; letter-spacing: -0.3px;
    }}
    .meta {{
      font-size: 12px; color: #868e96;
      text-align: center; margin-bottom: 14px;
    }}
    table {{
      width: 100%; border-collapse: collapse; font-size: 13px;
    }}
    thead tr {{
      background: #f8f9fa;
      border-top: 2px solid #dee2e6;
      border-bottom: 2px solid #dee2e6;
    }}
    th {{
      color: #495057; padding: 10px 6px;
      font-weight: 700; text-align: center;
      font-size: 12px; letter-spacing: 0.2px;
    }}
    td {{
      padding: 10px 6px; text-align: center;
      border-bottom: 1px solid #f1f3f5;
      font-size: 13px; font-weight: 600;
    }}
    tbody tr:nth-child(even) td {{ background: #f8f9fa; }}
    tbody tr:last-child td {{ border-bottom: 2px solid #dee2e6; }}
    tfoot td {{
      padding: 10px 6px; font-weight: 700;
      text-align: center; font-size: 13px;
      background: #f1f8ff; color: #1971c2;
      border-top: 2px solid #74c0fc;
    }}
    .summary-bar {{
      margin-top: 12px;
      background: #f1f8ff;
      border-left: 4px solid #339af0;
      border-radius: 6px;
      padding: 9px 13px;
      font-size: 12px; color: #1864ab;
      font-weight: 600;
    }}
    .btn {{
      display: block; width: 100%; margin-top: 12px;
      padding: 11px; border: none; border-radius: 8px;
      background: #1971c2; color: white;
      font-size: 14px; font-weight: 700;
      font-family: 'Noto Sans KR', sans-serif;
      cursor: pointer; letter-spacing: 0.5px;
      transition: background 0.15s;
    }}
    .btn:hover {{ background: #1558a8; }}
    .btn:disabled {{ background: #adb5bd; cursor: not-allowed; }}
    #status {{ text-align:center; font-size:12px; color:#868e96; margin-top:6px; min-height:18px; }}
  </style>
</head>
<body>
  <div id="captureArea">
    <div class="title">📊 {title_text}</div>
    <div class="meta">{meta_text}</div>
    <table>
      <thead><tr>{thead}</tr></thead>
      <tbody>{tbody_rows}</tbody>
      <tfoot><tr>{tfoot_row}</tr></tfoot>
    </table>
    <div class="summary-bar">{meta_text}</div>
  </div>
  <button class="btn" id="saveBtn" onclick="saveImg()">📷 이미지로 저장</button>
  <div id="status"></div>
  <script>
    async function saveImg() {{
      const btn = document.getElementById('saveBtn');
      const status = document.getElementById('status');
      btn.disabled = true;
      btn.textContent = '⏳ 생성 중...';
      status.textContent = '';
      try {{
        // 폰트 로딩 대기
        await document.fonts.ready;
        const el = document.getElementById('captureArea');
        const canvas = await html2canvas(el, {{
          backgroundColor: "#ffffff",
          scale: 2,
          useCORS: true,
          allowTaint: true,
          logging: false,
        }});
        const dataUrl = canvas.toDataURL('image/png');
        // Streamlit iframe 내부: window.open으로 새 탭에서 직접 다운로드
        const newWin = window.open('', '_blank');
        if (newWin) {{
          newWin.document.write(
            '<html><body style="margin:0;background:#111">' +
            '<img src="' + dataUrl + '" style="max-width:100%">' +
            '<br><a href="' + dataUrl + '" download="분할매수전략.png" ' +
            'style="display:block;margin:10px;padding:10px 20px;background:#1971c2;' +
            'color:white;text-decoration:none;border-radius:6px;width:fit-content">' +
            '💾 PNG 저장' +
            '</a></body></html>'
          );
          newWin.document.close();
          status.textContent = '✅ 새 탭이 열렸습니다. 이미지를 확인 후 저장하세요.';
        }} else {{
          // 팝업 차단된 경우: 같은 탭에서 a 태그로 시도
          const link = document.createElement('a');
          link.download = '분할매수전략.png';
          link.href = dataUrl;
          document.body.appendChild(link);
          link.click();
          document.body.removeChild(link);
          status.textContent = '✅ 다운로드가 시작됩니다.';
        }}
      }} catch(e) {{
        status.textContent = '❌ 오류: ' + e.message;
      }}
      btn.disabled = false;
      btn.textContent = '📷 이미지로 저장';
    }}
  </script>
</body>
</html>
"""
        st.table(df)
        st.info(
            f"총 {num_rounds}회 분할 | 비중 합계: **{total_weight}배** 단위 "
            f"| 기준 단위: "
            + (f"**${base_unit:,.2f}**" if symbol == "$" else f"**{int(base_unit):,}원**")
        )
        st.markdown("##### 📷 이미지 저장")
        components.html(html_component, height=component_height, scrolling=False)

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

