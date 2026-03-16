import { useState, useCallback } from "react";

const Badge = ({ children, color = "#00ff9d" }) => (
  <span style={{
    display: "inline-block", padding: "2px 8px", borderRadius: 3,
    background: color + "22", color, border: `1px solid ${color}55`,
    fontSize: 11, fontFamily: "monospace", fontWeight: 700, letterSpacing: 1
  }}>{children}</span>
);

const Card = ({ children, style = {} }) => (
  <div style={{
    background: "#0d1117", border: "1px solid #21262d",
    borderRadius: 8, padding: "18px 20px", marginBottom: 12, ...style
  }}>{children}</div>
);

const Spinner = () => (
  <div style={{ display: "flex", alignItems: "center", gap: 10, color: "#8b949e", fontSize: 13 }}>
    <div style={{
      width: 16, height: 16, border: "2px solid #21262d",
      borderTop: "2px solid #00ff9d", borderRadius: "50%",
      animation: "spin 0.8s linear infinite"
    }} />
    불러오는 중...
  </div>
);

const fmt = (n, sym) =>
  sym === "$"
    ? `$${Number(n).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
    : `${Math.round(n).toLocaleString("ko-KR")}원`;

// ── Filing type badge color ───────────────────────────────────────────────────
const filingColor = (form) => {
  if (["10-K", "20-F"].includes(form)) return "#f0883e";
  if (["10-Q"].includes(form)) return "#58a6ff";
  if (form?.startsWith("8-K")) return "#ff7b72";
  if (form?.startsWith("SC")) return "#bc8cff";
  if (form?.startsWith("DEF")) return "#ffa657";
  return "#8b949e";
};

const filingLabel = (form) => {
  const map = {
    "10-K": "연간보고서", "20-F": "연간보고서(외국)",
    "10-Q": "분기보고서", "8-K": "중요공시",
    "DEF 14A": "주주총회", "SC 13G": "대량보유",
    "SC 13D": "대량보유(적극)", "S-1": "IPO신고",
    "424B4": "공모신고", "4": "내부자거래",
    "3": "내부자최초", "5": "내부자연간"
  };
  return map[form] || form;
};

// ── SEC EDGAR Real-time filings ───────────────────────────────────────────────
async function fetchSECFilings(ticker) {
  try {
    // Step 1: Get CIK from ticker
    const searchRes = await fetch(
      `https://efts.sec.gov/LATEST/search-index?q=%22${ticker}%22&dateRange=custom&startdt=2020-01-01&forms=10-K,10-Q,8-K,SC+13G,SC+13D,DEF+14A,4`,
      { headers: { "User-Agent": "SwingScanner/1.0 contact@example.com" } }
    );

    // Use company search API instead
    const cikRes = await fetch(
      `https://www.sec.gov/cgi-bin/browse-edgar?company=&CIK=${ticker}&type=&dateb=&owner=include&count=1&search_text=&action=getcompany&output=atom`,
      { headers: { "User-Agent": "SwingScanner/1.0 contact@example.com" } }
    );

    // Get submissions via EDGAR REST API
    const subRes = await fetch(
      `https://data.sec.gov/submissions/CIK${String(
        await getCIK(ticker)
      ).padStart(10, "0")}.json`,
      { headers: { "User-Agent": "SwingScanner/1.0 contact@example.com" } }
    );
    const sub = await subRes.json();
    const recent = sub.filings?.recent;
    if (!recent) return [];

    const filings = [];
    for (let i = 0; i < Math.min(recent.form.length, 15); i++) {
      filings.push({
        form: recent.form[i],
        date: recent.filingDate[i],
        description: recent.primaryDocument[i],
        accNo: recent.accessionNumber[i],
        cik: sub.cik,
      });
    }
    return filings;
  } catch (e) {
    return null;
  }
}

