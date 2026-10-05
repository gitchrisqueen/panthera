/* Project Panthera — Football page (football.html).
 * Renders ncaaf_data.json (dashboard.build_ncaaf_data): the college parlay
 * strategies, their tickets, qualifying legs by signal, and the decision log.
 * Same numbers as reports/NCAAF_REPORT.md (asserted in tests/test_dashboard.py).
 */
(function () {
  "use strict";

  const P = window.Panthera;
  const { esc, mdInline, icon } = P;

  function money(x) {
    if (x == null) return "—";
    const sign = x >= 0 ? "+" : "";
    return `$${sign}${x.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  }
  function pct(x, digits) {
    if (x == null) return "—";
    const sign = x >= 0 ? "+" : "";
    return `${sign}${x.toFixed(digits == null ? 1 : digits)}%`;
  }
  function price(x) {
    if (x == null) return "—";
    return `${x >= 0 ? "+" : ""}${Math.round(x)}`;
  }
  function record(r) {
    return r ? `${r.wins}-${r.losses}-${r.pushes}` : "—";
  }
  function legLabel(lg) {
    if (lg.market === "spread") return `${lg.selection} ${lg.line >= 0 ? "+" : ""}${lg.line}`;
    if (lg.market === "moneyline") return `${lg.selection} ML`;
    return `${lg.selection} ${lg.line == null ? "" : lg.line}`;
  }
  function emptyRow(cols, text) {
    return `<tr><td colspan="${cols}" data-label=""><p class="empty-note">${esc(text)}</p></td></tr>`;
  }

  function renderFreshness(data) {
    const el = document.getElementById("freshness-badge");
    const gen = new Date(data.generated_at_utc);
    const when = gen.toLocaleString(undefined, {
      month: "short", day: "numeric", hour: "numeric", minute: "2-digit", timeZoneName: "short",
    });
    el.dataset.stale = String((Date.now() - gen.getTime()) / 36e5 > 30);
    el.innerHTML = `<span class="dot"></span><span>Last updated ${esc(when)}</span>`;
  }

  function strategyCard(s) {
    const t = s.tickets;
    const segs = (s.screen_segments || []).map((g) => `
      <div class="callout" style="border-color:var(--border);background:var(--bg-sunken);color:var(--fg-muted);">
        ${icon("eye")}<span><strong>SCREEN segment</strong> <code>${esc(g.config_hash)}</code> — outside the
        registered lineage, descriptive only. ${g.n} ticket${g.n === 1 ? "" : "s"}, ${record(g.record)}, P/L ${money(g.profit)}.</span>
      </div>`).join("");
    const checkpoints = (s.screen.checkpoints || []).join(", ");
    return `<article class="strategy-card" id="strategy-${esc(s.id)}">
      <div class="strategy-card-head">
        <h3>${esc(s.id)} <span style="color:var(--fg-faint);font-weight:400;font-size:13px;">· ${esc(s.kind)}${s.enabled ? "" : " · disabled"}</span></h3>
        <span style="font-size:12px;color:var(--fg-faint);">${s.registered_at ? "registered " + esc(s.registered_at) : ""}</span>
      </div>
      ${s.hypothesis ? `<p class="hypothesis">${mdInline(s.hypothesis)}</p>` : ""}
      <div class="verdict-line">${P.glossBadge("tier_screen", "badge-screen", `${icon("eye")}SCREEN`)}
        <span class="verdict-text">Descriptive only — no profit threshold is tested.${checkpoints ? ` Checkpoints at ${esc(checkpoints)} tickets.` : ""}</span></div>
      ${segs}
      ${t.n ? `<div class="stat-grid">
        <div><div class="stat-label">Tickets</div><div class="stat-value">${t.n}</div></div>
        <div><div class="stat-label">Record</div><div class="stat-value">${record(t.record)}</div></div>
        <div><div class="stat-label">P/L</div><div class="stat-value">${money(t.profit)}</div></div>
        <div><div class="stat-label">ROI</div><div class="stat-value">${pct(t.roi)}</div></div>
        <div><div class="stat-label">Pending</div><div class="stat-value">${t.pending}</div></div>
      </div>` : `<p class="section-sub">No tickets yet.</p>`}
      <div style="font-size:12px;color:var(--fg-faint);">config hash: ${s.hash_lineage.map((h) => `<code>${esc(h)}</code>`).join(", ") || "none"}</div>
    </article>`;
  }

  function renderStrategies(data) {
    const el = document.getElementById("strategy-cards");
    el.innerHTML = data.strategies.length
      ? data.strategies.map(strategyCard).join("")
      : `<p class="empty-note">No college football strategy is registered.</p>`;
  }

  function renderTickets(data) {
    const tbody = document.getElementById("tickets-tbody");
    if (!data.tickets.length) {
      tbody.innerHTML = emptyRow(5, "No tickets yet. The first decision is on the next game day.");
      return;
    }
    tbody.innerHTML = data.tickets.map((t) => `
      <tr>
        <td data-label="Date">${esc(t.game_date_et)}</td>
        <td data-label="Legs"><ul class="ticket-legs">${t.legs.map((lg) =>
          `<li><span class="status-dot ${esc(lg.status)}"></span>${esc(legLabel(lg))}</li>`).join("")}</ul></td>
        <td data-label="Price" class="num">${price(t.price_american)}</td>
        <td data-label="Status">${P.statusCell(t.status)}</td>
        <td data-label="P/L" class="num">${money(t.profit)}</td>
      </tr>`).join("");
  }

  function renderSignals(data) {
    const rows = data.strategies.flatMap((s) => s.signals);
    const tbody = document.getElementById("signals-tbody");
    if (!rows.length) {
      tbody.innerHTML = emptyRow(5, "No qualifying legs yet.");
      return;
    }
    tbody.innerHTML = rows.map((r) => `
      <tr>
        <td data-label="Signal"><a class="signal-link" href="${P.glossHref("signal_" + r.signal.toLowerCase())}">${esc(r.signal)}</a></td>
        <td data-label="Legs" class="num">${r.legs}</td>
        <td data-label="Record">${record(r.record)}</td>
        <td data-label="Win %" class="num">${r.win_pct == null ? "—" : r.win_pct.toFixed(1) + "%"}</td>
        <td data-label="vs 52.4%" class="num">${r.vs_breakeven == null ? "—" : pct(r.vs_breakeven).replace("%", " pts")}</td>
      </tr>`).join("");
  }

  function renderDecisions(data) {
    const recent = data.strategies.flatMap((s) => s.decisions.recent)
      .sort((a, b) => b.game_date_et.localeCompare(a.game_date_et));
    const counts = {};
    data.strategies.forEach((s) => Object.entries(s.decisions.counts)
      .forEach(([k, v]) => { counts[k] = (counts[k] || 0) + v; }));
    const summary = Object.entries(counts).map(([k, v]) => `${k}: ${v}`).join(", ");
    if (summary) {
      document.getElementById("decisions-sub").textContent += ` So far: ${summary}.`;
    }
    const tbody = document.getElementById("decisions-tbody");
    tbody.innerHTML = recent.length
      ? recent.map((d) => `
        <tr>
          <td data-label="Date">${esc(d.game_date_et)}</td>
          <td data-label="Decision">${esc(d.status)}</td>
          <td data-label="Reason">${esc(d.reason || "")}</td>
        </tr>`).join("")
      : emptyRow(3, "No decisions yet.");
  }

  async function init() {
    P.initTheme();
    P.renderSportTabs("football");
    let data;
    try {
      const [res] = await Promise.all([
        fetch("ncaaf_data.json", { cache: "no-store" }),
        P.loadGlossary(),
      ]);
      data = await res.json();
    } catch (e) {
      document.getElementById("freshness-badge").textContent = "Failed to load ncaaf_data.json";
      document.body.dataset.ready = "1";
      return;
    }
    P.levelChips("football");
    renderFreshness(data);
    renderStrategies(data);
    renderTickets(data);
    renderSignals(data);
    renderDecisions(data);
    P.wireNavOverflow();
    P.glossaryDecorate(document);
    // Readiness hook for scripts/site_audit.py.
    document.body.dataset.ready = "1";
  }

  document.addEventListener("DOMContentLoaded", init);
})();
