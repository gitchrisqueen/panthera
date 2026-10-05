/* Project Panthera — shared dashboard runtime (window.Panthera).
 *
 * Loaded first by every page (index, football, calibration, glossary). Holds
 * what they all need: escaping, the theme toggle, the sport tabs and level
 * chips, and the glossary runtime that attaches a definition to every
 * [data-term] in the document.
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
     pill — the badge itself is the better tap target.
     {link: false} renders the same badge as a plain label with the definition
     as its tooltip — for badges repeated on every table row, where one linked
     column header beats a stack of identical links (and the call site still
     names the slug, so tests/test_glossary.py sees it rendered). */
  function glossBadge(slug, cls, inner, opts) {
    const t = glossTerm(slug);
    if (opts && opts.link === false) {
      const tip = t ? ` title="${escAttr(`${t.label} — ${mdStrip(t.short)}`)}"` : "";
      return `<span class="badge badge-label ${cls}"${tip}>${inner}</span>`;
    }
    if (!t) return `<span class="badge ${cls}">${inner}</span>`;
    const tip = escAttr(`${t.label} — ${mdStrip(t.short)}`);
    return `<a class="badge ${cls}" href="${glossHref(slug)}" title="${tip}">${inner}</a>`;
  }

  // ------------------------------------------------- sport tabs + levels
  /* One page per sport; the level (Professional / College / Other) is a
     filter on that page. Kept as a constant rather than generated: every
     sport needs its own hand-written page anyway. `live` = a registered
     strategy reports at that level. A level that isn't live shows as a
     disabled chip and is never selectable, so `?level=` for it falls back to
     the page's default. Add a sport = add a page + an entry here. */
  const LEVELS = [
    ["pro", "Professional"],
    ["college", "College"],
    ["other", "Other"],
  ];
  const SPORTS = [
    {
      id: "baseball", label: "Baseball", href: "index.html", defaultLevel: "pro",
      levels: {
        pro: { league: "MLB", live: true },
        college: { league: "NCAA D1", live: false },
        other: { league: "minor & international leagues", live: false },
      },
    },
    {
      id: "football", label: "Football", href: "football.html", defaultLevel: "college",
      levels: {
        pro: { league: "NFL", live: false },
        college: { league: "NCAAF FBS", live: true },
        other: { league: "CFL, UFL & others", live: false },
      },
    },
  ];

  /* Fills <nav class="sporttabs"> in the masthead: one tab per sport, then
     the page-level utility links (Glossary, Calibration) right-aligned in the
     same row — the one place on every page to change page. `current` is a
     sport id, "glossary" or "calibration". Not sticky on purpose: the sticky
     section nav below owns --nav-h and the anchor offsets, and carries only
     in-page jumps. */
  const UTILITY = [
    ["glossary", "Glossary", "glossary.html"],
    ["calibration", "Calibration", "calibration.html"],
  ];
  function renderSportTabs(current) {
    const nav = document.querySelector("nav.sporttabs");
    if (!nav) return;
    const link = ([id, label, href], cls) =>
      `<a href="${escAttr(href)}"${cls ? ` class="${cls}"` : ""}` +
      `${id === current ? ' aria-current="page"' : ""}>${esc(label)}</a>`;
    nav.innerHTML =
      SPORTS.map((s) => link([s.id, s.label, s.href])).join("") +
      UTILITY.map((u, i) => link(u, i === 0 ? "tab-util tab-util-first" : "tab-util")).join("");
  }

  /* The section nav scrolls sideways on narrow screens. Fade its right edge
     only while more links are off-screen, so the last link is never dimmed
     and a clipped word always reads as "scroll for more". */
  function wireNavOverflow() {
    const wrap = document.querySelector("nav.sitenav .wrap");
    if (!wrap) return;
    const update = () =>
      wrap.classList.toggle("has-more", wrap.scrollLeft + wrap.clientWidth < wrap.scrollWidth - 1);
    update();
    wrap.addEventListener("scroll", update, { passive: true });
    window.addEventListener("resize", update);
  }

  function sport(id) { return SPORTS.find((s) => s.id === id) || null; }

  /* Renders the level chips for a sport page into #level-chips, applies the
     active level to every [data-level] element and to the section-nav links
     that point at them, and returns the active level. */
  function levelChips(sportId, onChange) {
    const s = sport(sportId);
    const box = document.getElementById("level-chips");
    if (!s || !box) return null;
    const params = new URLSearchParams(window.location.search);
    let active = params.get("level");
    if (!active || !(s.levels[active] && s.levels[active].live)) active = s.defaultLevel;

    const apply = () => {
      document.body.dataset.level = active;
      document.querySelectorAll("main [data-level]").forEach((el) => {
        el.hidden = el.dataset.level !== active;
      });
      document.querySelectorAll("nav.sitenav a[href^='#']").forEach((a) => {
        const target = document.getElementById(a.getAttribute("href").slice(1));
        a.hidden = Boolean(target && target.closest("[hidden]"));
      });
      box.querySelectorAll("button.chip").forEach((b) => {
        b.setAttribute("aria-pressed", String(b.dataset.chipLevel === active));
      });
    };

    const idle = LEVELS.filter(([id]) => !s.levels[id].live).map(([, label]) => label);
    box.innerHTML =
      `<span class="level-label" data-term="level">Level</span>` +
      LEVELS.map(([id, label]) => {
        const lv = s.levels[id];
        const tip = lv.live ? lv.league : `${lv.league}: no strategy yet`;
        return `<button type="button" class="chip level-chip" data-chip-level="${id}"` +
          ` title="${escAttr(tip)}"${lv.live ? "" : " disabled aria-disabled=\"true\""}>` +
          `${esc(label)}${lv.live ? ` <span class="level-league">${esc(lv.league)}</span>` : ""}</button>`;
      }).join("") +
      (idle.length ? `<span class="level-note">${esc(idle.join(" and "))}: no strategy yet</span>` : "");
    box.addEventListener("click", (e) => {
      const b = e.target.closest("button.chip");
      if (!b || b.disabled || b.dataset.chipLevel === active) return;
      active = b.dataset.chipLevel;
      const url = new URL(window.location.href);
      url.searchParams.set("level", active);
      history.replaceState(null, "", url);
      apply();
      if (typeof onChange === "function") onChange(active);
    });
    apply();
    return active;
  }

  /* A status dot and its word as one unit, so stacked phone cards can't pull
     them apart (the cell is a space-between flex row there). */
  function statusCell(status) {
    return `<span class="status"><span class="status-dot ${escAttr(status)}"></span>${esc(status)}</span>`;
  }

  window.Panthera = {
    esc, escAttr, mdStrip, mdInline, icon, cssVar,
    currentIsDark, initTheme,
    loadGlossary, glossary, glossTerm, glossHref, glossaryDecorate, glossBadge,
    SPORTS, LEVELS, renderSportTabs, levelChips, wireNavOverflow, statusCell,
  };
})();
