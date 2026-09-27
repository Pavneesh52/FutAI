# Metric Definitions & Analytics Specification (Phase 2)

This document contains the mathematical definitions, coordinate conventions, edge-case rules, and hand-verified ground-truth calculations for all metrics computed by `app/analytics`.

---

## 1. Pitch Coordinate System

All spatial metrics operate in **StatsBomb pitch coordinates**:

- **Pitch Dimensions**: $120.0 \times 80.0$ yards / units.
- **Orientation**: $x \in [0.0, 120.0]$ (length, own goal line at $0.0$, opponent goal line at $120.0$), $y \in [0.0, 80.0]$ (width).
- **Perspective**: Coordinates are always oriented from the **acting team's perspective** (the team performing the action attacks towards $x = 120.0$).
- **Thirds Boundaries**:
  - **Defensive Third**: $x < 40.0$
  - **Middle Third**: $40.0 \le x < 80.0$
  - **Attacking Third (Final Third)**: $x \ge 80.0$

---

## 2. Metric Definitions & Formulas

### 2.1 Possession % (`possession_pct`)

$$\text{Possession \%}(T) = \frac{\text{Passes}(T)}{\sum_{t \in \text{Teams}} \text{Passes}(t)} \times 100$$

- **Rationale**: StatsBomb open event data provides discrete `possession` sequence IDs but not clock-duration continuous timestamps for off-ball intervals. In open football analytics (StatsBomb, Opta, FBref), pass-share is the standard proxy for match possession.
- **Edge Case**: Returns `None` if total match passes $= 0$.

### 2.2 Passes Per Defensive Action (`ppda`)

$$\text{PPDA}(T) = \frac{\text{Opponent Passes in Opponent's Own 60\% of Pitch}}{\text{Team } T\text{'s Defensive Actions in Team } T\text{'s Attacking 60\% of Pitch}}$$

- **Spatial Boundaries**:
  - Opponent's Own 60%: Opponent passes where $x \le 72.0$ (from opponent's perspective).
  - Team's Attacking 60%: Team defensive actions where $x \ge 48.0$ (from team's perspective).
- **Defensive Action Types Included**:
  - `tackle` (StatsBomb `Duel` events split by ETL into ground tackle actions)
  - `interception`
  - `foul_committed`
  - *Excluded*: `aerial_lost` (aerial duels are excluded from standard PPDA pressing intensity definitions).
- **Interpretation**: Lower PPDA indicates higher pressing intensity in the opponent's build-up zone.
- **Edge Case**: Returns `None` if the team has $0$ qualifying defensive actions in the attacking 60% (avoids division by zero).

### 2.3 Field Tilt (`field_tilt`)

