"""Splits threshold replay — the committed, reproducible basis for choosing
sharp_split / fade_public thresholds by the pre-stated MECHANICAL VOLUME RULE:

  sharp_split:  largest `min_handle_minus_bets` T yielding >= 4 qualifying
                bets/day (deduped to one per (date, game_pk));
  fade_public:  largest `min_tickets_pct` F yielding >= 6 qualifying bets/day.

Thresholds are volume-chosen, never in-sample-ROI-chosen. The in-window ROI
column is printed for full disclosure — at these sample sizes (SE 11-18 pts)
it is noise, and the volume rule's output is adopted even when it lands on an
in-window loser. The exploration window (everything before each strategy's
`registered_at`) is excluded from evaluation; run this again on post-fetch-fix
data before enabling the strategies, and commit the refreshed table.

Run from the repo root: python scripts/splits_replay.py
Writes docs/proofs/splits-replay.md.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from panthera_mvp import store  # noqa: E402
from panthera_mvp.clients.lumify import load_splits  # noqa: E402
from panthera_mvp.strategy.rules import american_to_decimal  # noqa: E402

SHARP_GRID = [5, 10, 15, 20, 25]
FADE_GRID = [55, 60, 65, 70, 75]
SHARP_MIN_PER_DAY = 4.0
FADE_MIN_PER_DAY = 6.0
LABEL_ORDER = ["pregame", "morning", "manual"]


def _game_rows() -> pd.DataFrame:
    """One row per (date, game_pk): ml splits (freshest label), latest
    consensus ML prices, and the final result."""
    splits = load_splits()
    games = store.load_games()
    lines = store.load_lines()
    finals = games[(games["status"] == "Final")]

    ml = splits[splits["metric"].str.startswith("moneyline.")].dropna(subset=["game_pk"])
    out = []
    for (date_et, pk), grp in ml.groupby(["game_date_et", "game_pk"]):
        row = {"game_date_et": date_et, "game_pk": int(pk)}
        chosen = None
        for label in LABEL_ORDER:
            lab = grp[grp["snapshot_label"] == label]
            if not lab.empty:
                latest = lab["captured_at"].astype(str).max()
                chosen = lab[lab["captured_at"].astype(str) == latest]
                break
        if chosen is None:
            continue
        for m in ("home.bets_pct", "home.handle_pct", "away.bets_pct", "away.handle_pct"):
            sel = chosen[chosen["metric"] == f"moneyline.{m}"]
            row[m.replace(".", "_")] = float(sel.iloc[0]["value"]) if not sel.empty else None

        game = finals[finals["game_pk"] == int(pk)]
        if game.empty:
            continue
        g = game.iloc[0]
        row["home_team"], row["away_team"] = g["home_team"], g["away_team"]
        row["winner"] = g["winner"]

        ev = lines[(lines["game_pk"] == pk) & (lines["market"] == "h2h")]
        if ev.empty:
            continue
        last_label = ev.sort_values("snapshot_ts_utc")["snapshot_label"].iloc[-1]
        ev = ev[ev["snapshot_label"] == last_label]
        for side, team in (("home", g["home_team"]), ("away", g["away_team"])):
            sel = ev[ev["outcome"] == team]
            row[f"{side}_ml"] = float(sel["price_american"].median()) if not sel.empty else None
        out.append(row)
    return pd.DataFrame(out)


def _grade(rows: pd.DataFrame, side_col: str) -> tuple[int, int, float]:
    n = wins = 0
    profit = 0.0
    for _, r in rows.iterrows():
        team = r[side_col]
        price = r["home_ml"] if team == r["home_team"] else r["away_ml"]
        if price is None or pd.isna(price):
            continue
        n += 1
        if r["winner"] == team:
            wins += 1
            profit += 100 * (american_to_decimal(price) - 1)
        else:
            profit -= 100
    roi = 100 * profit / (100 * n) if n else 0.0
    return n, wins, roi


def main() -> None:
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--since",
        default=None,
        help="Only use splits data from this ET date forward (YYYY-MM-DD) — "
        "used to scope the rule to the post-fetch-policy window",
    )
    args = ap.parse_args()

    df = _game_rows()
    if args.since:
        df = df[df["game_date_et"] >= args.since]
    n_days = df["game_date_et"].nunique()
    report = [
        "# Splits threshold replay (mechanical volume rule)",
        "",
        f"Window: {df['game_date_et'].min()} → {df['game_date_et'].max()} "
        f"({n_days} days, {len(df)} graded games with splits+prices). "
        "**Disclosure: the ROI column is in-window exploration data, "
        "noise-level at these n (SE 11–18 pts), and plays no part in the "
        "threshold choice — the volume rule does.**",
        "",
        "## sharp_split — side with handle − bets ≥ T and handle ≥ 50",
        "",
        "| T | bets | bets/day | wins | ROI (in-window, noise) |",
        "|---|---|---|---|---|",
    ]
    sharp_choice = None
    for t in SHARP_GRID:
        qual = []
        for _, r in df.iterrows():
            cands = []
            for side in ("home", "away"):
                b, h = r[f"{side}_bets_pct"], r[f"{side}_handle_pct"]
                if b is not None and h is not None and not pd.isna(b) and not pd.isna(h):
                    cands.append((h - b, h, r[f"{side}_team"]))
            if not cands:
                continue
            gap, handle, team = max(cands)
            if gap >= t and handle >= 50:
                qual.append({**r, "pick_team": team})
        qdf = pd.DataFrame(qual)
        n, wins, roi = _grade(qdf, "pick_team") if not qdf.empty else (0, 0, 0.0)
        per_day = n / n_days if n_days else 0
        report.append(f"| {t} | {n} | {per_day:.1f} | {wins} | {roi:+.1f}% |")
        if per_day >= SHARP_MIN_PER_DAY:
            sharp_choice = t  # grids ascend: last passing T is the largest
    report += [
        "",
        f"**Volume rule (≥{SHARP_MIN_PER_DAY:.0f}/day): T = {sharp_choice}**",
        "",
        "## fade_public — bet opposite the side with tickets ≥ F",
        "",
        "| F | bets | bets/day | wins | ROI (in-window, noise) |",
        "|---|---|---|---|---|",
    ]
    fade_choice = None
    for f in FADE_GRID:
        qual = []
        for _, r in df.iterrows():
            sides = []
            for side, other in (("home", "away"), ("away", "home")):
                b = r[f"{side}_bets_pct"]
                if b is not None and not pd.isna(b):
                    sides.append((b, r[f"{other}_team"]))
            if not sides:
                continue
            tickets, fade_team = max(sides)
            if tickets >= f:
                qual.append({**r, "pick_team": fade_team})
        qdf = pd.DataFrame(qual)
        n, wins, roi = _grade(qdf, "pick_team") if not qdf.empty else (0, 0, 0.0)
        per_day = n / n_days if n_days else 0
        report.append(f"| {f} | {n} | {per_day:.1f} | {wins} | {roi:+.1f}% |")
        if per_day >= FADE_MIN_PER_DAY:
            fade_choice = f
    report += [
        "",
        f"**Volume rule (≥{FADE_MIN_PER_DAY:.0f}/day): F = {fade_choice}**",
        "",
        "_Re-run on ≥3 days of post-fetch-policy data before enabling the "
        "strategies; set the YAML thresholds to the rule's output and update "
        "`registered_at`. The evaluation clock starts there._",
    ]
    out = Path("docs/proofs/splits-replay.md")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(report) + "\n")
    print(f"wrote {out}; sharp T={sharp_choice}, fade F={fade_choice}")


if __name__ == "__main__":
    main()
