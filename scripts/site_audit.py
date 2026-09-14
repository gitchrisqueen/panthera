#!/usr/bin/env python3
"""Geometry audit for the GitHub Pages dashboard.

The dashboard's layout bugs are all *geometric* — boxes that overlap, overflow
their container, or clip content the reader can never scroll to — and none of
them are visible to pytest, which never runs a browser. This script builds the
site, serves it, drives headless Chromium across a ladder of viewports, and
asserts a fixed set of layout invariants in the page.

Usage:
    python scripts/site_audit.py                     # build, audit, report
    python scripts/site_audit.py --warn-only         # never fail (baselining)
    python scripts/site_audit.py --url https://…     # audit a deployed site
    python scripts/site_audit.py --only no_sibling_overlap --screenshots all

Requires the `audit` extra (Playwright is deliberately not a `dev` dependency):
    pip install -e ".[audit]" && python -m playwright install chromium

Exit codes: 0 clean (or warnings only), 1 error-severity findings, 2 harness
failure (build failed, browser unavailable, or the built site has no data).
"""

from __future__ import annotations

import argparse
import json
import re
import socket
import sys
import threading
from datetime import UTC, datetime
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

DEFAULT_VIEWPORTS = [375, 640, 641, 768, 900, 901, 1080, 1081, 1280, 1440]
DEFAULT_PAGES = ["index.html", "calibration.html", "glossary.html"]
VIEWPORT_HEIGHT = 900

# Checks that are meaningless below/above a width are gated here rather than
# inside the injected JS, so --only/--skip and the report stay symmetrical.
ERROR_CHECKS = {
    "page_no_hscroll",
    "no_overflow_out_of_parent",
    "no_sibling_overlap",
    "no_unscrollable_clipped_content",
    "table_has_thead",
    "stacked_cells_labeled",
    "wide_table_fits_above_stack_point",
    "no_raw_markdown",
    "glossary_terms_resolve",
    "sticky_thead_works",
    "anchors_clear_nav",
    "no_console_errors",
    "no_failed_requests",
}
WARN_CHECKS = {
    "nav_h_token_matches",
    "row_height_budget",
    "tap_targets_24px",
    "contrast_tokens",
}
ALL_CHECKS = sorted(ERROR_CHECKS | WARN_CHECKS)