async function getCIK(ticker) {
  const res = await fetch(
    `https://efts.sec.gov/LATEST/search-index?q=%22${ticker}%22&forms=10-K&hits.hits._source=period_of_report`,
    { headers: { "User-Agent": "SwingScanner/1.0 contact@example.com" } }
  );
  // fallback: use company tickers JSON
  const tickerRes = await fetch(
    "https://www.sec.gov/files/company_tickers.json",
    { headers: { "User-Agent": "SwingScanner/1.0 contact@example.com" } }
  );
  const data = await tickerRes.json();
  const entry = Object.values(data).find(
    (c) => c.ticker.toUpperCase() === ticker.toUpperCase()
  );
  if (!entry) throw new Error("CIK not found");
  return entry.cik_str;
}

// ── DART Korean filings via Claude web search ─────────────────────────────────
async function fetchKoreanFilings(ticker, name) {
  const res = await fetch("https://api.anthropic.com/v1/messages", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      model: "claude-sonnet-4-20250514",
      max_tokens: 1000,
      tools: [{ type: "web_search_20250305", name: "web_search" }],
      messages: [{
        role: "user",
        content: `Search for recent corporate disclosure filings for Korean stock ${ticker} (${name || ticker}) on DART (dart.fss.or.kr) or Korean financial news. Find the 6 most recent major filings (실적발표, 사업보고서, 반기보고서, 분기보고서, 주요사항보고, 대량보유). Return ONLY JSON array: [{"form":"공시종류","date":"YYYY-MM-DD","title":"공시제목","dart_link":"https://dart.fss.or.kr/..."}]. No markdown, no explanation.`
      }]
    })
  });
  const data = await res.json();
  const text = data.content?.map(c => c.text || "").join("") || "[]";
  const clean = text.replace(/```json|```/g, "").trim();
  const s = clean.indexOf("["), e = clean.lastIndexOf("]");
  if (s === -1) return [];
  try { return JSON.parse(clean.slice(s, e + 1)); } catch { return []; }
}

// ── FilingPanel component ─────────────────────────────────────────────────────
function FilingPanel({ ticker, market, stockName }) {
  const [filings, setFilings] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      if (market === "US") {
        const data = await fetchSECFilings(ticker);
        if (!data || data.length === 0) setError("SEC 공시를 찾을 수 없습니다.");
        else setFilings(data);
      } else {
        const data = await fetchKoreanFilings(ticker, stockName);
        if (!data || data.length === 0) setError("DART 공시를 찾을 수 없습니다.");
        else setFilings(data);
      }
    } catch (e) {
      setError("공시 데이터를 불러오지 못했습니다.");
    }
    setLoading(false);
  }, [ticker, market, stockName]);

  if (!filings && !loading && !error) {
    return (
      <button onClick={load} style={{
        background: "none", border: "1px solid #30363d", borderRadius: 5,
        color: "#f0883e", padding: "6px 14px", cursor: "pointer",
        fontSize: 12, fontFamily: "monospace", marginTop: 8
      }}>
        📋 실시간 공시 불러오기
      </button>
    );
  }

  return (
    <div style={{ marginTop: 14 }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 10 }}>
        <span style={{ color: "#f0883e", fontSize: 12, fontWeight: 700, fontFamily: "monospace" }}>
          📋 {market === "US" ? "SEC EDGAR 실시간 공시" : "DART 최근 공시"}
        </span>
        <button onClick={load} style={{
          background: "none", border: "1px solid #21262d", borderRadius: 4,
          color: "#8b949e", padding: "3px 10px", cursor: "pointer", fontSize: 11
        }}>↻ 새로고침</button>
      </div>

      {loading && <Spinner />}
      {error && <span style={{ color: "#f85149", fontSize: 13 }}>{error}</span>}

      {filings && (
        <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          {filings.map((f, i) => {
            const form = f.form;
            const color = filingColor(form);
            const link = market === "US"
              ? `https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=${f.cik}&type=${encodeURIComponent(form)}&dateb=&owner=include&count=10`
              : f.dart_link || `https://dart.fss.or.kr/`;

            return (
              <a key={i} href={link} target="_blank" rel="noreferrer" style={{
                display: "flex", alignItems: "center", gap: 10,
                padding: "9px 12px", background: "#161b22",
                borderRadius: 6, border: "1px solid #21262d",
                textDecoration: "none", transition: "border-color 0.15s"
              }}
                onMouseEnter={e => e.currentTarget.style.borderColor = color + "88"}
                onMouseLeave={e => e.currentTarget.style.borderColor = "#21262d"}
              >
                <Badge color={color}>{form}</Badge>
                <span style={{ flex: 1, color: "#c9d1d9", fontSize: 13, lineHeight: 1.4 }}>
                  {market === "US" ? filingLabel(form) : (f.title || filingLabel(form))}
                </span>
                <span style={{ color: "#484f58", fontSize: 11, fontFamily: "monospace", whiteSpace: "nowrap" }}>
                  {f.date}
                </span>
                <span style={{ color: color, fontSize: 11 }}>↗</span>
              </a>
            );
          })}
        </div>
      )}

      {market === "KR" && (
        <a href={`https://dart.fss.or.kr/dsab001/search.ax?textCrpNm=${stockName || ticker}`}
          target="_blank" rel="noreferrer" style={{
            display: "inline-block", marginTop: 10, color: "#58a6ff",
            fontSize: 12, textDecoration: "none",
            borderBottom: "1px solid #58a6ff44"
          }}>
          🏛️ DART 전체 공시 검색 →
        </a>
      )}
    </div>
  );
}

