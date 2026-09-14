/* Project Panthera — shared dashboard runtime (window.Panthera).
 *
 * Loaded first by every page (index, calibration, glossary). Holds the things
 * all three need: escaping, the theme toggle, and the glossary runtime that
 * attaches a definition to every [data-term] in the document.
 *
 * `panthera-mvp pages` copies dashboard_static/ wholesale, so a new file under
 * static/ ships with no Python change — only new top-level HTML pages have to
 * be added to write_site()'s move list.
 */
(function () {
  "use strict";

  // ------------------------------------------------------------- escaping
  function esc(s) {
    const d = document.createElement("div");
    d.textContent = s == null ? "" : String(s);
    return d.innerHTML;
  }

  /* esc() round-trips through textContent -> innerHTML, so it only escapes
     & < >. A quote inside a glossary definition would break straight out of a
     title="..." attribute, so attribute sinks need this instead. */
  function escAttr(s) {
    return esc(s).replace(/"/g, "&quot;").replace(/'/g, "&#39;");
  }

  /* report.py writes **bold** into verdict text, hypotheses and HOW_TO_READ on
     purpose. mdStrip flattens it for plain-text sinks (title=, textContent);
     mdInline renders it. */
  function mdStrip(s) {
    return String(s == null ? "" : s)
      .replace(/\*\*(.+?)\*\*/g, "$1").replace(/\*\*/g, "").replace(/`/g, "");
  }

  /* esc() runs FIRST, so the only tags in the output are the <strong>s added
     here. This is not a general markdown renderer and must never be handed
     un-escaped input. */
  function mdInline(s) {
    return esc(s == null ? "" : String(s))
      .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
      .replace(/`([^`]+)`/g, "<code>$1</code>");
  }

  function icon(name, cls) {
    return `<svg class="icon ${cls || ""}"><use href="static/icons.svg#icon-${name}"/></svg>`;
  }
  function cssVar(name) {
    return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  }

  // ---------------------------------------------------------------- theme
  function currentIsDark() {
    const t = document.documentElement.getAttribute("data-theme");
    if (t) return t === "dark";
    return window.matchMedia("(prefers-color-scheme: dark)").matches;
  }
  function initTheme(onChange) {
    let saved = null;
    try { saved = localStorage.getItem("panthera-theme"); } catch (e) { /* private mode */ }
    if (saved) document.documentElement.setAttribute("data-theme", saved);
    const btn = document.getElementById("theme-toggle");
    if (!btn) return;
    const paint = () => {
      const dark = currentIsDark();
      btn.innerHTML = `${icon(dark ? "sun" : "moon")} ${dark ? "Light" : "Dark"}`;
    };
    paint();
    btn.addEventListener("click", () => {
      const next = currentIsDark() ? "light" : "dark";
      document.documentElement.setAttribute("data-theme", next);
      try { localStorage.setItem("panthera-theme", next); } catch (e) { /* ignore */ }
      paint();
      if (typeof onChange === "function") onChange(next);
    });
  }

  // ------------------------------------------------------------- glossary
  let GLOSSARY = { terms: {}, groups: [] };

  async function loadGlossary() {
    try {
      const res = await fetch("glossary.json", { cache: "no-store" });
      GLOSSARY = await res.json();
    } catch (e) {
      GLOSSARY = { terms: {}, groups: [] };
    }
    return GLOSSARY;
  }
  function glossary() { return GLOSSARY; }
  function glossTerm(slug) {
    return (GLOSSARY.terms && GLOSSARY.terms[slug]) || null;
  }
  function glossHref(slug) {
    return `glossary.html#${encodeURIComponent(slug)}`;
  }

  /* Attaches the info affordance to every [data-term]: title= is the short
     definition, href deep-links to the full entry.
     An unknown slug is left marked data-gloss="missing" rather than skipped
     silently — scripts/site_audit.py asserts that selector is empty, so a
     renamed column can never quietly lose its definition.
     Idempotent via :not([data-gloss]), so it is safe to call after any
     re-render. */
  function glossaryDecorate(root) {
    (root || document).querySelectorAll("[data-term]:not([data-gloss])").forEach((el) => {
      const slug = el.dataset.term;
      const t = glossTerm(slug);
      el.dataset.gloss = t ? "1" : "missing";
      if (!t) return;
      const tip = escAttr(`${t.label} — ${mdStrip(t.short)}`);
      const aria = escAttr(`What is ${t.label}? Opens the glossary`);
      el.insertAdjacentHTML(
        "beforeend",
        `<a class="gloss-link" href="${glossHref(slug)}" title="${tip}" aria-label="${aria}">` +
          `${icon("info")}</a>`
      );
    });
  }

  /* Badges link as a whole rather than growing a 24px affordance inside a
     pill — the badge itself is the better tap target. */
  function glossBadge(slug, cls, inner) {
    const t = glossTerm(slug);
    if (!t) return `<span class="badge ${cls}">${inner}</span>`;
    const tip = escAttr(`${t.label} — ${mdStrip(t.short)}`);
    return `<a class="badge ${cls}" href="${glossHref(slug)}" title="${tip}">${inner}</a>`;
  }

  window.Panthera = {
    esc, escAttr, mdStrip, mdInline, icon, cssVar,
    currentIsDark, initTheme,
    loadGlossary, glossary, glossTerm, glossHref, glossaryDecorate, glossBadge,
  };
})();
