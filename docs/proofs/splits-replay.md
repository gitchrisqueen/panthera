# Splits threshold replay (mechanical volume rule)

Window: 2026-08-01 → 2026-08-15 (14 days, 188 graded games with splits+prices). **Disclosure: the ROI column is in-window exploration data, noise-level at these n (SE 11–18 pts), and plays no part in the threshold choice — the volume rule does.**

## sharp_split — side with handle − bets ≥ T and handle ≥ 50

| T | bets | bets/day | wins | ROI (in-window, noise) |
|---|---|---|---|---|
| 5 | 106 | 7.6 | 56 | -1.0% |
| 10 | 79 | 5.6 | 40 | -5.9% |
| 15 | 53 | 3.8 | 28 | -0.7% |
| 20 | 39 | 2.8 | 21 | -0.1% |
| 25 | 24 | 1.7 | 14 | +11.5% |

**Volume rule (≥4/day): T = 10**

## fade_public — bet opposite the side with tickets ≥ F

| F | bets | bets/day | wins | ROI (in-window, noise) |
|---|---|---|---|---|
| 55 | 171 | 12.2 | 78 | -1.2% |
| 60 | 153 | 10.9 | 69 | -1.3% |
| 65 | 122 | 8.7 | 53 | -1.8% |
| 70 | 95 | 6.8 | 38 | -6.9% |
| 75 | 62 | 4.4 | 25 | -4.0% |

**Volume rule (≥6/day): F = 70**

_Re-run on ≥3 days of post-fetch-policy data before enabling the strategies; set the YAML thresholds to the rule's output and update `registered_at`. The evaluation clock starts there._