// ── Stock Scanner ─────────────────────────────────────────────────────────────
function StockScanner({ market }) {
  const [tickers, setTickers] = useState([]);
  const [input, setInput] = useState("");
  const [results, setResults] = useState({});
  const [loading, setLoading] = useState(false);
  const [expanded, setExpanded] = useState({});

  const isUS = market === "US";

  const addTicker = () => {
    const v = input.trim().toUpperCase();
    if (!v || tickers.includes(v)) return;
    setTickers(prev => [...prev, v]);
    setInput("");
  };

  const scan = useCallback(async () => {
    if (!tickers.length) return;
    setLoading(true);
    setResults({});

    const prompt = isUS
      ? `For US stock tickers: ${tickers.join(", ")}, provide analysis. Respond ONLY in JSON:
{"AAPL": {"price_note": "~$195", "news": ["key news 1", "key news 2", "key news 3"], "website": "https://apple.com", "outlook": "2-sentence outlook."}, ...}`
      : `For Korean stock codes: ${tickers.join(", ")}, provide analysis in Korean. Respond ONLY in JSON:
{"005930": {"name": "삼성전자 (Samsung Electronics)", "price_note": "~70,000원", "news": ["뉴스1", "뉴스2", "뉴스3"], "outlook": "2문장 전망."}, ...}`;

    try {
      const res = await fetch("https://api.anthropic.com/v1/messages", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          model: "claude-sonnet-4-20250514",
          max_tokens: 1000,
          messages: [{ role: "user", content: prompt }]
        })
      });
      const data = await res.json();
      const text = data.content?.map(c => c.text || "").join("") || "{}";
      const clean = text.replace(/```json|```/g, "").trim();
      setResults(JSON.parse(clean));
    } catch {
      setResults({ error: "데이터를 불러오지 못했습니다." });
    }
    setLoading(false);
  }, [tickers, isUS]);

  const toggleExpand = (t) => setExpanded(prev => ({ ...prev, [t]: !prev[t] }));

  return (
    <div>
      <div style={{ display: "flex", gap: 8, marginBottom: 16 }}>
        <input
          value={input}
          onChange={e => setInput(isUS ? e.target.value.toUpperCase() : e.target.value)}
          onKeyDown={e => e.key === "Enter" && addTicker()}
          placeholder={isUS ? "예: TSLA, AAPL" : "예: 005930"}
          style={{
            flex: 1, background: "#161b22", border: "1px solid #30363d",
            borderRadius: 6, padding: "10px 14px", color: "#e6edf3",
            fontSize: 14, fontFamily: "monospace", outline: "none"
          }}
        />
        <button onClick={addTicker} style={{
          background: "#21262d", border: "1px solid #30363d", borderRadius: 6,
          color: "#e6edf3", padding: "10px 18px", cursor: "pointer",
          fontSize: 13, fontWeight: 600
        }}>+ 추가</button>
      </div>

      {tickers.length > 0 && (
        <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginBottom: 16 }}>
          {tickers.map(t => (
            <span key={t} style={{
              display: "flex", alignItems: "center", gap: 6,
              background: "#161b22", border: "1px solid #30363d",
              borderRadius: 20, padding: "4px 12px", fontSize: 13,
              color: "#e6edf3", fontFamily: "monospace"
            }}>
              {t}
              <span onClick={() => setTickers(prev => prev.filter(x => x !== t))}
                style={{ cursor: "pointer", color: "#8b949e", fontSize: 16 }}>×</span>
            </span>
          ))}
        </div>
      )}

      <button onClick={scan} disabled={loading || !tickers.length} style={{
        width: "100%", padding: 13, borderRadius: 7,
        background: tickers.length ? "linear-gradient(135deg,#00ff9d22,#00b4ff22)" : "#161b22",
        border: `1px solid ${tickers.length ? "#00ff9d55" : "#21262d"}`,
        color: tickers.length ? "#00ff9d" : "#484f58",
        fontSize: 15, fontWeight: 700, cursor: tickers.length ? "pointer" : "default",
        letterSpacing: 1, fontFamily: "monospace", marginBottom: 20
      }}>
        🚀 {isUS ? "미국" : "한국"} 종목 스캔 시작
      </button>

      {loading && <Spinner />}
      {results.error && <Card style={{ borderColor: "#f8514955" }}><span style={{ color: "#f85149" }}>{results.error}</span></Card>}

      {!loading && Object.entries(results).filter(([k]) => k !== "error").map(([ticker, info]) => (
        <Card key={ticker}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <span style={{ fontSize: 17, fontWeight: 800, color: "#e6edf3", fontFamily: "monospace" }}>
                {isUS ? ticker : (info.name || ticker)}
              </span>
              {!isUS && <Badge color="#58a6ff">{ticker}</Badge>}
            </div>
            <span style={{ color: "#00ff9d", fontFamily: "monospace", fontSize: 13 }}>{info.price_note}</span>
          </div>

          <p style={{ color: "#8b949e", fontSize: 13, margin: "0 0 10px", lineHeight: 1.6 }}>{info.outlook}</p>

          {/* Filing Panel - always visible */}
          <FilingPanel ticker={ticker} market={market} stockName={info.name} />

          <button onClick={() => toggleExpand(ticker)} style={{
            background: "none", border: "1px solid #21262d", borderRadius: 5,
            color: "#58a6ff", padding: "6px 14px", cursor: "pointer",
            fontSize: 12, fontFamily: "monospace", marginTop: 10
          }}>
            {expanded[ticker] ? "▲ 접기" : "▼ 뉴스 & 링크 보기"}
          </button>

          {expanded[ticker] && (
            <div style={{ marginTop: 14, paddingTop: 14, borderTop: "1px solid #21262d" }}>
              {(info.news || []).map((n, i) => (
                <div key={i} style={{ padding: "7px 0", borderBottom: "1px solid #161b22", color: "#c9d1d9", fontSize: 13 }}>
                  📰 {n}
                </div>
              ))}
              <div style={{ display: "flex", gap: 10, flexWrap: "wrap", marginTop: 12 }}>
                {isUS && (
                  <a href={`https://www.sec.gov/cgi-bin/browse-edgar?CIK=${ticker}&action=getcompany`}
                    target="_blank" rel="noreferrer" style={{
                      color: "#f0883e", fontSize: 13, textDecoration: "none",
                      border: "1px solid #f0883e44", borderRadius: 5, padding: "5px 12px"
                    }}>🏛️ SEC 전체 공시</a>
                )}
                {isUS && info.website && (
                  <a href={info.website} target="_blank" rel="noreferrer" style={{
                    color: "#58a6ff", fontSize: 13, textDecoration: "none",
                    border: "1px solid #58a6ff44", borderRadius: 5, padding: "5px 12px"
                  }}>🔗 공식 홈페이지</a>
                )}
                {!isUS && (
                  <a href={`https://finance.naver.com/item/news.naver?code=${ticker}`}
                    target="_blank" rel="noreferrer" style={{
                      color: "#00ff9d", fontSize: 13, textDecoration: "none",
                      border: "1px solid #00ff9d44", borderRadius: 5, padding: "5px 12px"
                    }}>📊 네이버 증권</a>
                )}
              </div>
            </div>
          )}
        </Card>
      ))}
    </div>
  );
}

