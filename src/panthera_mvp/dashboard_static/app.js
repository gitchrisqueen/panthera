/* Project Panthera — public dashboard client.
 * Vanilla JS, no framework, no build step. Fetches site_data.json (emitted
 * by `panthera-mvp pages` / src/panthera_mvp/dashboard.py) and renders
 * everything client-side. The one rule this file must never violate:
 * retroactive_replay data stays in its own section — it is never merged
 * into the comparison table, strategy cards, ledger, or portfolio strip.
 */
(function () {
  "use strict";

  const GRADED = new Set(["win", "loss", "push", "void"]);
  const ICON_SPRITE = "static/icons.svg";

  // ---------------------------------------------------------------- utils
  function esc(s) {
    const d = document.createElement("div");
    d.textContent = s == null ? "" : String(s);
    return d.innerHTML;
  }
  function money(x) {
    if (x == null) return "—";
    const sign = x >= 0 ? "+" : "";
    return `$${sign}${x.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  }
  function pct(x, digits) {
    if (x == null) return "—";
    const sign = x >= 0 ? "+" : "";
    return `${sign}${x.toFixed(digits == null ? 2 : digits)}%`;
  }
  function price(x) {
    if (x == null) return "—";
    const sign = x >= 0 ? "+" : "";
    return `${sign}${Math.round(x)}`;
  }
  function icon(name, cls) {
    return `<svg class="icon ${cls || ""}"><use href="${ICON_SPRITE}#icon-${name}"/></svg>`;
  }
  function cssVar(name) {
    return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  }
  const STRATEGY_COLOR_VAR = {
    fav_ml: "--clr-fav_ml", pv_orig: "--clr-pv_orig", pv_v2: "--clr-pv_v2",
    pv_v3: "--clr-pv_v3", dog_ml: "--clr-dog_ml", sharp_split: "--clr-sharp_split",
    fade_public: "--clr-fade_public",
  };
  function strategyColor(sid) {
    return cssVar(STRATEGY_COLOR_VAR[sid] || "--clr-default");
  }
  function pickLabel(row) {
    if (row.market === "ml") return `${row.selection} ML`;
    if (row.market === "rl") return `${row.selection} ${row.line >= 0 ? "+" : ""}${row.line}`;
    return `${row.selection} ${row.line == null ? "" : row.line}`;
  }

  // --------------------------------------------------------------- theme
  function currentIsDark() {
    const t = document.documentElement.getAttribute("data-theme");
    if (t) return t === "dark";
    return window.matchMedia("(prefers-color-scheme: dark)").matches;
  }
  function initTheme() {
    const saved = localStorage.getItem("panthera-theme");
    if (saved) document.documentElement.setAttribute("data-theme", saved);
    const btn = document.getElementById("theme-toggle");
    const paint = () => {
      const dark = currentIsDark();
      btn.innerHTML = `${icon(dark ? "sun" : "moon")} ${dark ? "Light" : "Dark"}`;
    };
    paint();
    btn.addEventListener("click", () => {
      const next = currentIsDark() ? "light" : "dark";
      document.documentElement.setAttribute("data-theme", next);
      localStorage.setItem("panthera-theme", next);
      paint();
      renderCharts(window.__panthera.data); // colors read from CSS vars, dark swap needs a repaint
    });
  }

  // ----------------------------------------------------------- freshness
  function renderFreshness(data) {
    const el = document.getElementById("freshness-badge");
    const gen = new Date(data.generated_at_utc);
    const label = { morning: "morning run", pregame: "pregame run", manual: "manual build" }[data.generated_by_run] || data.generated_by_run;
    const ageHours = (Date.now() - gen.getTime()) / 36e5;
    const stale = ageHours > 20;
    el.dataset.stale = String(stale);
    const when = gen.toLocaleString(undefined, {
      month: "short", day: "numeric", hour: "numeric", minute: "2-digit", timeZoneName: "short",
    });
    el.innerHTML = `<span class="dot"></span><span>${stale ? "Data may be stale — " : "Last updated "}${esc(when)} · ${esc(label)}</span>`;
  }

  // --------------------------------------------------------- verdict/tier
  function verdictBadge(strategy) {
    const seg = strategy.verdict_segment;
    if (!seg) {
      return `<span class="badge badge-screen">${icon("eye")}SCREEN</span>`;
    }
    if (seg.n_graded < seg.min_graded) {
      const frozen = !strategy.enabled;
      return frozen
        ? `<span class="badge badge-frozen" title="Segment closed by design (superseded strategy) — will not reach its threshold">${icon("pause")}COLLECTING — closed</span>`
        : `<span class="badge badge-collecting">${icon("hourglass")}COLLECTING ${seg.n_graded}/${seg.min_graded}</span>`;
    }
    if (seg.roi > seg.supported_roi) return `<span class="badge badge-supported">${icon("check-circle")}SUPPORTED</span>`;
    if (seg.roi < seg.falsified_roi) return `<span class="badge badge-falsified">${icon("x-circle")}FALSIFIED</span>`;
    return `<span class="badge badge-collecting">${icon("hourglass")}INCONCLUSIVE</span>`;
  }
  function tierBadgeSmall(kind) {
    return kind === "verdict"
      ? `<span class="tier-tag">VERDICT</span>`
      : `<span class="badge badge-screen" style="padding:1px 7px;">${icon("eye")}SCREEN</span>`;
  }

  // ------------------------------------------------------- comparison tbl
  let compareSort = null;
  function renderComparison(data) {
    const tbody = document.getElementById("comparison-tbody");
    const rows = data.strategies.slice();
    if (compareSort) {
      const { key, dir } = compareSort;
      rows.sort((a, b) => ((a[key] ?? -Infinity) - (b[key] ?? -Infinity)) * dir);
    }
    tbody.innerHTML = rows.map((s) => {
      const record = s.record ? `${s.record.wins}-${s.record.losses}-${s.record.pushes}` : "—";
      const roiTxt = s.roi == null ? "—" : `${pct(s.roi)}${s.roi_se != null ? ` <span class="num" style="color:var(--fg-faint);font-size:12px;">±${s.roi_se}</span>` : ""}`;
      return `<tr data-strategy="${esc(s.id)}" style="--row-accent:${strategyColor(s.id)}">
        <td data-label="Strategy"><a href="#strategy-${esc(s.id)}"><strong>${esc(s.id)}</strong></a></td>
        <td data-label="Kind">${esc(s.kind)}</td>
        <td data-label="Graded" class="num">${s.graded_n || 0}</td>
        <td data-label="Record">${record}</td>
        <td data-label="P/L" class="num">${money(s.profit)}</td>
        <td data-label="ROI (±SE)" class="num">${roiTxt}</td>
        <td data-label="Avg CLV">${esc(s.clv)}</td>
        <td data-label="Overlap" class="num">${esc(s.overlap_pct)}</td>
        <td data-label="Pending" class="num">${s.pending}</td>
        <td data-label="Status">${esc(s.status_short)}</td>
      </tr>`;
    }).join("");
  }
  function wireComparisonSort() {
    document.querySelectorAll("#comparison-table th[data-sortable]").forEach((th) => {
      th.addEventListener("click", () => {
        const key = th.dataset.key;
        const dir = compareSort && compareSort.key === key && compareSort.dir === -1 ? 1 : -1;
        compareSort = { key, dir };
        renderComparison(window.__panthera.data);
      });
    });
  }

  // ------------------------------------------------------- strategy cards
  function breakdownTable(title, rows) {
    if (!rows || !rows.length) return "";
    return `<div><h4>${esc(title)}</h4><table><tbody>${rows.map((r) => `
      <tr><td>${esc(r.key)}</td><td>${r.record.wins}-${r.record.losses}-${r.record.pushes}</td>
      <td class="num">${money(r.profit)}</td><td class="num">${pct(r.roi)}</td></tr>`).join("")}
      </tbody></table></div>`;
  }
  function strategyCard(s) {
    const seg = s.verdict_segment;
    let verdictBlock = "";
    if (seg) {
      const frozen = !s.enabled && seg.n_graded < seg.min_graded;
      const frac = Math.min(100, (seg.n_graded / Math.max(seg.min_graded, 1)) * 100);
      verdictBlock = `
        <div class="verdict-line">${verdictBadge(s)} <span style="color:var(--fg-muted);font-size:13px;">${esc(seg.verdict_text)}</span></div>
        <div class="progress" data-frozen="${frozen}"><span style="width:${frac}%"></span></div>
        <div style="font-size:12px;color:var(--fg-faint);margin-top:4px;">config hash${seg.config_hashes.length === 1 ? "" : "es"}: ${seg.config_hashes.map((h) => `<code>${esc(h)}</code>`).join(", ") || "all"}</div>`;
    } else {
      verdictBlock = `<div class="verdict-line">${verdictBadge(s)} <span style="color:var(--fg-muted);font-size:13px;">Descriptive only — no threshold is tested.</span></div>`;
    }
    const screenBlocks = (s.screen_segments || []).map((seg2) => `
      <div class="callout" style="border-color:var(--border);background:var(--bg-sunken);color:var(--fg-muted);">
        ${icon("eye")}<span><strong>SCREEN segment</strong> <code>${esc(seg2.config_hash)}</code> — descriptive only, no inferential weight.
        ${seg2.record ? ` Record ${seg2.record.wins}-${seg2.record.losses}-${seg2.record.pushes}, P/L ${money(seg2.profit)}, ROI ${pct(seg2.roi)} (${seg2.n_graded} graded).` : " No graded picks yet."}
        ${seg2.checkpoints_reached.length ? ` Checkpoints reached: ${seg2.checkpoints_reached.join(", ")}.` : ""}</span>
      </div>`).join("");
    const b = s.breakdowns || {};
    return `<article class="strategy-card" id="strategy-${esc(s.id)}">
      <div class="strategy-card-head">
        <h3><span class="strategy-dot" style="--dot-color:${strategyColor(s.id)}"></span>${esc(s.id)} <span style="color:var(--fg-faint);font-weight:400;font-size:13px;">· ${esc(s.kind)}</span></h3>
        <span style="font-size:12px;color:var(--fg-faint);">${s.registered_at ? "registered " + esc(s.registered_at) : ""}</span>
      </div>
      ${s.hypothesis ? `<p class="hypothesis">${esc(s.hypothesis)}</p>` : ""}
      ${verdictBlock}
      ${screenBlocks}
      ${s.graded_n ? `<div class="stat-grid">
        <div><div class="stat-label">Record</div><div class="stat-value">${s.record.wins}-${s.record.losses}-${s.record.pushes}</div></div>
        <div><div class="stat-label">P/L</div><div class="stat-value">${money(s.profit)}</div></div>
        <div><div class="stat-label">ROI</div><div class="stat-value">${pct(s.roi)}</div></div>
        <div><div class="stat-label">Pending</div><div class="stat-value">${s.pending}</div></div>
        <div><div class="stat-label">Avg CLV</div><div class="stat-value" style="font-size:13px;">${esc(s.clv)}</div></div>
      </div>` : `<p class="section-sub">No graded picks yet (${s.pending} pending).</p>`}
      ${(b.by_rule || b.by_day_type) ? `<div class="breakdowns">
        ${breakdownTable("By rule", b.by_rule)}
        ${breakdownTable("By day type", b.by_day_type)}
        ${breakdownTable("By slot", b.by_slot)}
        ${breakdownTable("By market", b.by_market)}
      </div>` : ""}
    </article>`;
  }
  function renderStrategyCards(data) {
    document.getElementById("strategy-cards").innerHTML = data.strategies.map(strategyCard).join("");
  }

  // ------------------------------------------------------------- today
  function renderToday(data) {
    const rows = data.picks_history;
    if (!rows.length) {
      document.getElementById("today-sub").textContent = "No picks recorded yet.";
      return;
    }
    const latestDate = rows.reduce((m, r) => (r.game_date_et > m ? r.game_date_et : m), rows[0].game_date_et);
    const todays = rows.filter((r) => r.game_date_et === latestDate).sort((a, b) => (a.start_time_et || "").localeCompare(b.start_time_et || ""));
    document.getElementById("today-sub").textContent = `Most recent slate on file: ${latestDate} (${todays.length} pick${todays.length === 1 ? "" : "s"}).`;
    document.getElementById("today-tbody").innerHTML = todays.map((r) => `
      <tr>
        <td data-label="Strategy">${esc(r.strategy_id)}</td>
        <td data-label="Start (ET)">${esc(r.start_time_et)}</td>
        <td data-label="Matchup">${esc(r.matchup)}</td>
        <td data-label="Pick">${esc(pickLabel(r))}</td>
        <td data-label="Price" class="num">${price(r.price_american)}</td>
        <td data-label="Status"><span class="status-dot ${esc(r.status)}"></span>${esc(r.status)}</td>
      </tr>`).join("");
  }

  // ------------------------------------------------------------- ledger
  const LEDGER_PAGE_SIZE = 50;
  let ledgerState = { strategies: new Set(), status: "", search: "", from: "", to: "", sort: { key: "game_date_et", dir: -1 }, page: 0 };

  function ledgerFiltered(data) {
    let rows = data.picks_history;
    if (ledgerState.strategies.size) rows = rows.filter((r) => ledgerState.strategies.has(r.strategy_id));
    if (ledgerState.status) rows = rows.filter((r) => r.status === ledgerState.status);
    if (ledgerState.search) {
      const q = ledgerState.search.toLowerCase();
      rows = rows.filter((r) => r.matchup.toLowerCase().includes(q));
    }
    if (ledgerState.from) rows = rows.filter((r) => r.game_date_et >= ledgerState.from);
    if (ledgerState.to) rows = rows.filter((r) => r.game_date_et <= ledgerState.to);
    const { key, dir } = ledgerState.sort;
    rows = rows.slice().sort((a, b) => {
      const av = a[key], bv = b[key];
      if (av == null && bv == null) return 0;
      if (av == null) return 1;
      if (bv == null) return -1;
      return av > bv ? dir : av < bv ? -dir : 0;
    });
    return rows;
  }
  function renderLedgerChips(data) {
    const ids = data.strategies.map((s) => s.id);
    document.getElementById("ledger-strategy-chips").innerHTML = ids.map((id) => `
      <button type="button" class="chip" data-sid="${esc(id)}" style="--chip-color:${strategyColor(id)};color:${strategyColor(id)};" aria-pressed="false">
        <span class="swatch"></span>${esc(id)}</button>`).join("");
    document.querySelectorAll("#ledger-strategy-chips .chip").forEach((chip) => {
      chip.addEventListener("click", () => {
        const sid = chip.dataset.sid;
        if (ledgerState.strategies.has(sid)) { ledgerState.strategies.delete(sid); chip.setAttribute("aria-pressed", "false"); chip.style.color = strategyColor(sid); }
        else { ledgerState.strategies.add(sid); chip.setAttribute("aria-pressed", "true"); chip.style.color = ""; }
        ledgerState.page = 0;
        renderLedger(window.__panthera.data);
      });
    });
  }
  function renderLedger(data) {
    const filtered = ledgerFiltered(data);
    const pages = Math.max(1, Math.ceil(filtered.length / LEDGER_PAGE_SIZE));
    ledgerState.page = Math.min(ledgerState.page, pages - 1);
    const start = ledgerState.page * LEDGER_PAGE_SIZE;
    const pageRows = filtered.slice(start, start + LEDGER_PAGE_SIZE);
    document.getElementById("ledger-tbody").innerHTML = pageRows.length ? pageRows.map((r) => `
      <tr>
        <td data-label="Date">${esc(r.game_date_et)}</td>
        <td data-label="Strategy" style="color:${strategyColor(r.strategy_id)};font-weight:600;">${esc(r.strategy_id)}</td>
        <td data-label="Matchup">${esc(r.matchup)}</td>
        <td data-label="Pick">${esc(pickLabel(r))}</td>
        <td data-label="Price" class="num">${price(r.price_american)}</td>
        <td data-label="Status"><span class="status-dot ${esc(r.status)}"></span>${esc(r.status)}</td>
        <td data-label="P/L" class="num">${money(r.profit)}</td>
        <td data-label="CLV" class="num">${r.clv_cents == null ? "—" : `${r.clv_cents >= 0 ? "+" : ""}${r.clv_cents.toFixed(1)}c`}</td>
        <td data-label="Tier">${tierBadgeSmall(r.segment_kind)}</td>
      </tr>`).join("") : `<tr><td colspan="9" class="empty-note">No picks match these filters.</td></tr>`;
    document.getElementById("ledger-pagination").innerHTML = `
      <button ${ledgerState.page === 0 ? "disabled" : ""} data-nav="prev">← Prev</button>
      <span>Page ${ledgerState.page + 1} of ${pages} · ${filtered.length} pick${filtered.length === 1 ? "" : "s"}</span>
      <button ${ledgerState.page >= pages - 1 ? "disabled" : ""} data-nav="next">Next →</button>`;
    document.getElementById("ledger-pagination").querySelectorAll("button").forEach((b) => {
      b.addEventListener("click", () => { ledgerState.page += b.dataset.nav === "prev" ? -1 : 1; renderLedger(data); });
    });
  }
  function wireLedgerControls(data) {
    document.getElementById("ledger-status-filter").addEventListener("change", (e) => { ledgerState.status = e.target.value; ledgerState.page = 0; renderLedger(data); });
    document.getElementById("ledger-search").addEventListener("input", (e) => { ledgerState.search = e.target.value; ledgerState.page = 0; renderLedger(data); });
    document.getElementById("ledger-date-from").addEventListener("change", (e) => { ledgerState.from = e.target.value; ledgerState.page = 0; renderLedger(data); });
    document.getElementById("ledger-date-to").addEventListener("change", (e) => { ledgerState.to = e.target.value; ledgerState.page = 0; renderLedger(data); });
    document.querySelectorAll("#ledger-table th[data-sortable]").forEach((th) => {
      th.addEventListener("click", () => {
        const key = th.dataset.key;
        const dir = ledgerState.sort.key === key && ledgerState.sort.dir === -1 ? 1 : -1;
        ledgerState.sort = { key, dir };
        renderLedger(data);
      });
    });
  }

  // ------------------------------------------------------------- charts
  function svgWrap(inner, w, h) {
    return `<svg viewBox="0 0 ${w} ${h}" width="100%" height="${h}" role="img">${inner}</svg>`;
  }
  function renderCumulativeChart(data) {
    const W = 560, H = 220, PAD = 34;
    const series = data.strategies.map((s) => {
      const rows = data.picks_history
        .filter((r) => r.strategy_id === s.id && GRADED.has(r.status) && r.profit != null)
        .slice()
        .sort((a, b) => (a.settled_ts_utc || a.game_date_et).localeCompare(b.settled_ts_utc || b.game_date_et));
      let cum = 0;
      const points = rows.map((r) => { cum += r.profit; return { t: r.settled_ts_utc || r.game_date_et, y: cum }; });
      return { sid: s.id, dashed: !s.verdict_segment, points };
    }).filter((s) => s.points.length > 0);

    const host = document.getElementById("chart-cumulative");
    if (!series.length) { host.innerHTML = `<p class="empty-note">Not enough graded picks yet.</p>`; return; }

    const allY = series.flatMap((s) => s.points.map((p) => p.y)).concat([0]);
    const yMin = Math.min(...allY), yMax = Math.max(...allY);
    const yRange = yMax - yMin || 1;
    const maxLen = Math.max(...series.map((s) => s.points.length));
    const xFor = (i, n) => PAD + (n > 1 ? (i / (n - 1)) * (W - 2 * PAD) : 0);
    const yFor = (y) => H - PAD - ((y - yMin) / yRange) * (H - 2 * PAD);

    let inner = `<line x1="${PAD}" y1="${yFor(0)}" x2="${W - PAD}" y2="${yFor(0)}" stroke="var(--border-strong)" stroke-dasharray="2,3"/>`;
    series.forEach((s) => {
      const n = s.points.length;
      const d = s.points.map((p, i) => `${i === 0 ? "M" : "L"}${xFor(i, n).toFixed(1)},${yFor(p.y).toFixed(1)}`).join(" ");
      inner += `<path d="${d}" fill="none" stroke="${strategyColor(s.sid)}" stroke-width="2" ${s.dashed ? 'stroke-dasharray="6,4"' : ""}/>`;
    });
    host.innerHTML = svgWrap(inner, W, H) + `<div class="chart-legend">${series.map((s) => `
      <span class="item"><span class="swatch ${s.dashed ? "dashed" : ""}" style="background-color:${strategyColor(s.sid)};color:${strategyColor(s.sid)};"></span>${esc(s.sid)}</span>`).join("")}</div>`;
  }
  function renderClvChart(data) {
    const host = document.getElementById("chart-clv");
    const rowsBySid = data.strategies.map((s) => ({
      sid: s.id,
      points: data.picks_history.filter((r) => r.strategy_id === s.id && r.clv_cents != null).map((r) => r.clv_cents),
    })).filter((s) => data.strategies.find((x) => x.id === s.sid));
    if (!rowsBySid.some((r) => r.points.length)) { host.innerHTML = `<p class="empty-note">Not enough graded picks yet.</p>`; return; }
    const all = rowsBySid.flatMap((r) => r.points);
    const xMax = Math.max(1, ...all.map(Math.abs));
    const W = 560, PAD = 34, ROW_H = 30;
    const H = PAD + rowsBySid.length * ROW_H + 10;
    const xFor = (v) => W / 2 + (v / xMax) * (W / 2 - PAD);
    let inner = `<line x1="${W / 2}" y1="4" x2="${W / 2}" y2="${H - 4}" stroke="var(--border-strong)"/>`;
    rowsBySid.forEach((r, i) => {
      const y = PAD / 2 + i * ROW_H + ROW_H / 2;
      const n = r.points.length;
      const pos = n ? Math.round((100 * r.points.filter((v) => v > 0).length) / n) : 0;
      inner += `<text x="4" y="${y + 4}" font-size="11" fill="var(--fg-muted)">${esc(r.sid)}</text>`;
      r.points.forEach((v) => { inner += `<circle cx="${xFor(v).toFixed(1)}" cy="${y}" r="3.5" fill="${strategyColor(r.sid)}" opacity="0.75"/>`; });
      inner += `<text x="${W - 4}" y="${y + 4}" font-size="10.5" fill="var(--fg-faint)" text-anchor="end">n=${n}, ${pos}% pos</text>`;
    });
    host.innerHTML = svgWrap(inner, W, H);
  }
  function renderCharts(data) { renderCumulativeChart(data); renderClvChart(data); }

  // ------------------------------------------------------------- replay
  function renderReplay(data) {
    const r = data.retroactive_replay;
    document.querySelector("#replay-banner span:last-child").textContent = r.banner;
    if (!r.strategies.length) {
      document.getElementById("replay-body").innerHTML = `<p class="section-sub">No retroactive replays on file.</p>`;
      return;
    }
    document.getElementById("replay-body").innerHTML = r.strategies.map((s) => `
      <article class="strategy-card">
        <h3 style="margin:0 0 8px;">${esc(s.id)} <span style="font-weight:400;color:var(--fg-faint);font-size:13px;">(retroactive)</span></h3>
        ${s.graded_n ? `<p>Record ${s.record.wins}-${s.record.losses}-${s.record.pushes}, P/L ${money(s.profit)}, ROI ${pct(s.roi)} (${s.graded_n} graded, descriptive only).</p>
          <div class="breakdowns">${breakdownTable("By rule", s.by_rule)}</div>`
        : `<p class="section-sub">${s.n_picks} pick(s), none graded yet.</p>`}
      </article>`).join("");
  }

  // ----------------------------------------------------------- portfolio
  function renderPortfolio(data) {
    const p = data.portfolio_totals;
    const el = document.getElementById("portfolio-strip");
    if (!p) { el.textContent = "No graded picks yet."; return; }
    el.innerHTML = `<strong>Portfolio (all strategies): </strong>${money(p.profit)} on $${p.risked.toLocaleString()} risked (${pct(p.roi)}). ${esc(p.note)}`;
  }

  // ----------------------------------------------------------- how-to-read
  function renderHowToRead(data) {
    document.getElementById("how-to-read-text").textContent = data.how_to_read.replace(/\*\*/g, "").replace(/\n/g, " ");
  }

  // --------------------------------------------------------------- init
  async function init() {
    initTheme();
    let data;
    try {
      const res = await fetch("site_data.json", { cache: "no-store" });
      data = await res.json();
    } catch (e) {
      document.getElementById("freshness-badge").textContent = "Failed to load site_data.json";
      return;
    }
    window.__panthera = { data };
    renderFreshness(data);
    renderHowToRead(data);
    renderComparison(data);
    wireComparisonSort();
    renderStrategyCards(data);
    renderToday(data);
    renderLedgerChips(data);
    wireLedgerControls(data);
    renderLedger(data);
    renderCharts(data);
    renderReplay(data);
    renderPortfolio(data);
  }

  document.addEventListener("DOMContentLoaded", init);
})();