# --------------------------------------------------------------------------
# The in-page audit. One string, evaluated once per page x viewport, so the
# whole geometry pass costs a single round trip. Returns a list of findings;
# Python tags each with page/viewport/severity.
# --------------------------------------------------------------------------
AUDIT_JS = r"""
(opts) => {
  const out = [];
  const TOL = 1;                       // sub-pixel layout noise
  const want = (name) => opts.checks.includes(name);
  const R = (el) => { const r = el.getBoundingClientRect(); return [r.x, r.y, r.width, r.height]; };
  const cs = (el) => getComputedStyle(el);
  const sel = (el) => {
    if (!el || el === document.body) return "body";
    if (el.id) return "#" + el.id;
    const cls = (el.getAttribute("class") || "").trim().split(/\s+/).filter(Boolean).slice(0, 3);
    let s = el.tagName.toLowerCase() + cls.map((c) => "." + c).join("");
    const dl = el.getAttribute("data-label") || el.getAttribute("data-term");
    if (dl) s += `[${el.hasAttribute("data-label") ? "data-label" : "data-term"}="${dl}"]`;
    const p = el.parentElement;
    if (p && p !== document.body && !el.id) s = sel(p) + " > " + s;
    return s;
  };
  const add = (check, message, el, rects) => out.push({
    check, message,
    selector: el ? sel(el) : null,
    text: el ? (el.textContent || "").trim().replace(/\s+/g, " ").slice(0, 80) : null,
    rects: rects || (el ? [R(el)] : []),
  });
  const positioned = (st) => st.position === "absolute" || st.position === "fixed";
  // An element inside an <svg> has its own coordinate system; its client rects
  // legitimately escape the parent box, so the box checks skip those subtrees.
  const inSvg = (el) => !!el.closest("svg");

  // ---- page_no_hscroll ---------------------------------------------------
  if (want("page_no_hscroll")) {
    const de = document.documentElement;
    if (de.scrollWidth > de.clientWidth + TOL) {
      add("page_no_hscroll",
        `page scrolls horizontally: scrollWidth ${de.scrollWidth} > clientWidth ${de.clientWidth}`,
        document.body, [[0, 0, de.scrollWidth, 40]]);
    }
  }

  // ---- no_overflow_out_of_parent ----------------------------------------
  // The direct detector for a <table> spilling out of its grid track and for a
  // .stat-grid label running into its neighbour: a child painting outside a
  // parent that is not clipping or scrolling is always a layout bug.
  if (want("no_overflow_out_of_parent")) {
    document.querySelectorAll("body *").forEach((el) => {
      if (inSvg(el)) return;
      const st = cs(el);
      if (positioned(st) || st.display === "none" || st.visibility === "hidden") return;
      const p = el.parentElement;
      if (!p || p === document.documentElement) return;
      const ps = cs(p);
      if (ps.overflowX !== "visible") return;   // parent clips or scrolls: fine
      const r = el.getBoundingClientRect(), pr = p.getBoundingClientRect();
      if (r.width === 0 || pr.width === 0) return;
      const over = Math.max(r.right - pr.right, pr.left - r.left);
      if (over > TOL) {
        add("no_overflow_out_of_parent",
          `overflows its parent (${sel(p)}) by ${Math.round(over)}px`,
          el, [R(el), R(p)]);
      }
    });
  }

  // ---- no_sibling_overlap ------------------------------------------------
  // Grid/flex children must not intersect *as the reader sees them*. Comparing
  // the children's own boxes is not enough and was the first version's bug: in
  // .breakdowns the grid CELLS tile correctly and never overlap — it is the
  // <table> inside each cell, which cannot shrink below its min-content, that
  // spills out and paints over the next cell. So each child is measured by the
  // union of its own box and any descendant that escapes it.
  const visualRect = (el) => {
    const r = el.getBoundingClientRect();
    let [l, t, rt, b] = [r.left, r.top, r.right, r.bottom];
    el.querySelectorAll("*").forEach((d) => {
      if (inSvg(d)) return;
      const st = cs(d);
      if (positioned(st) || st.display === "none" || st.visibility === "hidden") return;
      // A descendant with a clipping ANCESTOR between it and el is clipped to
      // that ancestor and cannot paint outside el, however far its own layout
      // box extends. Checking only the direct parent was wrong: a <td> inside a
      // scrolling .table-scroll has a plain <tr> for a parent, so the td's
      // pre-clip rect was being unioned in and reported as a phantom overlap.
      let clipped = false;
      for (let anc = d.parentElement; anc && anc !== el; anc = anc.parentElement) {
        if (cs(anc).overflowX !== "visible" || cs(anc).overflowY !== "visible") {
          clipped = true; break;
        }
      }
      if (clipped) return;
      const dr = d.getBoundingClientRect();
      if (dr.width === 0 || dr.height === 0) return;
      l = Math.min(l, dr.left); t = Math.min(t, dr.top);
      rt = Math.max(rt, dr.right); b = Math.max(b, dr.bottom);
    });
    return { left: l, top: t, right: rt, bottom: b, width: rt - l, height: b - t };
  };
  if (want("no_sibling_overlap")) {
    document.querySelectorAll("body *").forEach((box) => {
      if (inSvg(box)) return;
      const d = cs(box).display;
      if (!/grid|flex/.test(d)) return;
      if (cs(box).overflowX !== "visible") return;   // a scroller clips its kids
      const kids = [...box.children].filter((k) => {
        const st = cs(k);
        if (positioned(st) || st.position === "sticky") return false;
        if (st.display === "none" || st.visibility === "hidden") return false;
        const r = k.getBoundingClientRect();
        return r.width > 0 && r.height > 0;
      });
      const vis = kids.map(visualRect);
      for (let i = 0; i < kids.length; i++) {
        for (let j = i + 1; j < kids.length; j++) {
          const a = vis[i], b = vis[j];
          const ox = Math.min(a.right, b.right) - Math.max(a.left, b.left);
          const oy = Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top);
          if (ox > TOL && oy > TOL) {
            add("no_sibling_overlap",
              `overlaps sibling ${sel(kids[j])} by ` +
              `${Math.round(ox)}x${Math.round(oy)}px inside ${sel(box)}`,
              kids[i],
              [[a.left, a.top, a.width, a.height], [b.left, b.top, b.width, b.height]]);
          }
        }
      }
    });
  }

  // ---- no_unscrollable_clipped_content ----------------------------------
  if (want("no_unscrollable_clipped_content")) {
    document.querySelectorAll("body *").forEach((el) => {
      if (inSvg(el)) return;
      const st = cs(el);
      if (!/hidden|clip/.test(st.overflowX)) return;
      if (st.textOverflow === "ellipsis") return;   // deliberate truncation
      // The screen-reader-only idiom (1px box + clip-path) is clipped on
      // purpose and is never meant to be read on screen.
      if (el.clientWidth <= 1 || el.clientHeight <= 1) return;
      if (el.scrollWidth > el.clientWidth + TOL) {
        add("no_unscrollable_clipped_content",
          `clips ${el.scrollWidth - el.clientWidth}px of content with no way to scroll to it`, el);
      }
    });
  }

  // ---- table_has_thead ---------------------------------------------------
  if (want("table_has_thead")) {
    document.querySelectorAll("table").forEach((t) => {
      if (!t.tHead || !t.tHead.rows.length) {
        add("table_has_thead", "table has no header row — its columns are unlabeled", t);
      }
    });
  }

  // ---- stacked_cells_labeled --------------------------------------------
  // Once a responsive-stack table hides its thead, the only thing naming each
  // value is td[data-label]. A missing one renders an unlabeled number.
  if (want("stacked_cells_labeled")) {
    document.querySelectorAll("table.responsive-stack").forEach((t) => {
      if (!t.tHead || cs(t.tHead).display !== "none") return;
      t.querySelectorAll("tbody td").forEach((td) => {
        if (td.hasAttribute("colspan")) return;         // full-width empty-state row
        const lab = (td.getAttribute("data-label") || "").trim();
        if (!lab) add("stacked_cells_labeled", "stacked cell has no data-label", td);
      });
    });
  }

  // ---- wide_table_fits_above_stack_point --------------------------------
  // A table with a designed stack point makes a promise: below it the table
  // becomes cards, above it the table fits. A horizontal scrollbar there means
  // the promise is broken and the last column is simply unreachable without
  // scrolling — which is how the comparison table came to clip "Status" at
  // every desktop width once the glossary affordances widened its headers.
  if (want("wide_table_fits_above_stack_point")) {
    document.querySelectorAll("table.stack-wide, table.stack-mid").forEach((t) => {
      if (!t.tHead || cs(t.tHead).display === "none") return;   // stacked: not applicable
      const box = t.closest(".table-scroll");
      if (!box) return;
      if (box.scrollWidth > box.clientWidth + TOL) {
        const last = t.tHead.rows[0].cells[t.tHead.rows[0].cells.length - 1];
        add("wide_table_fits_above_stack_point",
          `needs ${box.scrollWidth - box.clientWidth}px of horizontal scroll above its ` +
          `stack point — "${(last.textContent || "").trim()}" is cut off`, t);
      }
    });
  }

  // ---- no_raw_markdown ---------------------------------------------------
  if (want("no_raw_markdown")) {
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT, {
      acceptNode(n) {
        if (!n.nodeValue || !n.nodeValue.trim()) return NodeFilter.FILTER_REJECT;
        if (n.parentElement && n.parentElement.closest("code, pre, script, style, textarea")) {
          return NodeFilter.FILTER_REJECT;
        }
        return NodeFilter.FILTER_ACCEPT;
      },
    });
    const pat = /\*\*|`|\[[^\]]+\]\([^)]+\)/;
    let n;
    while ((n = walker.nextNode())) {
      const m = n.nodeValue.match(pat);
      if (m) {
        add("no_raw_markdown", `unrendered markdown "${m[0]}" in visible text`, n.parentElement);
      }
    }
  }

  // ---- glossary_terms_resolve -------------------------------------------
  if (want("glossary_terms_resolve")) {
    document.querySelectorAll('[data-gloss="missing"]').forEach((el) => {
      add("glossary_terms_resolve",
        `data-term="${el.getAttribute("data-term")}" has no entry in glossary.json`, el);
    });
    const seen = new Set();
    document.querySelectorAll('a[href*="glossary.html#"]').forEach((a) => {
      const frag = a.getAttribute("href").split("#")[1];
      if (frag) seen.add(decodeURIComponent(frag));
    });
    out.push({ check: "__glossary_fragments", selector: null, rects: [],
                message: JSON.stringify([...seen]) });
  }

  // ---- nav_h_token_matches ----------------------------------------------
  if (want("nav_h_token_matches")) {
    const nav = document.querySelector("nav.sitenav");
    if (nav) {
      const rootStyle = getComputedStyle(document.documentElement);
      const tok = parseFloat(rootStyle.getPropertyValue("--nav-h"));
      const real = nav.getBoundingClientRect().height;
      if (isNaN(tok)) add("nav_h_token_matches", "--nav-h is not defined", nav);
      else if (Math.abs(tok - real) > 2) {
        add("nav_h_token_matches",
          `--nav-h is ${tok}px but the nav measures ${Math.round(real)}px — ` +
          "anchor offsets will be wrong", nav);
      }
    }
  }

  // ---- row_height_budget -------------------------------------------------
  if (want("row_height_budget") && opts.viewport >= 1081) {
    document.querySelectorAll("#comparison-table tbody tr").forEach((tr) => {
      const h = tr.getBoundingClientRect().height;
      if (h > opts.rowBudget) {
        add("row_height_budget",
          `comparison row is ${Math.round(h)}px tall ` +
          `(budget ${opts.rowBudget}px) — a cell is wrapping`, tr);
      }
    });
  }

  // ---- tap_targets_24px --------------------------------------------------
  if (want("tap_targets_24px") && opts.viewport <= 640) {
    document.querySelectorAll("a, button, summary, input, select, [role=button]").forEach((el) => {
      const st = cs(el);
      if (st.display === "none" || st.visibility === "hidden") return;
      const r = el.getBoundingClientRect();
      if (r.width === 0 || r.height === 0) return;
      // WCAG 2.5.8 exempts links flowing inline inside a sentence.
      if (st.display === "inline" && el.closest("p, li, .tagline, .section-sub, footer")) return;
      if (r.width < 24 || r.height < 24) {
        add("tap_targets_24px",
          `tap target is ${Math.round(r.width)}x${Math.round(r.height)}px (minimum 24x24)`, el);
      }
    });
  }

  return out;
}
"""

