/* Project Panthera — calibration page.
 * Renders calibration_data.json (emitted by dashboard.py::build_calibration_data).
 * Extracted from calibration.html's inline <script>, which duplicated esc() and
 * the whole theme block from app.js; both now live in common.js.
 */
(function () {
  "use strict";
  const P = window.Panthera;
  const { esc, escAttr } = P;

  function statGrid(bp) {
    return `<h2>Chosen config</h2><div class="stat-grid">` +
      Object.keys(bp).map((k) => {
        // Sweep parameters that have a glossary entry get the affordance; the
        // rest are left bare rather than stamped data-term and reported as
        // missing by scripts/site_audit.py.
        const slug = String(k).toLowerCase();
        const attr = P.glossTerm(slug) ? ` data-term="${escAttr(slug)}"` : "";
        return `<div><div class="stat-label"${attr}>${esc(k)}</div>` +
          `<div class="stat-value stat-value-sm">${esc(bp[k])}</div></div>`;
      }).join("") + `</div>`;
  }

  function topConfigs(rows) {
    // responsive-stack + per-cell data-label: without them the "P/L (valid)"
    // column was simply clipped off the right edge at phone widths, with no
    // way to reach it.
    return `<h2 class="section-gap">Top configs by validation ROI</h2>
      <div class="table-scroll"><table class="responsive-stack">
        <thead><tr>
          <th data-term="config_id">Config</th>
          <th class="num" data-term="n_bets">N (valid)</th>
          <th class="num" data-term="roi_valid">ROI (valid)</th>
          <th class="num" data-term="profit_valid">P/L (valid)</th>
        </tr></thead>
        <tbody>${rows.map((c) => `
          <tr>
            <td data-label="Config"><code>${esc(c.config_id)}</code></td>
            <td class="num" data-label="N (valid)">${c.n_bets}</td>
            <td class="num" data-label="ROI (valid)">${c.roi_valid >= 0 ? "+" : ""}${c.roi_valid.toFixed(2)}%</td>
            <td class="num" data-label="P/L (valid)">$${c.profit_valid.toFixed(2)}</td>
          </tr>`).join("")}
        </tbody>
      </table></div>`;
  }

  async function init() {
    P.initTheme();
    let data;
    try {
      const [res] = await Promise.all([
        fetch("calibration_data.json", { cache: "no-store" }),
        P.loadGlossary(),
      ]);
      data = await res.json();
    } catch (e) {
      document.getElementById("cal-status").textContent =
        "Failed to load calibration_data.json";
      document.body.dataset.ready = "1";
      return;
    }
    const body = document.getElementById("calibration-body");
    if (!data.available) {
      body.innerHTML = `<p class="section-sub">No calibration sweep has been run yet ` +
        `(<code>panthera-mvp calibrate</code>).</p>`;
      document.body.dataset.ready = "1";
      return;
    }
    let html = "";
    if (data.best_params) html += statGrid(data.best_params);
    if (data.top_configs && data.top_configs.length) html += topConfigs(data.top_configs);
    document.getElementById("cal-status").remove();
    body.insertAdjacentHTML("beforeend", html);
    P.glossaryDecorate(document);
    document.body.dataset.ready = "1";
  }

  document.addEventListener("DOMContentLoaded", init);
})();
