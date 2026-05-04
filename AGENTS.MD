# AGENTS.MD — Source of Truth for Coding Agents

## Project: Evidence-Based Political Match Web App for Israeli Parties

This document is the authoritative instruction set for any coding agent working on this repository. Follow it over ad-hoc assumptions. If a user request conflicts with this file, ask for clarification or implement the safer, more transparent interpretation.

---

## 0. Current Implementation Status

**Phase: 0 — Bare skeleton only. Nothing from Sections 4–19 has been built yet.**

The repository currently contains:

```text
smartvoter/          ← project name (pyproject.toml)
  pyproject.toml     ← uv-managed Python 3.14 project, no dependencies yet
  uv.lock            ← uv lockfile
  .python-version    ← pins Python 3.14
  .cadence/configs/  ← empty placeholder directory
  README.md          ← empty
```

### Development environment

- **OS**: Windows
- **Shell**: PowerShell (`pwsh.exe`)
- Generate all terminal commands for PowerShell syntax (not bash/sh). Use `;` or `&&` for chaining, `$env:VAR` for environment variables, and quote paths with spaces.

### Environment setup

This project uses **[uv](https://github.com/astral-sh/uv)** as the package and environment manager. Do **not** use `pip` or `poetry` directly.

```powershell
# Install dependencies (creates .venv automatically)
uv sync

# Add a new dependency
uv add <package>

# Run a script / command inside the managed environment
uv run python hello.py
uv run pytest
```

No backend, frontend, database, or Docker configuration exists yet. Start from **Phase 1** in Section 18.

---

## 1. Product Goal

Build an MVP web application that helps Israeli voters compare their policy preferences with Israeli political parties based on evidence, not slogans.

The app compares user answers with:

1. real parliamentary behavior;
2. legislative initiatives;
3. historical behavior of current party members and candidates;
4. party lineage, splits, mergers, renames, and rebrands;
5. official platforms and public statements;
6. LLM-based classification and analysis;
7. explicit uncertainty, confidence, and volatility modeling.

The system must **not** tell users whom to vote for. It must provide transparent, evidence-based similarity analysis.

Correct product framing:

> “Based on available evidence, your preferences are closest to these parties, with this level of confidence and these limitations.”

Incorrect product framing:

> “You should vote for this party.”

---

## 2. Core Principles

### 2.1 Evidence-first

Rank evidence reliability in this order:

1. actual parliamentary votes;
2. sponsored or supported bills;
3. committee behavior, if available;
4. historical behavior of current candidates;
5. party lineage / predecessor behavior;
6. coalition agreements;
7. official party platforms;
8. public statements;
9. media interviews.

Declared positions are useful, but less reliable than observed behavior.

### 2.2 LLM-assisted, not LLM-sovereign

The app should use LLMs heavily for:

- summarization;
- topic classification;
- policy-axis extraction;
- neutral question generation;
- question critique;
- party-position inference;
- party-lineage inference;
- explanation generation.

However, LLM outputs are not final truth. Every LLM output must be:

- stored;
- versioned;
- linked to source text or source IDs;
- assigned a confidence score;
- auditable;
- reviewable in admin UI.

Do not store or expose hidden chain-of-thought. Store concise public explanations only.

### 2.3 Separate match from confidence

Always compute and display two different concepts:

```text
policy_match_score
confidence_score
```

Example:

```text
Party A — 72% match, high confidence
Party B — 78% match, low confidence because it has no parliamentary voting history
```

Never sort or present new parties as if low-confidence declared positions were equal to high-confidence voting history.

### 2.4 Model volatility

Israeli parties frequently appear, disappear, split, merge, rename, and rebrand. Candidates also move between parties. The app must model this explicitly.

Do **not** treat party name as a stable identity.

Distinguish:

```text
Political Brand
Party Instance / Election List
Knesset Faction
Legal Party
Person / Candidate / MK
Historical Lineage
```

---

## 3. MVP Scope

### 3.1 Include in MVP

- Local development with mock data first.
- 5 mock parties.
- 20 mock policy items.
- 40 mock questions.
- 10 mock persons/candidates.
- Examples of party lineage: rename, split, merger, successor, alliance, rebrand.
- Examples of candidate volatility.
- Adaptive questionnaire.
- Final results page with match, confidence, evidence, volatility, agreements, disagreements, and representation gap.
- Admin review UI for LLM classifications and generated questions.
- LLM provider abstraction.
- PostgreSQL schema designed for future real Knesset ingestion.

### 3.2 Do not include in MVP unless explicitly requested later

- Full historical coverage of all Knessets.
- Perfect Hebrew legal NLP.
- Full committee transcript analysis.
- Real-time news tracking.
- Automatic public release of LLM-generated questions without review.
- Persuasive political UX.

---

## 4. Technology Stack

### Backend

- Python 3.14 (pinned via `.python-version`; do not downgrade)
- uv (package and virtual-environment manager — replaces pip/poetry; see Section 0)
- FastAPI
- PostgreSQL
- SQLAlchemy or SQLModel
- Alembic
- Pydantic
- Redis
- Celery or RQ for background jobs
- pytest

### Frontend

- Next.js
- TypeScript
- Tailwind CSS
- shadcn/ui preferred

### Infrastructure

- Docker Compose for local development
- `.env.example`
- Backend and frontend health checks
- Clear README setup instructions

### LLM Layer

Use provider abstraction. Do not hardcode a single provider.

Required interface pattern:

```python
class LLMProvider:
    def summarize_bill_or_vote(self, input_data): ...
    def classify_policy_item(self, input_data): ...
    def extract_policy_axis(self, input_data): ...
    def generate_question(self, input_data): ...
    def critique_question(self, input_data): ...
    def infer_party_position(self, input_data): ...
    def infer_party_lineage(self, input_data): ...
```

---

## 5. Repository Structure

Target structure:

```text
political-match/
  backend/
    app/
      main.py
      db/
      models/
      schemas/
      services/
        ingestion/
        llm/
        scoring/
        questionnaire/
        lineage/
        volatility/
        simulation/
        polling/
        coalitions/
      api/
      admin/
      tests/
    alembic/
    pyproject.toml

  frontend/
    app/
    components/
    lib/
    package.json

  docs/
    methodology.md
    data_sources.md
    scoring.md
    llm_pipeline.md
    ux_principles.md

  docker-compose.yml
  README.md
  AGENTS.MD
```

---

## 6. Data Model

Implement these core tables/entities.

### 6.1 `political_brands`

Represents a long-lived political identity, not a specific election list.

Fields:

```text
id
canonical_name
names_json
description
created_at
updated_at
```

### 6.2 `party_instances`

A concrete party/list/faction in a specific period or election.

Fields:

```text
id
political_brand_id
official_name
election_cycle
knesset_number
start_date
end_date
status: active | dissolved | merged | split | renamed
source_url
```

### 6.3 `party_lineage_edges`

Tracks continuity, rename, split, merger, successor, alliance, and rebrand relations.

Fields:

```text
id
from_party_instance_id
to_party_instance_id
relation_type: rename | split | merger | successor | alliance | rebrand
continuity_weight float  -- 0..1
llm_explanation
human_review_status
source_url
```

Continuity is probabilistic, not binary.

Suggested weights:

```text
simple rename: 0.85–0.95
same leader, same structure, new branding: 0.65–0.85
partial split: 0.25–0.55
technical electoral alliance: 0.10–0.35
```

### 6.4 `persons`

MKs, candidates, leaders, founders.

Fields:

```text
id
name_he
name_en
external_ids_json
birth_year nullable
public_profile_url
```

### 6.5 `person_party_memberships`

Tracks membership over time.

Fields:

```text
id
person_id
party_instance_id
role: mk | candidate | minister | leader | founder
start_date
end_date
confidence
source_url
```

### 6.6 `bills`

Fields:

```text
id
external_id
title_he
title_en
summary_he
summary_en
full_text_url
date_submitted
status
source_url
raw_json
```

### 6.7 `votes`

Fields:

```text
id
external_id
bill_id nullable
title_he
title_en
date
knesset_number
vote_type
is_procedural_estimate boolean
importance_score float
signal_quality_score float
source_url
raw_json
```

### 6.8 `vote_results`

Fields:

```text
id
vote_id
person_id
party_instance_id_at_time
vote_value: for | against | abstain | absent | unknown
source_url
```

Important: absence is not automatically opposition. Treat `absent` as low-information unless evidence says otherwise.

### 6.9 `topics`

Suggested MVP topics:

```text
security
judiciary
religion_state
settlements
economy_taxes
healthcare
education
civil_rights
housing
welfare
military_service
governance_corruption
environment
transport
cost_of_living
```

Fields:

```text
id
slug
name_he
name_en
name_ru
description
```

### 6.10 `policy_items`

A normalized political issue extracted from one or more bills, votes, platforms, or statements.

Fields:

```text
id
title
description
topic_id
directional_axis
source_type: vote | bill | platform | statement | candidate_history
source_refs_json
llm_confidence
human_review_status
```

Example axis:

```text
judicial_review_scope:
-1 = broader judicial review and stronger court independence
+1 = greater parliamentary/government control over judicial review
```

### 6.11 `party_positions`

Party position on a policy item.

Fields:

```text
id
party_instance_id
policy_item_id
position_mean float       -- -1..+1
position_uncertainty float
evidence_strength float   -- 0..1
evidence_type
source_refs_json
llm_explanation
```

### 6.12 `questions`

Fields:

```text
id
policy_item_id
question_text_he
question_text_en
question_text_ru
answer_scale_type: likert_5 | binary | tradeoff
neutrality_score
complexity_score
llm_prompt_version
human_review_status: draft | llm_generated | needs_review | approved | rejected | deprecated
```

### 6.13 User/session tables

```text
user_sessions
user_answers
recommendation_runs
```

Store user data anonymously by default. Do not require login for MVP unless explicitly requested.

### 6.14 LLM audit tables

```text
llm_runs
llm_prompt_versions
llm_outputs
```

Every LLM output must store:

```text
model
provider
prompt_version
input_hash
output_json
confidence
created_at
```

---

## 7. LLM Pipeline

### 7.1 Bill/vote summarization

Input:

```text
bill title
bill text or vote title
metadata
```

Output JSON:

```json
{
  "plain_summary": "...",
  "main_policy_change": "...",
  "affected_groups": ["..."],
  "is_procedural": false,
  "importance_score": 0.73,
  "reasoning_summary": "Short public explanation only"
}
```

### 7.2 Topic classification

Output JSON:

```json
{
  "topics": [
    {"topic": "judiciary", "confidence": 0.91},
    {"topic": "governance_corruption", "confidence": 0.62}
  ],
  "primary_topic": "judiciary",
  "classification_confidence": 0.86
}
```

### 7.3 Policy-axis extraction

Output JSON:

```json
{
  "axis_name": "judicial_review_scope",
  "negative_pole": "broader judicial review and stronger court independence",
  "positive_pole": "greater parliamentary/government control over judicial review",
  "direction_explanation": "Positive values indicate support for limiting judicial review."
}
```

### 7.4 Party-position inference

Evidence priority:

```text
votes > sponsored_bills > committee_behavior > candidate_history > lineage > coalition_agreement > platform > public_statement > media_interview
```

Output JSON:

```json
{
  "party_position_mean": 0.72,
  "uncertainty": 0.18,
  "evidence_strength": 0.84,
  "evidence_sources": [
    {"type": "vote", "id": "...", "weight": 1.0},
    {"type": "bill", "id": "...", "weight": 0.7}
  ],
  "explanation": "The party mostly supported bills reducing court review powers."
}
```

### 7.5 Neutral question generation

Output JSON:

```json
{
  "question": "Should the Knesset have greater power to limit the Supreme Court's ability to strike down laws?",
  "answer_scale": [
    "Strongly oppose",
    "Somewhat oppose",
    "Neutral / unsure",
    "Somewhat support",
    "Strongly support"
  ],
  "neutrality_risk": "medium",
  "loaded_terms": [],
  "source_refs": ["vote:123", "bill:456"]
}
```

### 7.6 Question critique

Run a second pass to detect loaded wording.

Output JSON:

```json
{
  "is_loaded": false,
  "bias_direction": null,
  "suggested_revision": null,
  "reading_level": "general public",
  "requires_context": true,
  "context_note": "Explain what judicial review means."
}
```

### 7.7 Public release rules for generated questions

A question can be public only if:

```text
classification_confidence > 0.75
neutrality_score > 0.75
human_review_status = approved
```

For MVP, require human approval.

---

## 8. Bayesian and Probabilistic Modeling

The MVP may use simple formulas, but architecture must support Bayesian uncertainty later.

### 8.1 Party position as latent variable

For each party `p` and policy item `i`, define:

```text
θ[p, i] ∈ [-1, +1]
```

Where:

```text
-1 = strongly supports one pole
 0 = mixed / unclear / centrist
+1 = strongly supports opposite pole
```

### 8.2 Evidence reliability priors

Initial configurable reliability weights:

```text
vote: 1.00
sponsored_bill: 0.80
committee_behavior: 0.70
candidate_past_vote: 0.55
party_lineage: 0.50
coalition_agreement: 0.45
party_platform: 0.35
public_statement: 0.25
media_interview: 0.20
```

### 8.3 MVP posterior approximation

Use weighted evidence aggregation:

```python
position_mean = sum(evidence_value * evidence_weight) / sum(evidence_weight)
uncertainty = 1 / sqrt(sum(evidence_weight) + prior_strength)
```

Use guardrails:

- if total evidence weight is low, uncertainty must be high;
- if evidence is contradictory, uncertainty must increase;
- if source type is mostly platform/statements, confidence must be lower;
- absence from vote should be low-signal unless separately classified as meaningful.

### 8.4 Future hierarchical Bayesian model

Design data structures to support:

```text
θ_brand[brand, issue]
θ_party_instance[party_instance, issue] ~ Normal(θ_brand, σ_party_volatility)
θ_candidate[candidate, issue] ~ Normal(θ_person_history, σ_candidate_volatility)
observed_evidence ~ Normal(θ_party_instance, evidence_noise)
```

---

## 9. Handling New Parties

New parties must not be excluded and must not be treated as if they have voting history.

### 9.1 New-party position formula

For a new party with no direct votes:

```text
party_position =
  0.45 * candidate_history
+ 0.25 * party_lineage_prior
+ 0.20 * official_platform
+ 0.10 * public_statements
```

These coefficients are initial defaults and must be configurable.

### 9.2 New-party confidence

New-party confidence must usually be lower than confidence for parties with substantial voting history.

Display warning:

```text
This party has limited parliamentary history. Its score is based mostly on candidate history, lineage, and declared positions. Treat the match score as less reliable.
```

### 9.3 Candidate-history weighting

If a new party contains former MKs, use their historical votes, discounted by time and context.

Formula:

```text
candidate_history_weight =
  base_weight
  * exp(-age_in_years / half_life)
  * party_switch_penalty
  * role_weight
```

Suggested defaults:

```text
half_life = 4 years
party_switch_penalty = 0.7
leader_role_weight = 1.5
founder_role_weight = 1.3
ordinary_candidate_weight = 0.5
```

---

## 10. Volatility Modeling

### 10.1 Candidate volatility

Compute candidate volatility in range `0..1`.

Inputs:

```text
number_of_party_switches
ideological_distance_between_old_and_new_parties
inconsistency_between_votes_and_statements
recency_of_switch
faction_discipline_deviation
public reversal on major issues
```

Interpretation:

```text
0.0 = stable
1.0 = highly volatile
```

Use volatility to widen uncertainty:

```text
candidate_uncertainty = base_uncertainty + volatility * 0.4
```

### 10.2 Party volatility

Compute party volatility in range `0..1`.

Inputs:

```text
candidate_turnover
leader_change
rename_or_rebrand
merger_or_split
coalition_behavior_change
platform_change
variance among candidates
low faction discipline
```

Use in confidence:

```text
confidence = evidence_strength * coverage_score * (1 - party_volatility_penalty)
```

---

## 11. User Preference Model

Each answer creates:

```text
user_position[user, policy_item] ∈ [-1, +1]
salience[user, policy_item] ∈ [0, 2]
```

Likert mapping:

```text
Strongly oppose = -1
Somewhat oppose = -0.5
Neutral / unsure = 0
Somewhat support = +0.5
Strongly support = +1
```

Importance mapping:

```text
Not important = 0.5
Medium importance = 1.0
Very important = 2.0
```

---

## 12. Matching and Confidence

### 12.1 Match score

For each answered question / policy item:

```python
distance = abs(user_position - party_position)
similarity = 1 - distance / 2
weighted_similarity = similarity * user_salience * party_evidence_strength
```

Final:

```python
match_score = sum(weighted_similarity) / sum(user_salience * party_evidence_strength)
```

Return as `0..1`, display as percentage.

### 12.2 Confidence score

Compute separately:

```python
confidence = (
    average_evidence_strength
    * coverage_score
    * (1 - party_volatility_penalty)
    * answer_stability_score
)
```

Where:

```text
coverage_score = how many user-important issues have evidence for this party
answer_stability_score = whether rankings change strongly when one answer is removed
```

Do not overstate confidence for sparse data.

---

## 13. Adaptive Questionnaire

### 13.1 UX goal

Do not ask 50 fixed questions. Ask 8–15 adaptive questions.

### 13.2 Next-question selection

After each answer:

1. compute current party scores;
2. identify current top 5 parties;
3. find unasked policy items;
4. prefer questions where top parties differ most;
5. prefer high evidence quality;
6. prefer topics related to important previous answers;
7. avoid repeating the same topic too much;
8. apply user fatigue penalty.

Heuristic:

```python
question_value = (
    party_separation_score
    * evidence_quality
    * topic_relevance
    * diversity_penalty
    * user_fatigue_penalty
)
```

Where:

```text
party_separation_score = variance of party positions among current top parties
```

### 13.3 Stop condition

Offer results when:

```text
user answered >= 8 questions AND ranking stability > threshold
```

Force result option after:

```text
15 questions
```

UX options:

```text
Show result now
Ask 5 more questions to improve confidence
Deep dive into a topic
```

Do not show live party recommendation during questionnaire. It biases later answers.

---

## 14. UI/UX Requirements

### 14.1 Tone

Neutral, non-persuasive, analytical.

Never use language like:

```text
Your correct party is...
You should vote for...
This party is best for you...
```

Use:

```text
Based on available evidence...
Your answers are closest to...
Confidence is low/medium/high because...
```

### 14.2 Onboarding screen

Must say:

```text
This tool compares your policy preferences with parties' observed parliamentary behavior and declared positions.
It does not tell you whom to vote for.
It shows similarity, disagreement, evidence, and uncertainty.
```

Buttons:

```text
Start quick test
Detailed test
View methodology
```

### 14.3 Question card

Each question card must include:

```text
Question
Short context
Answer scale
Importance selector
Expandable: Why am I asked this?
Expandable: Related votes/sources
```

Do not expose party alignment before answer submission.

### 14.4 Results page

Required sections:

1. Top matches.
2. Confidence and uncertainty.
3. Main agreements.
4. Main disagreements.
5. Evidence quality.
6. Volatility warning if relevant.
7. New-party warning if relevant.
8. Representation gap.
9. Link to methodology.

Example result card:

```text
Party A — 72% match, high confidence
Evidence: 230 votes, 31 bills
Volatility: low
Coverage of your important topics: 82%

Main agreements:
- judiciary
- security
- taxes

Main disagreements:
- religion and state
- welfare
```

### 14.5 Representation gap

Always compute and display whether the user is poorly represented overall.

Example:

```text
No party strongly represents all of your high-priority positions.
You are closest to Party A on economy, Party B on judiciary, and Party C on religion/state.
```

---

## 14A. Elegant UI, Infographics, Visual Analytics, and Verifiable Evidence Explorer

This product must not look like a crude political quiz. It must feel like a serious civic analytics platform: elegant, calm, data-rich, and transparent. The interface should combine a polished consumer-grade questionnaire with analyst-grade drill-down tools.

### 14A.1 Visual design direction

Design qualities:

```text
calm
neutral
trustworthy
elegant
modern
non-partisan
information-dense only where useful
```

Avoid:

```text
campaign-style colors
party-colored emotional framing
aggressive banners
leader photos as persuasion elements
red/green moral coding for parties
winner/loser language
```

Preferred design language:

```text
soft background
high-quality typography
large readable cards
subtle borders
ample whitespace
clear hierarchy
muted accent colors
careful micro-interactions
```

Use party colors only in factual comparison charts and legends, never as emotional endorsement.

### 14A.2 Required design system components

Implement reusable frontend components:

```text
AppShell
OnboardingHero
QuestionCard
ImportanceSelector
EvidenceDrawer
SourceCitationBadge
ConfidenceBadge
VolatilityBadge
MatchScoreRing
TopicRadarChart
PartyComparisonMatrix
EvidenceTimeline
VoteBreakdownChart
PolicyAxisChart
RepresentationGapPanel
MethodologyPanel
AdminReviewCard
```

Every visual component must have loading, empty, and error states.

### 14A.3 Results page must be visually rich

The result page should include both summary and drill-down.

Required visualizations:

1. **Top-party match cards**
   - match percentage;
   - confidence badge;
   - evidence strength;
   - volatility warning;
   - short explanation.

2. **Topic radar / spider chart**
   - user preference profile by topic;
   - top 2–3 parties overlaid;
   - must allow toggling parties on/off.

3. **Agreement/disagreement heatmap**
   - rows: topics or policy axes;
   - columns: parties;
   - cells: similarity, disagreement, or insufficient evidence.

4. **Evidence quality stacked bar**
   - votes;
   - bills;
   - candidate history;
   - party lineage;
   - platform;
   - public statements.

5. **Confidence decomposition chart**
   Show how final confidence was calculated:

```text
evidence strength
coverage
answer stability
party volatility penalty
new-party penalty
```

6. **Representation gap visualization**
   Show when no party strongly represents the user across all high-salience topics.

7. **Timeline of party behavior**
   For a selected party/topic, show relevant votes, bills, candidate changes, and lineage events over time.

### 14A.4 Evidence-first UX

Every factual claim in the UI about a party, candidate, or policy decision must be clickable and verifiable.

Any statement like:

```text
Party A supported limiting judicial review.
Candidate B historically supported increasing subsidies for religious education.
Party C has high volatility on economic policy.
```

must link to an evidence drawer that shows:

```text
source type
source title
source date
original source link
short neutral summary
LLM classification output
confidence score
human review status
related vote/bill/person/party IDs
```

No unsupported political claim should appear in the UI.

### 14A.5 Evidence Drawer

Implement an `EvidenceDrawer` or `EvidenceModal` that opens from any claim, chart cell, result card, or question.

The drawer must show:

```text
Claim being supported
Evidence list
Source type icons
Date
Party/person involved
Original vote/bill/platform/statement reference
How the party voted or acted
How the LLM classified the source
Human review status
Confidence and uncertainty
```

For votes, show:

```text
vote title
vote date
bill linkage if available
party-level summary
MK-level vote distribution
for / against / abstain / absent counts
source URL
```

For candidate history, show:

```text
candidate name
role in current party
previous party memberships
relevant past votes
party-switch history
candidate volatility score
```

For party lineage, show:

```text
from party instance
to party instance
relation type
continuity weight
reasoning summary
source URL
human review status
```

### 14A.6 Database-backed verifiability

The frontend must not rely on hardcoded political claims. All claims must come from database records.

Add or support these database entities if not already present:

```text
evidence_sources
claim_records
claim_evidence_links
source_documents
source_snapshots
chart_annotations
```

Suggested fields for `evidence_sources`:

```text
id
source_type: vote | bill | platform | statement | committee | candidate_history | lineage | external_report
source_title
source_date
source_url
source_origin: knesset | open_knesset | party_site | admin_upload | other
raw_text nullable
raw_json nullable
language
created_at
```

Suggested fields for `claim_records`:

```text
id
claim_text
claim_type: party_position | candidate_position | lineage | volatility | topic_classification | question_context
entity_type: party | person | policy_item | vote | bill
entity_id
confidence
human_review_status
created_by: llm | admin | system
created_at
```

Suggested fields for `claim_evidence_links`:

```text
id
claim_id
evidence_source_id
support_type: supports | contradicts | context | weak_support
weight
llm_explanation
```

Any chart value that implies a political claim should be traceable to one or more `claim_records` and `evidence_sources`.

### 14A.7 Infographic requirements

Use statistical charts carefully and honestly.

Required chart rules:

```text
always label axes
always explain scale direction
always expose missing data
never hide low confidence
never use misleading 3D charts
never normalize in a way that hides sparse evidence
show uncertainty intervals where available
```

Recommended visualizations:

```text
radar chart for topic profile
heatmap for party-policy similarity
stacked bar for evidence composition
line/timeline chart for policy movement over time
sankey or flow diagram for party lineage/splits/mergers
network graph for candidate movement between parties
small multiples for topic-by-topic comparison
box/interval plot for uncertainty ranges
```

Do not overuse charts. Every chart must answer a clear user question.

### 14A.8 Party lineage visualization

Because Israeli parties appear, disappear, merge, split, and rebrand, the app should include a lineage visualization.

For MVP, implement a simple timeline/flow view:

```text
Party A → rename → Party B
Party C + Party D → merger/alliance → Party E
Party F → split → Party G / Party H
```

Each edge must show:

```text
relation type
continuity weight
confidence
source links
human review status
```

Later this can become a Sankey diagram or graph visualization.

### 14A.9 Candidate volatility visualization

For each candidate/person page, show:

```text
party membership timeline
role timeline
major policy-position changes
past votes relevant to current party score
volatility score
uncertainty contribution
```

For new parties, show how much each candidate contributes to the party inferred position.

Example:

```text
New Party X position on judiciary is based on:
- Leader A past votes: 45%
- Candidate B past votes: 20%
- Party platform: 25%
- Public statements: 10%
```

### 14A.10 Question UX with verifiability

Each question should include:

```text
plain-language question
short neutral context
answer scale
importance selector
optional “show evidence behind this question”
optional “show why this question was selected”
```

The “why selected” explanation must be non-manipulative:

```text
This question helps distinguish between parties that are currently close in your results.
```

Do not say:

```text
This question will determine whether you are really right-wing/left-wing.
```

### 14A.11 Methodology transparency page

Create a polished methodology page with diagrams explaining:

```text
how data is collected
how LLM classification works
how human review works
how party positions are inferred
how confidence is calculated
how volatility is calculated
how new parties are handled
how user answers are scored
what the system cannot know
```

This page must be accessible from onboarding, question pages, and results.

### 14A.12 Database explorer / public evidence browser

MVP should include a read-only evidence browser for transparency.

Minimum pages:

```text
/parties
/parties/[id]
/persons/[id]
/policy-items/[id]
/votes/[id]
/bills/[id]
/sources/[id]
/methodology
```

Each page must show:

```text
summary
data provenance
linked claims
linked evidence
LLM classifications
human review status
last updated timestamp
```

This is not only an admin feature. Users must be able to verify claims themselves.

### 14A.13 Admin analytics and review UX

The admin panel should not be an afterthought. It is central to trust.

Admin needs dashboards for:

```text
unreviewed LLM classifications
low-confidence claims
claims with contradictory evidence
questions with neutrality risk
parties with high volatility
new parties with sparse evidence
sources needing refresh
```

Admin review screens should show side-by-side:

```text
original source text
LLM summary
LLM classification
suggested policy axis
generated question
linked party positions
confidence scores
approve / reject / edit controls
```

### 14A.14 UX quality bar

The MVP should be visually impressive even with mock data. It should demonstrate the intended product quality.

Acceptance criteria for UI/UX:

```text
1. The onboarding page looks polished and non-partisan.
2. The questionnaire feels smooth and modern.
3. Results include at least three meaningful visualizations.
4. Every result card links to evidence.
5. Every chart cell or major claim can be drilled into.
6. Source links and human review status are visible.
7. Low confidence and missing data are visually obvious.
8. New-party uncertainty is clearly explained.
9. Party lineage and candidate volatility are visualized at least minimally.
10. The methodology page uses diagrams or structured visual explanations, not only text.
```

### 14A.15 Implementation recommendation for charts

Use a charting library such as Recharts, Visx, or ECharts. Prefer simple, readable charts over complex decorative ones.

Recommended MVP chart components:

```text
TopicRadarChart
PartyPolicyHeatmap
EvidenceCompositionBar
ConfidenceBreakdownBar
PartyLineageTimeline
CandidateMovementTimeline
```

Each chart component must accept data from API responses, not hardcoded values.



---

## 14B. Election / Knesset Seat Simulation, Coalition Scenarios, and Forecasting

The product should eventually include a simulation layer that estimates possible Knesset distributions and coalition scenarios. This is separate from the voter-party matching engine.

The matching engine answers:

```text
Which parties are closest to this user's preferences, with what confidence?
```

The simulation engine answers:

```text
Given current polling, past election behavior, threshold rules, party volatility, and uncertainty, what Knesset compositions and coalition outcomes are plausible?
```

Do not mix these two outputs into a manipulative recommendation. A party may be a good policy match but have low probability of passing the electoral threshold, or it may be a mediocre match but central to a plausible coalition. Show this as analysis, not voting advice.

### 14B.1 Required simulation goals

MVP simulation should support:

1. estimated seat distribution across parties;
2. probability that a party passes the electoral threshold;
3. uncertainty intervals for each party's seat count;
4. bloc-level summaries;
5. coalition feasibility scenarios;
6. sensitivity analysis: what happens if a party gains or loses 1–2 seats;
7. historical comparison with previous elections;
8. explicit assumptions and confidence warnings.

The simulation must never present a single deterministic forecast as fact.

Correct phrasing:

```text
In this simulation run, Party A receives 9–12 seats in the central 80% interval.
```

Incorrect phrasing:

```text
Party A will receive 10 seats.
```

### 14B.2 Data sources for simulation

Design the simulation ingestion layer to support multiple source classes:

1. **Official historical election results**
   - vote shares;
   - turnout;
   - parties/lists;
   - threshold outcomes;
   - final seat allocations.

2. **Current polling data**
   - pollster;
   - sample size;
   - field dates;
   - published seat estimates or vote-share estimates;
   - undecided voters, if reported;
   - pollster methodology notes, if available.

3. **Historical polling error**
   - average pollster bias;
   - variance by pollster;
   - late campaign swing;
   - bloc-level polling error;
   - threshold miss probability.

4. **Party lineage and successor mapping**
   - necessary because polling names, election lists, factions, and historical brands may not match exactly.

5. **Coalition constraints**
   - declared refusal to sit with specific parties;
   - ideological bloc assumptions;
   - historical coalition behavior;
   - leadership constraints;
   - confidence score for each constraint.

Polls and coalition declarations are time-sensitive. When real ingestion is implemented, each simulation result must show the data timestamp and source age.

### 14B.3 New database tables for simulation

Add these models to the backend schema.

```text
pollsters
polls
poll_party_results
historical_election_results
historical_party_results
seat_allocation_runs
seat_allocation_results
simulation_runs
simulation_party_results
simulation_bloc_results
coalition_constraints
coalition_scenarios
coalition_scenario_members
simulation_assumptions
model_backtests
```

Suggested fields:

```text
pollsters:
  id
  name
  country
  historical_bias_json
  historical_error_std_json
  reliability_score
  source_url

polls:
  id
  pollster_id
  field_start_date
  field_end_date
  publication_date
  sample_size
  population
  method
  source_url
  raw_json
  quality_score

poll_party_results:
  id
  poll_id
  party_instance_id nullable
  political_brand_id nullable
  reported_name
  seats_mean nullable
  vote_share_mean nullable
  lower_bound nullable
  upper_bound nullable
  undecided_handling_notes

historical_election_results:
  id
  election_cycle
  date
  turnout
  threshold_percent
  total_valid_votes
  source_url

historical_party_results:
  id
  historical_election_result_id
  party_instance_id nullable
  political_brand_id nullable
  reported_name
  vote_share
  votes
  seats
  passed_threshold

simulation_runs:
  id
  created_at
  model_version
  data_cutoff_date
  n_iterations
  assumptions_json
  input_snapshot_hash

simulation_party_results:
  id
  simulation_run_id
  party_instance_id
  seats_mean
  seats_median
  seats_p10
  seats_p25
  seats_p75
  seats_p90
  threshold_pass_probability
  vote_share_mean
  volatility_score

coalition_constraints:
  id
  source_party_instance_id
  target_party_instance_id nullable
  target_bloc nullable
  constraint_type: refuses | prefers | requires | impossible | uncertain
  strength: hard | soft
  confidence
  source_refs_json
  llm_explanation
  human_review_status

coalition_scenarios:
  id
  simulation_run_id
  scenario_name
  probability_estimate
  seat_mean
  seat_p10
  seat_p90
  feasibility_score
  stability_score
  ideological_coherence_score
  explanation
```

### 14B.4 Seat allocation model

Implement the official seat allocation rules as a separate deterministic module, then use it inside Monte Carlo simulations.

The module should accept vote shares or vote counts and return seat allocation after threshold filtering.

Required interface:

```python
class SeatAllocator:
    def allocate(self, vote_shares: dict[str, float], total_seats: int = 120) -> dict[str, int]:
        ...
```

Implementation notes:

- Keep threshold percent configurable.
- Keep surplus-vote agreement handling configurable for later versions.
- MVP may first implement simplified proportional allocation with threshold filtering, but the code must clearly mark this as simplified.
- Add unit tests for allocation edge cases near the threshold.

### 14B.5 Poll aggregation model

Build a poll aggregator that produces a probabilistic prior for party vote shares.

MVP model:

```text
weighted_poll_average = weighted average of recent polls
```

Weights should include:

```text
recency_weight
sample_size_weight
pollster_reliability_weight
method_quality_weight
```

Suggested simple recency decay:

```text
recency_weight = exp(-days_since_field_end / half_life_days)
half_life_days = 14 to 21 by default
```

The aggregator should output:

```json
{
  "party_id": "...",
  "vote_share_mean": 0.083,
  "vote_share_std": 0.018,
  "polling_support_sources": [...],
  "model_notes": "..."
}
```

### 14B.6 Bayesian / probabilistic simulation model

For each party, model vote share as a latent variable:

```text
v[p] = latent current vote share for party p
```

MVP approximation:

```text
v[p] ~ Normal(poll_average[p] + pollster_bias_adjustment[p], uncertainty[p])
```

Then normalize sampled vote shares and apply threshold + seat allocation.

Better later:

```text
v ~ Dirichlet or logistic-normal distribution
```

The model should account for:

1. party-level polling uncertainty;
2. correlated bloc-level polling error;
3. threshold uncertainty for small parties;
4. new-party volatility;
5. party split/merger uncertainty;
6. turnout scenario uncertainty;
7. undecided voter allocation.

Recommended MVP simulation loop:

```python
for iteration in range(n_iterations):
    sampled_vote_share = sample_vote_share_distribution(poll_aggregate, covariance_model)
    sampled_vote_share = apply_undecided_voter_model(sampled_vote_share)
    sampled_vote_share = apply_party_volatility_model(sampled_vote_share)
    seats = seat_allocator.allocate(sampled_vote_share)
    save_iteration_summary(seats)
```

### 14B.7 Volatility in simulation

The existing party volatility model should also affect election simulation.

A volatile party should have wider forecast intervals.

Party volatility inputs:

```text
candidate turnover
leader replacement
recent split/merger/rebrand
new-party status
inconsistent platform or unclear ideology
historical polling instability
threshold proximity
```

Use volatility to increase uncertainty:

```python
adjusted_std = base_polling_std * (1 + volatility_score * volatility_multiplier)
```

New parties should have especially high uncertainty unless there is strong polling evidence.

### 14B.8 Party disappearance, merger, split, and rename in simulations

The simulation engine must use `political_brands`, `party_instances`, and `party_lineage_edges`, not raw party names.

Required cases:

1. **Rename**
   - treat as high continuity if leadership/list/policy are substantially continuous.

2. **Merger / electoral alliance**
   - combine priors from component parties;
   - increase uncertainty if alliance is new or fragile.

3. **Split**
   - allocate predecessor support probabilistically across successors;
   - use candidate movement, polling, and declared voter targeting.

4. **Disappeared party**
   - keep historical record;
   - do not include in current simulation unless it has a successor edge.

5. **New party**
   - initialize from candidate histories, public polling, lineage if any, and declared platform;
   - widen uncertainty.

LLM may propose lineage and support-transfer assumptions, but admin review is required.

### 14B.9 Coalition scenario simulation

After each seat simulation, evaluate possible coalitions.

MVP coalition logic:

```text
A coalition is numerically viable if seats >= 61.
A coalition is politically feasible if it does not violate hard constraints and has acceptable soft-constraint score.
```

Implement:

```python
class CoalitionSimulator:
    def generate_viable_coalitions(self, seat_distribution): ...
    def score_coalition(self, coalition_parties): ...
```

Coalition score should include:

```text
seat_margin
ideological distance
historical cooperation
explicit refusal constraints
leader compatibility
party volatility
number of parties
```

Output examples:

```text
Coalition Scenario A:
- members: Party A, Party B, Party C
- mean seats: 64
- feasibility: medium
- stability: low
- main weakness: depends on one volatile threshold party
```

Do not present coalition scenarios as predictions. Present them as conditional simulations.

### 14B.10 UI/UX for simulations

Add a dedicated “Election Simulator” or “Knesset Simulator” section.

Required visualizations:

1. **Knesset semicircle chart**
   - 120 seats grouped by party/bloc.

2. **Seat distribution intervals**
   - bar chart with p10/p50/p90 or p25/p75 intervals.

3. **Threshold risk chart**
   - probability of each small party passing the threshold.

4. **Coalition scenario cards**
   - possible coalitions, seats, feasibility, stability, constraints.

5. **Scenario comparison panel**
   - compare current polling average vs historical election baseline vs user-defined assumptions.

6. **Sensitivity sliders**
   - allow user to adjust small changes:
     - Party A +1 seat equivalent;
     - Party B below threshold;
     - undecided voters shift toward bloc X;
     - turnout high/low.

7. **Assumptions drawer**
   - data cutoff date;
   - included polls;
   - weighting method;
   - threshold rule;
   - uncertainty model;
   - limitations.

UX warning:

The simulator must be visually engaging but epistemically humble. Use uncertainty bands, probability labels, and “scenario” language everywhere.

### 14B.11 Integration with user matching

On the result page, optionally show a separate section:

```text
Strategic context, not voting advice
```

Possible displays:

```text
Your closest party has low threshold-pass probability.
Your second-closest party has high confidence and likely parliamentary representation.
Your preferred policy cluster is split across several parties/blocs.
```

Do not recommend strategic voting. The app may show facts and scenarios only.

Correct:

```text
Party A is your closest match, but current simulations give it a low probability of passing the threshold. This reduces confidence that your vote would translate into seats.
```

Incorrect:

```text
Vote for Party B instead because Party A may not pass the threshold.
```

### 14B.12 Backtesting

Every simulation model must support historical backtesting.

Backtesting task:

```text
Use polls available N days before a past election and compare simulated seat distributions with final results.
```

Metrics:

```text
mean absolute seat error
bloc-level error
threshold prediction accuracy
calibration of confidence intervals
Brier score for threshold pass/fail
coalition feasibility hit rate, if applicable
```

Add a backtesting admin page showing:

```text
model version
historical election
data cutoff date
forecast distribution
actual result
error metrics
```

Simulation models should not be trusted until backtested.

### 14B.13 API endpoints for simulation

Add:

```http
GET /api/simulation/latest
POST /api/simulation/run
GET /api/simulation/{run_id}
GET /api/simulation/{run_id}/party/{party_id}
GET /api/simulation/{run_id}/coalitions
POST /api/simulation/scenario
GET /api/admin/simulation/backtests
POST /api/admin/simulation/backtest
```

### 14B.14 Simulation acceptance criteria

The simulation module is acceptable when:

```text
1. It can run with mock polling/election data.
2. It outputs probabilistic seat ranges, not one deterministic result.
3. It computes threshold-pass probability for small parties.
4. It generates at least 5 plausible coalition scenarios.
5. It shows assumptions and data sources in the UI.
6. It supports party rename/merger/split via lineage edges.
7. It widens uncertainty for new and volatile parties.
8. It has unit tests for seat allocation and threshold behavior.
9. It has at least one historical backtest using mocked or real historical data.
10. It is visually separated from the personal political matching result.
```

---

## 14C. Additional Missing Requirements to Add Before Real Public Release

The following areas are not optional for a real civic/political product. They may be simplified in MVP but must be represented in architecture.

### 14C.1 Privacy and anonymity

Political preferences are sensitive. Default mode must be anonymous.

Requirements:

```text
- Do not require login for basic questionnaire.
- Store user sessions with random IDs.
- Do not store IP address unless strictly needed for security logs.
- Provide a delete-session endpoint.
- Separate analytics events from political answers.
- Never sell, export, or share individual preference data.
```

Add privacy endpoints:

```http
DELETE /api/session/{session_id}
GET /api/privacy
```

### 14C.2 Localization and language consistency

Israel requires at least Hebrew support; Russian, Arabic, and English should be structurally supported.

Requirements:

```text
- UI text must be i18n-ready.
- Source language and translated text must both be stored.
- LLM translations must be reviewable.
- Political terms must use a glossary to avoid inconsistent translation.
- Hebrew RTL layout must be first-class, not an afterthought.
```

#### Implementation status (Phase 8)

The following i18n infrastructure is in place:

```text
frontend/locales/types.ts          — Translations TypeScript interface (single source of truth for keys)
frontend/locales/en.ts             — English translations (complete)
frontend/locales/he.ts             — Hebrew translations (UI shell complete; question/party content pending review)
frontend/locales/ru.ts             — Russian translations (UI shell complete; question/party content pending review)
frontend/lib/i18n.tsx              — I18nProvider, useT(), useLang() hooks
frontend/components/LanguageSwitcher.tsx  — EN / עב / РУ toggle in header
```

Supported languages and direction:

| Code | Language | Direction | Status |
|------|----------|-----------|--------|
| `en` | English  | LTR       | Complete |
| `he` | Hebrew   | RTL       | UI translated; content needs native review |
| `ru` | Russian  | LTR       | UI translated; content needs native review |

Outstanding work is tracked in **Phase 8** (Section 18).

### 14C.3 Accessibility

Visual sophistication must not reduce accessibility.

Requirements:

```text
- WCAG AA target.
- Keyboard navigation.
- Screen-reader labels for charts.
- Text alternatives for infographics.
- Colorblind-safe palettes.
- Do not encode political meaning by color alone.
```

### 14C.4 Bias and neutrality audit

Add periodic audits for:

```text
- loaded wording;
- topic overrepresentation;
- party over/underexposure;
- LLM classification drift;
- unequal treatment of new vs old parties;
- translation bias;
- source coverage gaps.
```

Admin UI should include a neutrality dashboard.

### 14C.5 Source licensing and legal review

Before public deployment, verify:

```text
- permission to use source data;
- licensing of Open Knesset / other datasets;
- correct attribution;
- compliance with Israeli election law and campaign-period restrictions;
- disclaimer language reviewed by legal expert if possible.
```

### 14C.6 Editorial governance

Because the app classifies political claims, it needs governance.

Requirements:

```text
- Maintain reviewer roles.
- Keep review logs.
- Allow public issue reports for bad classifications.
- Version methodology changes.
- Show methodology version used for each recommendation run.
```

### 14C.7 Reproducibility

Every result must be reproducible from a snapshot.

Store:

```text
- data snapshot hash;
- model version;
- prompt versions;
- scoring configuration;
- simulation configuration;
- timestamp;
- approved question versions.
```

### 14C.8 Security

At minimum:

```text
- Rate-limit public APIs.
- Validate all LLM JSON outputs.
- Sanitize source text before rendering.
- Protect admin routes.
- Keep API keys server-side only.
- Add audit logs for admin edits.
```

### 14C.9 Public feedback loop

Add a mechanism for users to report:

```text
- biased question wording;
- wrong translation;
- wrong party classification;
- missing source;
- outdated party lineage;
- incorrect politician membership.
```

Store feedback in:

```text
public_feedback_reports
```

Fields:

```text
id
related_entity_type
related_entity_id
report_type
message
created_at
status
admin_notes
```

### 14C.10 Analytics without manipulation

Product analytics should measure usability, not political persuasion.

Allowed:

```text
- completion rate;
- question drop-off;
- time per question;
- chart interactions;
- evidence drawer opens;
- methodology page views.
```

Avoid:

```text
- optimizing wording to push users toward a party;
- A/B testing politically loaded framings;
- hiding uncertainty to increase conversion.
```

---

## 15. Admin / Review UI

MVP must include a basic admin panel.

Admin can review:

- LLM topic classification;
- generated question;
- neutrality score;
- source links;
- party-position inference;
- party-lineage edges;
- candidate volatility flags.

Review statuses:

```text
draft
llm_generated
needs_review
approved
rejected
deprecated
```

No question should become public in MVP unless `approved`.

---

## 16. API Endpoints

### Public API

```http
GET /api/topics
GET /api/questions/next?session_id=...
POST /api/answers
GET /api/results/{session_id}
GET /api/methodology
GET /api/party/{party_id}/evidence
```

### Admin API

```http
POST /api/admin/ingest/knesset
POST /api/admin/llm/classify
POST /api/admin/llm/generate-questions
GET /api/admin/review/items
POST /api/admin/review/{item_id}/approve
POST /api/admin/review/{item_id}/reject
POST /api/admin/lineage/approve
```

---

## 17. Scoring Output Schema

Every recommendation run should return:

```json
{
  "parties": [
    {
      "party_id": "...",
      "name": "...",
      "match_score": 0.72,
      "confidence": 0.81,
      "evidence_strength": 0.88,
      "volatility": 0.12,
      "coverage": 0.76,
      "is_new_party": false,
      "explanation": "...",
      "top_agreements": ["..."],
      "top_disagreements": ["..."],
      "weak_evidence_topics": ["..."]
    }
  ],
  "representation_gap": {
    "has_gap": true,
    "explanation": "...",
    "best_party_by_topic": [
      {"topic": "economy_taxes", "party": "Party A"},
      {"topic": "judiciary", "party": "Party B"}
    ]
  }
}
```

---

## 18. Implementation Phases

### Phase 1 — Skeleton

Build:

- FastAPI backend;
- Next.js frontend;
- PostgreSQL schema;
- Docker Compose;
- health checks;
- seed topics;
- mock parties/questions.

Deliverable:

```text
App runs locally. User can answer mock questions and get dummy results.
```

### Phase 2 — Core scoring with mock data

Build:

- user sessions;
- answers;
- salience weights;
- party positions;
- match score;
- confidence score;
- representation gap.

Deliverable:

```text
User completes 8–15 questions and gets ranked parties with confidence.
```

### Phase 3 — Adaptive questionnaire

Build:

- current top-party computation;
- next-question heuristic;
- topic diversity penalty;
- stop condition.

Deliverable:

```text
Question sequence adapts to user answers.
```

### Phase 4 — Lineage and volatility

Build:

- political brands;
- party instances;
- lineage edges;
- candidate history;
- candidate volatility;
- party volatility;
- new-party scoring.

Deliverable:

```text
New parties can be scored with low confidence using candidate history, lineage, and declared positions.
```

### Phase 5 — LLM abstraction and audit storage

Build:

- LLM provider interface;
- prompt versioning;
- LLM run storage;
- JSON validation;
- admin review screen.

Deliverable:

```text
LLM outputs can be generated, stored, inspected, approved, or rejected.
```

### Phase 6 — Real ingestion hooks

Build placeholder or partial importers for:

- Knesset OData;
- Open Knesset / Hasadna data.

Deliverable:

```text
Ingestion service architecture exists and can import normalized mock or real data later.
```

### Phase 7 — UX polish

Build:

- neutral onboarding;
- question cards with context;
- evidence expandable sections;
- results explanations;
- methodology page.

Deliverable:

```text
MVP is usable by non-technical users.
```

### Phase 8 — Internationalisation (i18n): English, Hebrew, Russian

**Status: partially complete — UI shell translated, question/party content still English.**

#### What is done

- `frontend/locales/types.ts` — shared `Translations` TypeScript interface.
- `frontend/locales/en.ts`, `he.ts`, `ru.ts` — full translations of all static UI strings.
- `frontend/lib/i18n.tsx` — React Context with `I18nProvider`, `useT()` hook, `useLang()` hook.
  - Language detected from `localStorage` key `sv_lang`, falling back to browser `navigator.language`.
  - `<html lang>` and `<html dir>` updated automatically (Hebrew uses `dir="rtl"`).
- `frontend/components/LanguageSwitcher.tsx` — EN / עב / РУ toggle button in the header.
- All four pages (`/`, `/questionnaire`, `/results`, `/methodology`) consume `useT()`.

#### What still needs work

1. **Question content**: `question_text_he` and `question_text_ru` fields exist in the DB schema
   and seed data but the questionnaire page currently always renders `question_text_en`.
   Update the questionnaire page to select the correct field based on active language:
   ```ts
   const questionText =
     lang === "he" ? question.question_text_he :
     lang === "ru" ? question.question_text_ru :
     question.question_text_en;
   ```

2. **Party names / explanations**: Party mock data has only English names.
   Add `name_he`, `name_ru`, and `explanation_he`, `explanation_ru` to the `party_instances`
   and `political_brands` seed data and return the correct language from the results API.

3. **Topic names**: `topics` table already has `name_he` and `name_ru` columns and seed data.
   The questionnaire `topic_slug` badge should be replaced with the localised topic name
   (requires the API to return it, or the frontend to look it up from a `/api/topics` cache).

4. **RTL layout refinements**: Hebrew (`dir="rtl"`) flips some CSS flex-row UIs correctly via
   Tailwind's logical properties, but some explicit `left`/`right` CSS may need adjustment.
   Use Tailwind's `rtl:` variant or logical properties (`ms-`, `me-`, `ps-`, `pe-`) where needed.

5. **Political/legal term glossary**: Politically sensitive terms should be translated consistently.
   Create `frontend/locales/glossary.ts` mapping canonical term slugs to translations in all
   three languages. Reference it from question context notes and methodology explanations.

6. **Missing locales for future pages**: Any new page added after Phase 8 must add its strings
   to all three locale files and to the `Translations` interface before the page goes live.

#### Implementation rules for future agents

- Never add a hardcoded UI string to a `.tsx` file. Always add it to all three locale files first.
- Never assume LTR layout. Default to logical Tailwind properties (e.g., `ms-4` not `ml-4`).
- Hebrew strings must be reviewed by a native speaker before public release.
- Russian strings must be reviewed by a native speaker before public release.
- Do not use machine translation for politically sensitive terms (party names, policy axes,
  legal and constitutional vocabulary). Use a verified glossary instead.
- Store the user's language preference in `localStorage` key `sv_lang`.
  Do not send it to the backend or expose it in analytics without consent.

---

## 19. Acceptance Criteria

The MVP is acceptable when:

```text
1. User can start an anonymous session.
2. User can answer 8–15 adaptive questions.
3. User can mark question importance.
4. App returns ranked parties.
5. Each party has match score, confidence, evidence strength, volatility, and explanation.
6. New parties appear with lower confidence, not excluded.
7. Results include representation gap.
8. Admin can review LLM-generated questions/classifications.
9. All LLM outputs are stored and auditable.
10. Methodology page explains scoring and limitations.
11. No UI copy tells users whom to vote for.
12. Knesset/election simulation works with mock polling data and produces probabilistic seat ranges.
13. Simulation UI shows assumptions, uncertainty, threshold risk, and coalition scenarios.
14. Every political claim in the UI can be traced to source evidence or marked as low-confidence inferred analysis.
15. Privacy, localization, accessibility, and neutrality-audit requirements are represented in architecture.
```

---

## 20. Coding-Agent Rules

1. Prefer simple, working MVP over complex unfinished architecture.
2. Keep scoring explainable.
3. Do not hide uncertainty.
4. Do not conflate party name with party identity.
5. Do not treat new-party platforms as equal to voting history.
6. Do not show party recommendations before the user finishes answering.
7. Do not release LLM-generated questions without review status.
8. Store LLM outputs with prompt version and input hash.
9. Keep data model extensible for real Knesset ingestion.
10. Write tests for scoring, confidence, volatility, and adaptive question selection.
11. Do not hardcode political assumptions in UI text.
12. Use neutral wording for all questions and explanations.
13. Keep personal matching separate from election/coalition simulation.
14. Never turn simulation output into strategic voting advice.
15. Always show data cutoff dates and assumptions for simulations.
16. Build privacy, localization, accessibility, and auditability into the architecture from the start.

---

## 21. First Coding Milestone

Build local mock MVP with:

```text
5 parties
20 policy items
40 questions
10 persons/candidates
party lineage examples
candidate volatility examples
adaptive questionnaire
results page
admin review page
mock polling data
Knesset seat simulation
coalition scenario visualization
```

The first milestone should work without real external data and without real LLM calls. Use mock LLM outputs and mocked data. Real ingestion and live LLM calls come later.

---

## 22. Key Warning

Do not build a simplistic quiz that maps answers directly to parties.

The desired architecture is:

```text
user preferences
        ↓
policy axes
        ↓
party latent positions
        ↓
evidence strength
        ↓
volatility / uncertainty
        ↓
transparent probabilistic recommendation
```

The MVP may use simple formulas internally, but it must preserve this conceptual structure.