# Contrast is checked against the design tokens rather than by scanning every
# node: the regression mode that actually happens here is someone editing a
# token in one theme, and a token sweep catches that deterministically.
CONTRAST_JS = r"""
(pairs) => {
  const lum = (c) => {
    const m = c.match(/[\d.]+/g);
    if (!m || m.length < 3) return null;
    if (m.length > 3 && parseFloat(m[3]) < 1) return null;   // translucent: not comparable
    const f = [0, 1, 2].map((i) => {
      const v = parseFloat(m[i]) / 255;
      return v <= 0.04045 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4);
    });
    return 0.2126 * f[0] + 0.7152 * f[1] + 0.0722 * f[2];
  };
  // Resolve a custom property to a real rgb() by painting it on a probe.
  const probe = document.createElement("span");
  probe.style.cssText = "position:absolute;left:-99999px;top:0";
  document.body.appendChild(probe);
  const resolve = (token) => {
    probe.style.color = "";
    probe.style.color = `var(${token})`;
    const v = getComputedStyle(probe).color;
    return v && v !== "" ? v : null;
  };
  const out = [];
  pairs.forEach(([fgTok, bgTok, minRatio, label]) => {
    const fg = resolve(fgTok), bg = resolve(bgTok);
    const lf = fg && lum(fg), lb = bg && lum(bg);
    if (lf == null || lb == null) return;
    const ratio = (Math.max(lf, lb) + 0.05) / (Math.min(lf, lb) + 0.05);
    if (ratio < minRatio) {
      out.push({
        check: "contrast_tokens",
        message: `${label}: ${fgTok} on ${bgTok} is ${ratio.toFixed(2)}:1 (needs ${minRatio}:1)`,
        selector: ":root", text: `${fg} on ${bg}`, rects: [],
      });
    }
  });
  probe.remove();
  return out;
}
"""

