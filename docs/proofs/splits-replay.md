# Splits threshold replay (mechanical volume rule)

Window: 2026-08-17 → 2026-08-22 (6 days, 50 graded games with splits+prices). **Disclosure: the ROI column is in-window exploration data, noise-level at these n (SE 11–18 pts), and plays no part in the threshold choice — the volume rule does.**

## sharp_split — side with handle − bets ≥ T and handle ≥ 50

| T | bets | bets/day | wins | ROI (in-window, noise) |
|---|---|---|---|---|
| 5 | 29 | 4.8 | 16 | -6.9% |
| 10 | 26 | 4.3 | 15 | -1.7% |
| 15 | 18 | 3.0 | 10 | -3.6% |
| 20 | 12 | 2.0 | 5 | -23.6% |
| 25 | 7 | 1.2 | 4 | +11.4% |

**Volume rule (≥4/day): T = 10**

## fade_public — bet opposite the side with tickets ≥ F

| F | bets | bets/day | wins | ROI (in-window, noise) |
|---|---|---|---|---|
| 55 | 45 | 7.5 | 13 | -38.9% |
| 60 | 42 | 7.0 | 11 | -43.6% |
| 65 | 36 | 6.0 | 9 | -43.3% |
| 70 | 27 | 4.5 | 7 | -39.0% |
| 75 | 16 | 2.7 | 4 | -39.5% |

**Volume rule (≥6/day): F = 65**

_Re-run on ≥3 days of post-fetch-policy data before enabling the strategies; set the YAML thresholds to the rule's output and update `registered_at`. The evaluation clock starts there._
