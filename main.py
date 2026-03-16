
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