CONTRAST_PAIRS = [
    ["--fg", "--bg", 4.5, "body text"],
    ["--fg-muted", "--bg", 4.5, "muted text"],
    ["--fg-muted", "--bg-raised", 4.5, "muted text on raised"],
    ["--fg-faint", "--bg", 3.0, "faint text (large/secondary)"],
    ["--link", "--bg", 4.5, "links"],
    ["--supported-fg", "--supported-bg", 4.5, "SUPPORTED badge"],
    ["--falsified-fg", "--falsified-bg", 4.5, "FALSIFIED badge"],
    ["--collecting-fg", "--collecting-bg", 4.5, "COLLECTING badge"],
    ["--frozen-fg", "--frozen-bg", 4.5, "frozen badge"],
    ["--replay-fg", "--replay-bg", 4.5, "REPLAY badge"],
    ["--screen-fg", "--bg", 4.5, "SCREEN badge"],
]


# --------------------------------------------------------------------------
# harness
# --------------------------------------------------------------------------
class HarnessError(RuntimeError):
    """Something prevented the audit from running — never a layout finding."""


def _quiet_handler(directory: str):
    class Handler(SimpleHTTPRequestHandler):
        def log_message(self, *args):  # noqa: A003 - silence per-request logging
            pass

    return partial(Handler, directory=directory)


