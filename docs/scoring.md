# Scoring Methodology

This document describes how SmartVoter turns user answers into a ranked list
of parties with explicit confidence and uncertainty. It implements the rules
laid out in **AGENTS.MD §§ 2, 8, 9, 10, 11, 12**.

> **Golden rule.** Match score and confidence score are computed
> *independently*. Match measures *similarity*. Confidence measures *how much
> we trust that similarity*. They are never combined into a single number.

---

## 1. User input → numeric model

Each submitted answer becomes a triple:

| Field          | Range            | Source |
|----------------|------------------|--------|
| `answer_value` | `[-1, +1]`       | Likert scale (–1, –0.5, 0, +0.5, +1) inverted by question polarity. |
| `salience`     | `{0.5, 1.0, 2.0}`| Importance selector. Validated server-side; rejected if other. |
| `policy_item_id` | UUID            | Resolved from the question record (root questions roll up to topics). |

Salience is **linear**. A salience-2.0 answer counts exactly four times more
than a salience-0.5 answer in the match formula.

---

## 2. Party position model

Each `(party_instance, policy_item)` row stores:

* `position_mean` — latent position in `[-1, +1]`.
* `position_uncertainty` — base uncertainty from ingestion.
* `evidence_strength` — raw `[0, 1]` signal strength.
* `evidence_type` — source class (`vote`, `sponsored_bill`, `party_platform`, …).

### 2.1 Effective evidence strength (§8.2)

The reliability priors are **ceilings**. A platform-only row that
accidentally got `evidence_strength=0.95` written into the database does
*not* contribute 0.95 to scoring; it is clipped to:

```
effective_strength = min(stored_strength, prior[evidence_type])
```

| evidence_type        | prior |
|----------------------|------:|
| `vote`               | 1.00  |
| `sponsored_bill`     | 0.80  |
| `committee_behavior` | 0.70  |
| `candidate_past_vote`| 0.55  |
| `party_lineage`      | 0.50  |
| `coalition_agreement`| 0.45  |
| `party_platform`     | 0.35  |
| `public_statement`   | 0.25  |
| `media_interview`    | 0.20  |
| `new_party_synth`    | 0.55  |

Legacy aliases (`platform`, `bill`, `statement`, `null`) and unknown types
are normalised to `party_platform` (0.35) — the safe default.

### 2.2 Effective uncertainty (§10.2)

```
effective_uncertainty = clip(base_uncertainty + 0.4 · party_volatility, 0, 1)
```

Volatility — caused by candidate churn, leader changes, splits, mergers,
rebrands — directly widens position uncertainty.

### 2.3 New-party synthesis (§9.1)

When a party has no direct vote evidence on an item, the engine offers an
aggregator that fuses up to four signals:

```
position = 0.45 · candidate_history
         + 0.25 · party_lineage
         + 0.20 · platform
         + 0.10 · public_statements
```

Missing signals are dropped and weights renormalised. The resulting evidence
strength is **capped at 0.40** (`NEW_PARTY_EVIDENCE_CAP`) and scaled by the
fraction of slots actually present, so a platform-only new party gets ≈0.13
while a party with all four sources approaches the cap.

This means new parties are **never excluded** from the ranking, but they
also never out-weigh established parties on the same item.

---

## 3. Match score (§12.1)

```
distance     = |answer_value − position_mean|
similarity   = 1 − distance / 2                ∈ [0, 1]
weight       = salience · effective_strength
match_score  = Σ similarity · weight  /  Σ weight
```

Only items that appear in *both* the user's answers and the party's positions
contribute. The match score is reported as a percentage in the UI.

Properties guaranteed by tests in `tests/test_methodology_invariants.py`:

* Salience-2 vs salience-0.5 → 4× weight ratio.
* Match score is independent of party volatility.
* A platform-only party with perfect alignment can still score 100% match
  *on that item alone* — but its **confidence will be low** (see §4).

---

## 4. Confidence score (§12.2)

```
base = 0.40 · avg_effective_evidence_on_matched_items
     + 0.25 · coverage_score
     + 0.15 · answer_stability
     + 0.20 · high_salience_topic_coverage

confidence = base · (1 − 0.6 · party_volatility)
```

* `avg_effective_evidence_on_matched_items` — only positions on items the
  user actually answered count. Sectoral parties cannot pad confidence by
  holding strong unrelated positions.
* `coverage_score` — salience-weighted fraction of answered items the party
  has a position on.
* `answer_stability` — leave-one-out: how much the match changes when each
  answer is removed.
* `high_salience_topic_coverage` — fraction of the user's *very-important*
  (`salience=2.0`) topics the party engages with at all.
* `party_volatility` — multiplicative penalty. A party at volatility=0.5
  loses 30% of its base confidence; at volatility=1.0 it loses 60%.

Practical envelope:

| Party profile | Typical confidence |
|---|---|
| Established, rich vote history, full coverage, low volatility | 0.80–0.95 |
| New party, platform + statements only, mid coverage | 0.20–0.35 |
| Established but high candidate turnover (volatility 0.7) | 0.30–0.45 |
| Sectoral party that ignores user's high-salience topics | 0.30–0.50 |

---

## 5. What the scoring engine **never** does

* Combines match and confidence into a single "should-vote-for" number.
* Treats stored `evidence_strength` as ground truth — §8.2 priors always
  apply as ceilings.
* Excludes new parties or treats their declared positions as equal to
  observed parliamentary behaviour.
* Lets a single answer dominate the result silently — `answer_stability`
  exposes that as a confidence drag.
* Looks at IP, login, or any analytics metadata when computing the score.

---

## 6. Files of interest

| File | Purpose |
|---|---|
| `backend/app/services/scoring/engine.py` | All math; pure functions, no DB. |
| `backend/app/services/scoring/__init__.py` | Public exports. |
| `backend/app/api/results.py` | Wires DB → engine → output schema. |
| `backend/app/services/volatility/volatility_service.py` | Computes `party_volatility`. |
| `backend/app/services/ingestion/party_position_pipeline.py` | Writes `party_positions` from real votes. |
| `backend/app/tests/test_scoring.py` | Behavioural tests of each function. |
| `backend/app/tests/test_methodology_invariants.py` | Spec-invariant tests (§§8.2, 9.1, 10.2, 11, 12). |