$$\text{Field Tilt}(T) = \frac{\text{Team } T\text{'s Passes in Final Third }(x \ge 80.0)}{\text{Total Passes by Both Teams in Final Third }(x \ge 80.0)}$$

- **Property**: For a two-team match, $\text{Field Tilt}(A) + \text{Field Tilt}(B) = 1.0$.
- **Edge Case**: Returns `None` if neither team completes any final-third passes. Events with missing coordinates (`x is None`) are excluded from zone-based calculations.

### 2.4 Pass Accuracy (`pass_accuracy`)

$$\text{Pass Accuracy}(T) = \frac{\text{Completed Passes}(T)}{\text{Attempted Passes}(T)} \times 100$$

- **Completed outcome**: Event outcome is `Complete` (StatsBomb events with no outcome field or explicit `Complete`).
- **Edge Case**: Returns `None` if team attempted $0$ passes.

### 2.5 Possession Sequences (`possession_sequences`)

Groups consecutive events sharing the same StatsBomb `possession` sequence ID:
- **Team**: Team initiating the possession (first event in chain).
- **Start / End Zone**: Pitch zone (`defensive_third`, `middle_third`, `attacking_third`) based on first and last valid coordinates in the chain.
- **Duration**: Elapsed match clock time in seconds (`(last.minute * 60 + last.second) - (first.minute * 60 + first.second)`). Stoppage time is preserved. Single-event chains have duration $0$.
- **Ended in Shot**: Boolean flag indicating whether any event in the chain has `event_type == "shot"`.

---

## 3. Hand-Verified Calculations & Sanity Checks

These three benchmark matches serve as test fixtures with exact hand-calculated ground truth:

### Match 1: Argentina 1–0 Colombia (Final with Extra Time, Match ID: `3943077`)

- **Events parsed**: 4,146 regulation + extra-time events (shootout penalties excluded).

| Metric | Colombia (769) | Argentina (779) | Total / Invariant |
|---|---|---|---|
| **Passes** | 660 | 537 | 1,197 |
| **Pass Accuracy** | 84.2% (556 / 660) | 81.2% (436 / 537) | — |
| **Possession %** | **55.1%** (660 / 1197) | **44.9%** (537 / 1197) | 100.0% ✓ |
| **Opponent Passes (Own 60%)** | 399 | 472 | — |
| **Defensive Actions (Atk 60%)** | 29 | 12 | — |
| **PPDA** | **13.76** (399 / 29) | **39.33** (472 / 12) | — |
| **Final-Third Passes ($x \ge 80$)** | 171 | 132 | 303 |
| **Field Tilt** | **0.5642** (171 / 303) | **0.4358** (132 / 303) | 1.0000 ✓ |
| **Shots / Shots on Target** | 19 / 4 | 11 / 5 | 30 / 9 |
| **Expected Goals (xG)** | 0.9723 | 1.0827 | 2.0550 |

---

### Match 2: Argentina 1–1 (5–3 p) Ecuador (Quarter-Final, Match ID: `3942228`)

- **Events parsed**: 2,829 events (regulation + extra time; shootout events excluded from open-play counts).

| Metric | Argentina (779) | Ecuador (3565) | Total / Invariant |
|---|---|---|---|
| **Passes** | 401 | 392 | 793 |
| **Pass Accuracy** | 80.5% (323 / 401) | 80.1% (314 / 392) | — |
| **Possession %** | **50.6%** (401 / 793) | **49.4%** (392 / 793) | 100.0% ✓ |
| **Opponent Passes (Own 60%)** | 265 | 275 | — |
| **Defensive Actions (Atk 60%)** | 23 | 21 | — |
| **PPDA** | **11.52** (265 / 23) | **13.10** (275 / 21) | — |
| **Final-Third Passes ($x \ge 80$)** | 94 | 54 | 148 |
| **Field Tilt** | **0.6351** (94 / 148) | **0.3649** (54 / 148) | 1.0000 ✓ |
| **Shots / Shots on Target** | 13 / 6 | 13 / 6 | 26 / 12 |
| **Expected Goals (xG)** | 4.7761 | 4.5225 | 9.2986 |

---

### Match 3: Deterministic Synthetic Match Fixture (`synthetic_match_events`)

- **Events**: 15 passes + 5 defensive actions + shots.

| Metric | Team A (101) | Team B (102) | Calculation Notes |
|---|---|---|---|
| **Passes (Comp / Att)** | 9 / 10 | 4 / 5 | Team A: 90.0%, Team B: 80.0% |
| **Possession %** | **66.6667%** (10 / 15) | **33.3333%** (5 / 15) | Sum = 100.0% |
| **Opponent Passes (Own 60%)** | 4 (Team B $x \le 72$) | 7 (Team A $x \le 72$) | Exact coordinate filter |
| **Defensive Actions (Atk 60%)** | 2 (Tackle@55, Int@90) | 1 (Foul@50) | Actions with $x < 48$ ignored |
| **PPDA** | **2.00** (4 / 2) | **7.00** (7 / 1) | Strict formula test |
| **Final-Third Passes ($x \ge 80$)** | 3 | 1 | Total = 4 |
| **Field Tilt** | **0.7500** (3 / 4) | **0.2500** (1 / 4) | Sum = 1.0000 |