def build_site() -> Path:
    """Build via the real code path so the audit can never test a stale site/."""
    sys.path.insert(0, str(REPO_ROOT / "src"))
    try:
        from panthera_mvp.dashboard import write_site
    except ImportError as exc:  # pragma: no cover - environment problem
        raise HarnessError(f"cannot import panthera_mvp.dashboard: {exc}") from exc
    return write_site(generated_by_run="manual")


def check_site_has_data(site: Path) -> None:
    """An empty build makes every geometry check pass vacuously — refuse it."""
    data_file = site / "site_data.json"
    if not data_file.exists():
        raise HarnessError(f"{data_file} does not exist — did the build run?")
    data = json.loads(data_file.read_text())
    if not data.get("strategies"):
        raise HarnessError("site_data.json has no strategies — nothing to audit")
    if not data.get("picks_history"):
        raise HarnessError("site_data.json has no picks — nothing to audit")


def serve(site: Path) -> tuple[ThreadingHTTPServer, str]:
    """Serve over HTTP, never file://.

    Chromium gives file:// documents an opaque origin, so the pages' fetch() of
    site_data.json fails CORS, every page renders empty, and every geometry
    check passes against a blank document.
    """
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), _quiet_handler(str(site)))
    httpd.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, f"http://127.0.0.1:{httpd.server_address[1]}/"


def fragments_in(html: str) -> set[str]:
    return set(re.findall(r'\bid="([^"]+)"', html))