// ── Split Buy Calculator ──────────────────────────────────────────────────────
function SplitBuyCalc() {
  const [currency, setCurrency] = useState("USD");
  const [budget, setBudget] = useState(1000);
  const [startPrice, setStartPrice] = useState(10);
  const [drops, setDrops] = useState([0, 5, 10, 15, 20]);
  const sym = currency === "USD" ? "$" : "원";
  const baseUnit = budget / 31;
  const rows = [1, 2, 3, 4, 5].map(i => ({
    round: i, weight: Math.pow(2, i - 1),
    targetPrice: startPrice * (1 - drops[i - 1] / 100),
    amount: baseUnit * Math.pow(2, i - 1), drop: drops[i - 1]
  }));

  return (
    <div>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 12, marginBottom: 20 }}>
        <div>
          <label style={{ color: "#8b949e", fontSize: 12, display: "block", marginBottom: 6 }}>통화</label>
          <div style={{ display: "flex", gap: 6 }}>
            {["USD", "KRW"].map(c => (
              <button key={c} onClick={() => setCurrency(c)} style={{
                flex: 1, padding: 10, borderRadius: 6,
                background: currency === c ? "#00ff9d22" : "#161b22",
                border: `1px solid ${currency === c ? "#00ff9d" : "#30363d"}`,
                color: currency === c ? "#00ff9d" : "#8b949e",
                cursor: "pointer", fontSize: 13, fontFamily: "monospace"
              }}>{c === "USD" ? "$ USD" : "₩ KRW"}</button>
            ))}
          </div>
        </div>
        <div>
          <label style={{ color: "#8b949e", fontSize: 12, display: "block", marginBottom: 6 }}>총 예산 ({sym})</label>
          <input type="number" value={budget} onChange={e => setBudget(+e.target.value)} style={{
            width: "100%", background: "#161b22", border: "1px solid #30363d",
            borderRadius: 6, padding: "10px 12px", color: "#e6edf3",
            fontSize: 14, fontFamily: "monospace", boxSizing: "border-box"
          }} />
        </div>
        <div>
          <label style={{ color: "#8b949e", fontSize: 12, display: "block", marginBottom: 6 }}>현재가 ({sym})</label>
          <input type="number" value={startPrice} onChange={e => setStartPrice(+e.target.value)} style={{
            width: "100%", background: "#161b22", border: "1px solid #30363d",
            borderRadius: 6, padding: "10px 12px", color: "#e6edf3",
            fontSize: 14, fontFamily: "monospace", boxSizing: "border-box"
          }} />
        </div>
      </div>

      <div style={{ marginBottom: 20 }}>
        <p style={{ color: "#8b949e", fontSize: 13, marginBottom: 10 }}>📉 각 회차별 하락 목표치 (%)</p>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(4,1fr)", gap: 10 }}>
          {[2, 3, 4, 5].map(i => (
            <div key={i}>
              <label style={{ color: "#8b949e", fontSize: 11, display: "block", marginBottom: 4 }}>{i}차 하락 %</label>
              <input type="number" value={drops[i - 1]}
                onChange={e => { const d = [...drops]; d[i - 1] = +e.target.value; setDrops(d); }}
                style={{
                  width: "100%", background: "#161b22", border: "1px solid #30363d",
                  borderRadius: 5, padding: "8px 10px", color: "#e6edf3",
                  fontSize: 13, fontFamily: "monospace", boxSizing: "border-box"
                }} />
            </div>
          ))}
        </div>
      </div>

      <div style={{ overflowX: "auto" }}>
        <table style={{ width: "100%", borderCollapse: "collapse", fontFamily: "monospace" }}>
          <thead>
            <tr style={{ background: "#161b22" }}>
              {["회차", "비중", "목표가", "매수금액", "현재가 대비"].map(h => (
                <th key={h} style={{ padding: "12px 14px", textAlign: "left", color: "#8b949e", fontSize: 12, borderBottom: "1px solid #21262d" }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((r, idx) => {
              const colors = ["#00ff9d", "#58a6ff", "#f0883e", "#ff7b72", "#f85149"];
              const color = colors[idx];
              return (
                <tr key={r.round} style={{ borderBottom: "1px solid #161b22" }}>
                  <td style={{ padding: "13px 14px", color }}><strong>{r.round}차</strong></td>
                  <td style={{ padding: "13px 14px" }}><Badge color={color}>{r.weight}배</Badge></td>
                  <td style={{ padding: "13px 14px", color: "#e6edf3" }}>{fmt(r.targetPrice, sym)}</td>
                  <td style={{ padding: "13px 14px", color }}><strong>{fmt(r.amount, sym)}</strong></td>
                  <td style={{ padding: "13px 14px", color: r.drop > 0 ? "#f85149" : "#00ff9d" }}>
                    {r.drop > 0 ? `▼ -${r.drop}%` : "기준가"}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <div style={{ marginTop: 14, padding: "12px 16px", background: "#161b22", borderRadius: 6, borderLeft: "3px solid #00ff9d" }}>
        <span style={{ color: "#8b949e", fontSize: 12 }}>기준 단위: </span>
        <span style={{ color: "#00ff9d", fontFamily: "monospace", fontSize: 13 }}>
          {fmt(baseUnit, sym)} (총 예산 ÷ 31)
        </span>
      </div>
    </div>
  );
}

// ── World News ────────────────────────────────────────────────────────────────
function WorldNews() {
  const [news, setNews] = useState([]);
  const [loading, setLoading] = useState(false);
  const [fetched, setFetched] = useState(false);
  const sentColor = { positive: "#00ff9d", negative: "#f85149", neutral: "#8b949e" };
  const sentLabel = { positive: "📈 긍정", negative: "📉 부정", neutral: "➡️ 중립" };

  const fetchNews = async () => {
    setLoading(true);
    try {
      const res = await fetch("https://api.anthropic.com/v1/messages", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          model: "claude-sonnet-4-20250514",
          max_tokens: 1000,
          tools: [{ type: "web_search_20250305", name: "web_search" }],
          messages: [{ role: "user", content: "Search for the top 8 latest global economy and stock market news today. Return ONLY a JSON array: [{\"title\":\"...\",\"summary\":\"...\",\"topic\":\"...\",\"sentiment\":\"positive|negative|neutral\"}]. No markdown." }]
        })
      });
      const data = await res.json();
      const text = data.content?.map(c => c.text || "").join("") || "[]";
      const clean = text.replace(/```json|```/g, "").trim();
      const s = clean.indexOf("["), e = clean.lastIndexOf("]");
      if (s !== -1) setNews(JSON.parse(clean.slice(s, e + 1)));
    } catch { setNews([{ title: "뉴스를 불러오지 못했습니다.", summary: "다시 시도해 주세요.", topic: "오류", sentiment: "neutral" }]); }
    setLoading(false);
    setFetched(true);
  };

  return (
    <div>
      <button onClick={fetchNews} disabled={loading} style={{
        width: "100%", padding: 13, borderRadius: 7,
        background: "linear-gradient(135deg,#58a6ff22,#00ff9d22)",
        border: "1px solid #58a6ff55", color: "#58a6ff",
        fontSize: 15, fontWeight: 700, cursor: "pointer",
        letterSpacing: 1, fontFamily: "monospace", marginBottom: 20
      }}>🔄 실시간 글로벌 경제 뉴스 불러오기</button>
      {loading && <Spinner />}
      {fetched && !loading && news.map((n, i) => (
        <Card key={i} style={{ borderLeft: `3px solid ${sentColor[n.sentiment] || "#8b949e"}` }}>
          <div style={{ display: "flex", gap: 8, marginBottom: 6 }}>
            <Badge color="#58a6ff">{n.topic}</Badge>
            <span style={{ color: sentColor[n.sentiment], fontSize: 12 }}>{sentLabel[n.sentiment]}</span>
          </div>
          <p style={{ color: "#e6edf3", fontSize: 14, margin: "0 0 6px", fontWeight: 600 }}>{n.title}</p>
          <p style={{ color: "#8b949e", fontSize: 13, margin: 0, lineHeight: 1.6 }}>{n.summary}</p>
        </Card>
      ))}
    </div>
  );
}

// ── Main ──────────────────────────────────────────────────────────────────────
export default function App() {
  const [activeTab, setActiveTab] = useState(0);
  const tabs = [
    { icon: "🇺🇸", label: "미국 종목" },
    { icon: "🇰🇷", label: "한국 종목" },
    { icon: "💰", label: "분할 매수" },
    { icon: "🌍", label: "글로벌 뉴스" },
  ];

  return (
    <div style={{ minHeight: "100vh", background: "#010409", fontFamily: "'Noto Sans KR', -apple-system, sans-serif", color: "#e6edf3" }}>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;600;700;800&display=swap');
        * { box-sizing: border-box; }
        input::placeholder { color: #484f58; }
        @keyframes spin { to { transform: rotate(360deg); } }
        ::-webkit-scrollbar { width: 6px; height: 6px; }
        ::-webkit-scrollbar-track { background: #010409; }
        ::-webkit-scrollbar-thumb { background: #21262d; border-radius: 3px; }
      `}</style>

      <div style={{ background: "linear-gradient(180deg,#0d1117 0%,#010409 100%)", borderBottom: "1px solid #21262d", padding: "22px 24px 0" }}>
        <div style={{ maxWidth: 900, margin: "0 auto" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 20 }}>
            <div style={{ width: 36, height: 36, borderRadius: 8, background: "linear-gradient(135deg,#00ff9d,#00b4ff)", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 18 }}>🚨</div>
            <div>
              <h1 style={{ margin: 0, fontSize: 20, fontWeight: 800, letterSpacing: -0.5 }}>글로벌 스윙 알리미</h1>
              <p style={{ margin: 0, fontSize: 11, color: "#8b949e", fontFamily: "monospace" }}>SWING SCANNER V12.4 · SEC LIVE FILINGS</p>
            </div>
          </div>
          <div style={{ display: "flex", gap: 2 }}>
            {tabs.map((t, i) => (
              <button key={i} onClick={() => setActiveTab(i)} style={{
                padding: "10px 18px", border: "none", borderRadius: "6px 6px 0 0",
                background: activeTab === i ? "#0d1117" : "transparent",
                color: activeTab === i ? "#e6edf3" : "#8b949e",
                cursor: "pointer", fontSize: 13, fontWeight: activeTab === i ? 700 : 400,
                borderBottom: activeTab === i ? "2px solid #00ff9d" : "2px solid transparent"
              }}>{t.icon} {t.label}</button>
            ))}
          </div>
        </div>
      </div>

      <div style={{ maxWidth: 900, margin: "0 auto", padding: "24px" }}>
        {activeTab === 0 && <StockScanner market="US" />}
        {activeTab === 1 && <StockScanner market="KR" />}
        {activeTab === 2 && <SplitBuyCalc />}
        {activeTab === 3 && <WorldNews />}
      </div>
    </div>
  );
}
