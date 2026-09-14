/* Project Panthera — glossary page.
 * Renders glossary.json (emitted from config/glossary.yaml by
 * src/panthera_mvp/glossary.py) grouped into sections, with a client-side
 * filter. Every entry id is a stable URL fragment: the [data-term] affordances
 * on the ledger's table headers deep-link straight to glossary.html#<slug>.
 */
(function () {
  "use strict";
  const P = window.Panthera;
  const { esc, escAttr, mdInline } = P;

  function entryHtml(slug, t, terms) {
    const seeAlso = (t.see_also || []).filter((s) => terms[s]);
    return `<div class="gloss-entry" id="${escAttr(slug)}" data-slug="${escAttr(slug)}">
      <h3>${esc(t.label)}<span class="gloss-slug">#${esc(slug)}</span></h3>
      <p>${esc(t.short)}</p>
      ${t.long ? `<p class="gloss-long">${mdInline(t.long)}</p>` : ""}
      ${seeAlso.length ? `<p class="see-also">See also: ${seeAlso
        .map((s) => `<a href="#${escAttr(s)}">${esc(terms[s].label)}</a>`)
        .join(", ")}</p>` : ""}
    </div>`;
  }

  function render(data) {
    const terms = data.terms || {};
    const groups = data.groups || [];
    // A term whose group is missing from the render order would vanish
    // silently, so anything unplaced lands in a trailing "Other" section.
    const placed = new Set();
    let html = groups.map((g) => {
      const rows = Object.keys(terms)
        .filter((slug) => terms[slug].group === g.id)
        .sort((a, b) => terms[a].label.localeCompare(terms[b].label, undefined,
                                                     { sensitivity: "base" }));
      rows.forEach((s) => placed.add(s));
      if (!rows.length) return "";
      return `<section class="gloss-group" id="group-${escAttr(g.id)}">
        <h2>${esc(g.title)}</h2>
        ${rows.map((slug) => entryHtml(slug, terms[slug], terms)).join("")}
      </section>`;
    }).join("");
    const orphans = Object.keys(terms).filter((s) => !placed.has(s)).sort();
    if (orphans.length) {
      html += `<section class="gloss-group" id="group-other"><h2>Other</h2>
        ${orphans.map((slug) => entryHtml(slug, terms[slug], terms)).join("")}</section>`;
    }
    document.getElementById("gloss-body").innerHTML = html;
    // 94 terms is a long page; jump chips make each section reachable without
    // scrolling past the ones above it.
    const present = groups.filter((g) => document.getElementById(`group-${g.id}`));
    document.getElementById("gloss-jump").innerHTML = present
      .map((g) => `<a href="#group-${escAttr(g.id)}">${esc(g.title)}</a>`)
      .join("") + (orphans.length ? `<a href="#group-other">Other</a>` : "");
    return Object.keys(terms).length;
  }

  function wireFilter(total) {
    const input = document.getElementById("gloss-search");
    const status = document.getElementById("gloss-status");
    const entries = [...document.querySelectorAll(".gloss-entry")].map((el) => ({
      el, hay: (el.textContent || "").toLowerCase(),
    }));
    const groups = [...document.querySelectorAll(".gloss-group")];
    const paint = () => {
      const q = input.value.trim().toLowerCase();
      let shown = 0;
      entries.forEach(({ el, hay }) => {
        const hit = !q || hay.includes(q);
        el.hidden = !hit;
        if (hit) shown++;
      });
      // Hide a section whose every entry filtered out, heading included.
      groups.forEach((g) => {
        g.hidden = !g.querySelector(".gloss-entry:not([hidden])");
        const chip = document.querySelector(`#gloss-jump a[href="#${g.id}"]`);
        if (chip) chip.hidden = g.hidden;
      });
      status.textContent = q
        ? `${shown} of ${total} terms match “${input.value.trim()}”.`
        : `${total} terms.`;
    };
    input.addEventListener("input", paint);
    paint();
  }

  async function init() {
    P.initTheme();
    const data = await P.loadGlossary();
    if (!data.terms || !Object.keys(data.terms).length) {
      document.getElementById("gloss-status").textContent =
        "Failed to load glossary.json.";
      document.body.dataset.ready = "1";
      return;
    }
    const total = render(data);
    wireFilter(total);
    // Render happens after load, so the browser has already given up on the
    // incoming #fragment — scroll to it ourselves (scroll-margin-top in
    // app.css keeps it clear of the sticky nav).
    if (location.hash.length > 1) {
      const t = document.getElementById(decodeURIComponent(location.hash.slice(1)));
      if (t) t.scrollIntoView();
    }
    document.body.dataset.ready = "1";
  }

  document.addEventListener("DOMContentLoaded", init);
})();