class Auditor:
    def __init__(self, args):
        self.args = args
        self.findings: list[dict] = []
        self.checks = self._resolve_checks()
        self.shots_dir = Path(args.out) / "screenshots"

    def _resolve_checks(self) -> list[str]:
        checks = set(ALL_CHECKS)
        if not self.args.check_contrast:
            checks.discard("contrast_tokens")
        if self.args.only:
            checks &= set(self.args.only)
        if self.args.skip:
            checks -= set(self.args.skip)
        return sorted(checks)

    def severity(self, check: str) -> str:
        if self.args.strict:
            return "error"
        return "error" if check in ERROR_CHECKS else "warn"

    def record(self, raw: dict, page: str, viewport: int, theme: str) -> dict:
        f = dict(raw)
        f.update(page=page, viewport=viewport, theme=theme, severity=self.severity(raw["check"]))
        self.findings.append(f)
        return f

    # -- per page x viewport ------------------------------------------------
    def audit_page(self, browser, base: str, page_name: str, viewport: int, theme: str,
                   glossary_ids: set[str]) -> None:
        from playwright.sync_api import Error as PWError

        ctx = browser.new_context(
            viewport={"width": viewport, "height": VIEWPORT_HEIGHT},
            device_scale_factor=1,
        )
        page = ctx.new_page()
        console_errors: list[str] = []
        failed: list[str] = []
        page.on("console", lambda m: console_errors.append(m.text) if m.type == "error" else None)
        page.on("pageerror", lambda e: console_errors.append(str(e)))
        page.on("response",
                lambda r: failed.append(f"{r.status} {r.url}") if r.status >= 400 else None)

        try:
            page.goto(base + page_name, wait_until="load", timeout=20000)
            if theme != "system":
                page.evaluate(
                    "(t) => document.documentElement.setAttribute('data-theme', t)", theme)
            try:
                page.wait_for_function("document.body.dataset.ready === '1'", timeout=8000)
            except PWError:
                # Pre-Phase-3 builds have no readiness hook; fall back to a
                # settle so the baseline run still measures a rendered page.
                page.wait_for_timeout(1200)
            # Collapsed <details> hide real tables from every geometry check.
            page.evaluate("document.querySelectorAll('details').forEach(d => d.open = true)")
            page.wait_for_timeout(200)

            opts = {
                "checks": self.checks,
                "viewport": viewport,
                "rowBudget": self.args.row_budget,
            }
            raw = page.evaluate(AUDIT_JS, opts)
            if "contrast_tokens" in self.checks:
                raw += page.evaluate(CONTRAST_JS, CONTRAST_PAIRS)

            # Glossary deep links are cross-page, so they resolve here, not in JS.
            for item in list(raw):
                if item["check"] == "__glossary_fragments":
                    raw.remove(item)
                    for frag in json.loads(item["message"]):
                        if glossary_ids and frag not in glossary_ids:
                            raw.append({
                                "check": "glossary_terms_resolve",
                                "message": f"glossary.html#{frag} has no matching element id",
                                "selector": f'a[href*="#{frag}"]', "text": frag, "rects": [],
                            })

            if ("sticky_thead_works" in self.checks
                    and page_name == "index.html" and viewport >= 901):
                raw += self.check_sticky(page)
            if "anchors_clear_nav" in self.checks:
                raw += self.check_anchors(page)

            if "no_console_errors" in self.checks:
                for msg in console_errors:
                    raw.append({"check": "no_console_errors", "message": msg,
                                "selector": None, "text": None, "rects": []})
            if "no_failed_requests" in self.checks:
                for msg in failed:
                    raw.append({"check": "no_failed_requests", "message": msg,
                                "selector": None, "text": None, "rects": []})

            recorded = [self.record(r, page_name, viewport, theme) for r in raw]
            self.capture(page, page_name, viewport, theme, recorded)
        finally:
            ctx.close()

    def check_sticky(self, page) -> list[dict]:
        """A sticky thead only works if its scroll container is actually bounded."""
        return page.evaluate(r"""
          () => {
            const box = document.querySelector("#ledger .table-scroll.is-tall");
            if (!box) return [{check:"sticky_thead_works",
              message:"#ledger has no .table-scroll.is-tall — the sticky header cannot work",
              selector:"#ledger .table-scroll", text:null, rects:[]}];
            const th = box.querySelector("thead th");
            if (!th) return [];
            // stacked (no thead to stick), or too short to prove anything
            if (getComputedStyle(th).position !== "sticky") return [];
            if (box.scrollHeight <= box.clientHeight + 1) return [];
            box.scrollTop = 400;
            const bt = box.getBoundingClientRect().top +
              parseFloat(getComputedStyle(box).borderTopWidth || 0);
            const rt = th.getBoundingClientRect().top;
            if (Math.abs(rt - bt) > 2) {
              return [{check:"sticky_thead_works",
                message:`header drifted ${Math.round(rt-bt)}px from the ` +
                  "scroller top after scrolling",
                selector:"#ledger-table thead th", text:th.textContent.trim(),
                rects:[[th.getBoundingClientRect().x, th.getBoundingClientRect().y,
                        th.getBoundingClientRect().width, th.getBoundingClientRect().height]]}];
            }
            box.scrollTop = 0;
            return [];
          }
        """)

    def check_anchors(self, page) -> list[dict]:
        """Every in-page anchor must land below the sticky nav, not under it."""
        return page.evaluate(r"""
          () => {
            const nav = document.querySelector("nav.sitenav");
            if (!nav) return [];
            const out = [];
            document.querySelectorAll("nav.sitenav a[href^='#']").forEach((a) => {
              const id = a.getAttribute("href").slice(1);
              const t = document.getElementById(id);
              if (!t) { out.push({check:"anchors_clear_nav",
                message:`nav links to #${id} but no such element exists`,
                selector:`a[href="#${id}"]`, text:a.textContent.trim(), rects:[]}); return; }
              t.scrollIntoView();
              const navB = nav.getBoundingClientRect().bottom;
              const tT = t.getBoundingClientRect().top;
              if (tT < navB - 1) {
                out.push({check:"anchors_clear_nav",
                  message:`#${id} lands ${Math.round(navB - tT)}px under the sticky nav`,
                  selector:"#" + id, text:null,
                  rects:[[t.getBoundingClientRect().x, t.getBoundingClientRect().y,
                          t.getBoundingClientRect().width,
                          Math.min(200, t.getBoundingClientRect().height)]]});
              }
            });
            window.scrollTo(0, 0);
            return out;
          }
        """)

    def capture(self, page, page_name: str, viewport: int, theme: str,
                findings: list[dict]) -> None:
        mode = self.args.screenshots
        if mode == "none":
            return
        if mode == "failures" and not findings:
            return
        self.shots_dir.mkdir(parents=True, exist_ok=True)
        stem = f"{Path(page_name).stem}-{viewport}-{theme}"
        boxed = [f for f in findings if f.get("rects")]
        if boxed:
            page.evaluate(
                """(rects) => {
                  rects.forEach(r => {
                    const d = document.createElement("div");
                    d.className = "__audit_box";
                    d.style.cssText = "position:absolute;pointer-events:none;z-index:2147483647;" +
                      "outline:3px solid #d55e00;background:rgba(213,94,0,.12);";
                    d.style.left = (r[0] + window.scrollX) + "px";
                    d.style.top = (r[1] + window.scrollY) + "px";
                    d.style.width = r[2] + "px";
                    d.style.height = r[3] + "px";
                    document.body.appendChild(d);
                  });
                }""",
                [r for f in boxed for r in f["rects"]],
            )
        shot = self.shots_dir / f"{stem}.png"
        page.screenshot(path=str(shot), full_page=True)
        page.evaluate("document.querySelectorAll('.__audit_box').forEach(e => e.remove())")
        rel = str(shot.relative_to(Path(self.args.out)))
        for f in findings:
            f["screenshot"] = rel

    # -- run ---------------------------------------------------------------
    def run(self) -> int:
        from playwright.sync_api import sync_playwright

        httpd = None
        if self.args.url:
            base = self.args.url if self.args.url.endswith("/") else self.args.url + "/"
            site = None
        else:
            site = Path(self.args.site) if self.args.site else None
            if not self.args.no_build:
                site = build_site()
            elif site is None:
                site = REPO_ROOT / "site"
            check_site_has_data(site)
            httpd, base = serve(site)

        glossary_ids: set[str] = set()
        try:
            with sync_playwright() as pw:
                browser = pw.chromium.launch(headless=not self.args.headed,
                                             slow_mo=self.args.slow_mo)
                try:
                    if "glossary_terms_resolve" in self.checks:
                        ctx = browser.new_context()
                        p = ctx.new_page()
                        try:
                            p.goto(base + "glossary.html", wait_until="load", timeout=15000)
                            p.wait_for_timeout(800)
                            glossary_ids = fragments_in(p.content())
                        except Exception:
                            glossary_ids = set()   # page not built yet (baseline run)
                        ctx.close()

                    for page_name in self.args.pages:
                        for vw in self.args.viewports:
                            for theme in self.args.themes:
                                self.audit_page(browser, base, page_name, vw, theme, glossary_ids)
                finally:
                    browser.close()
        finally:
            if httpd:
                httpd.shutdown()

        return self.report(str(site) if site else self.args.url, base)

    # -- report ------------------------------------------------------------
    def report(self, site: str, base: str) -> int:
        out = Path(self.args.out)
        out.mkdir(parents=True, exist_ok=True)
        errors = [f for f in self.findings if f["severity"] == "error"]
        warns = [f for f in self.findings if f["severity"] == "warn"]
        by_check: dict[str, int] = {}
        for f in self.findings:
            by_check[f["check"]] = by_check.get(f["check"], 0) + 1

        payload = {
            "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
            "site": site,
            "base_url": base,
            "checks_run": self.checks,
            "viewports": self.args.viewports,
            "pages": self.args.pages,
            "themes": self.args.themes,
            "summary": {"error": len(errors), "warn": len(warns), "by_check": by_check},
            "findings": self.findings,
        }
        (out / "report.json").write_text(json.dumps(payload, indent=1))

        lines = ["## Site audit", "",
                 f"`{len(errors)}` errors, `{len(warns)}` warnings across "
                 f"{len(self.args.pages)} pages x {len(self.args.viewports)} viewports "
                 f"x {len(self.args.themes)} themes.", ""]
        if self.findings:
            lines += ["| sev | check | page | vw | theme | detail |", "|---|---|---|---|---|---|"]
            for f in sorted(self.findings, key=lambda x: (x["severity"] != "error", x["check"])):
                detail = f["message"].replace("|", "\\|")[:120]
                what = (f.get("selector") or "")[:60].replace("|", "\\|")
                lines.append(f"| {f['severity']} | `{f['check']}` | {f['page']} | {f['viewport']} "
                             f"| {f['theme']} | `{what}` {detail} |")
        else:
            lines.append("No findings. :tada:")
        (out / "report.md").write_text("\n".join(lines) + "\n")

        for check, n in sorted(by_check.items(), key=lambda kv: -kv[1]):
            sev = "ERROR" if self.severity(check) == "error" else "warn "
            print(f"  {sev} {check:<32} {n}")
        print(f"\n{len(errors)} error(s), {len(warns)} warning(s) → {out}/report.json")

        if self.args.json:
            print(json.dumps(payload, indent=1))
        if self.args.warn_only:
            return 0
        return 1 if errors else 0


def parse_args(argv=None):
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--site", help="audit this already-built site dir (implies --no-build)")
    p.add_argument("--no-build", action="store_true", help="do not run write_site() first")
    p.add_argument("--url", help="audit a deployed URL instead of a local build")
    p.add_argument("--viewports", default=",".join(map(str, DEFAULT_VIEWPORTS)),
                   help="comma-separated widths")
    p.add_argument("--pages", default=",".join(DEFAULT_PAGES),
                   help="comma-separated page filenames")
    p.add_argument("--themes", default="light,dark", help="comma-separated: light,dark,system")
    p.add_argument("--only", help="run only these checks (comma-separated)")
    p.add_argument("--skip", help="skip these checks (comma-separated)")
    p.add_argument("--check-contrast", action="store_true", help="also audit token contrast ratios")
    p.add_argument("--row-budget", type=int, default=64,
                   help="max comparison-table row height in px (default 64)")
    p.add_argument("--screenshots", choices=["all", "failures", "none"], default="failures")
    p.add_argument("--out", default="artifacts/site-audit")
    p.add_argument("--strict", action="store_true", help="treat warnings as errors")
    p.add_argument("--warn-only", action="store_true", help="always exit 0 (for baselining)")
    p.add_argument("--json", action="store_true", help="also print report.json to stdout")
    p.add_argument("--headed", action="store_true")
    p.add_argument("--slow-mo", type=int, default=0)
    a = p.parse_args(argv)

    a.viewports = [int(v) for v in a.viewports.split(",") if v.strip()]
    a.pages = [s.strip() for s in a.pages.split(",") if s.strip()]
    a.themes = [s.strip() for s in a.themes.split(",") if s.strip()]
    a.only = [s.strip() for s in a.only.split(",")] if a.only else None
    a.skip = [s.strip() for s in a.skip.split(",")] if a.skip else None
    if a.site:
        a.no_build = True
    for name in (a.only or []) + (a.skip or []):
        if name not in ALL_CHECKS:
            p.error(f"unknown check {name!r}; known checks: {', '.join(ALL_CHECKS)}")
    return a


def main(argv=None) -> int:
    args = parse_args(argv)
    try:
        return Auditor(args).run()
    except HarnessError as exc:
        print(f"harness error: {exc}", file=sys.stderr)
        return 2
    except ImportError as exc:
        print(f"harness error: {exc}\ninstall with: pip install -e '.[audit]' "
              "&& python -m playwright install chromium", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
