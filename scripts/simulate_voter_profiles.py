"""
Voter Profile Simulation Script
================================
Simulates real questionnaire sessions with predefined voter profiles and
analyses results to verify the matching algorithm.

Usage:
    uv run python scripts/simulate_voter_profiles.py
    uv run python scripts/simulate_voter_profiles.py --profile right_wing
    uv run python scripts/simulate_voter_profiles.py --base-url http://localhost:8000

Profiles:
    right_wing          Strong nationalist / security-first / religious
    center_right        Center-right liberal nationalist
    left_wing           Social-democratic / secular / two-state
    liberal             Civil rights / secular / free market
    religious           Ultra-Orthodox / religious law / anti-reform
    secular_progressive Progressive / LGBTQ+ / environment / anti-religion
    center_neutral      Middle of the road, no strong opinion

Each profile maps topic_slugs → answer_value (-1..+1, +salience 0.5|1|2).
After running, prints a ranked table of top-5 party matches with confidence
and flags if the expected top party is not in position 1-2.
"""
import argparse
import json
import sys
import time
import uuid
from dataclasses import dataclass, field
from typing import Optional

try:
    import httpx
except ImportError:
    print("ERROR: httpx not installed. Run: uv add httpx")
    sys.exit(1)

BASE_URL = "http://localhost:8000"

# ─────────────────────────────────────────────────────────────────────────────
# Voter profiles
# Each profile is a dict: topic_slug → (answer_value, salience)
# answer_value: -1 = strongly oppose, +1 = strongly support (positive axis pole)
# salience: 0.5 = not important, 1.0 = neutral, 2.0 = very important
#
# Topic slugs (from seed data):
#   security, judiciary, religion_state, settlements, economy_taxes,
#   healthcare, education, civil_rights, housing, welfare,
#   military_service, governance_corruption, environment, transport,
#   cost_of_living
# ─────────────────────────────────────────────────────────────────────────────

PROFILES: dict[str, dict[str, tuple[float, float]]] = {

    "right_wing": {
        # Pro-judicial reform, pro-settlement, nationalist security
        "judiciary":            (+0.85, 2.0),   # support limiting Supreme Court
        "settlements":          (+0.80, 2.0),   # support settlement expansion
        "security":             (+0.70, 2.0),   # hawkish security
        "religion_state":       (+0.60, 1.5),   # religious parties' power OK
        "military_service":     (+0.50, 1.5),   # some exemptions for Haredim
        "economy_taxes":        (+0.40, 1.0),   # prefer lower taxes / free market
        "governance_corruption": (-0.30, 0.5),  # less concerned
        "civil_rights":         (+0.30, 0.5),   # traditional values
        "environment":          (-0.20, 0.5),   # growth over environment
        "welfare":              (+0.20, 0.5),
        "healthcare":           (+0.10, 0.5),
        "housing":              (+0.20, 0.5),
        "education":            (+0.40, 1.0),
    },

    "center_right": {
        # Liberal nationalist — supports some judicial oversight but not full reform
        "judiciary":            (+0.30, 1.5),
        "settlements":          (+0.40, 1.0),
        "security":             (+0.50, 2.0),
        "religion_state":       (-0.20, 1.5),   # civil marriage, religious pluralism
        "military_service":     (-0.60, 2.0),   # universal military service
        "economy_taxes":        (+0.30, 1.0),
        "governance_corruption": (-0.60, 1.5),
        "civil_rights":         (-0.20, 1.0),
        "environment":          (-0.30, 0.5),
        "welfare":              (0.00, 0.5),
        "healthcare":           (-0.20, 1.0),
        "housing":              (-0.30, 1.0),
        "education":            (+0.20, 1.0),
    },

    "left_wing": {
        # Labour-left: two-state, social welfare, anti-judicial reform
        "judiciary":            (-0.80, 2.0),   # oppose limiting Supreme Court
        "settlements":          (-0.85, 2.0),   # oppose settlement expansion
        "security":             (-0.40, 1.0),   # diplomacy over force
        "religion_state":       (-0.85, 2.0),   # strong separation of religion & state
        "military_service":     (-0.70, 1.5),   # universal military service
        "economy_taxes":        (-0.65, 1.5),   # higher taxes, social programs
        "governance_corruption": (-0.80, 2.0),   # very concerned about corruption
        "civil_rights":         (-0.80, 2.0),   # strong civil rights / LGBTQ+
        "environment":          (-0.70, 1.5),   # carbon tax, renewables
        "welfare":              (-0.70, 1.5),
        "healthcare":           (-0.60, 1.5),
        "housing":              (-0.60, 1.5),
        "education":            (-0.60, 1.5),
    },

    "liberal": {
        # Liberal / Yesh Atid-style: free market + civil liberties + secular
        "judiciary":            (-0.50, 1.5),
        "settlements":          (-0.30, 1.0),
        "security":             (+0.20, 1.0),
        "religion_state":       (-0.80, 2.0),   # strong civil marriage, anti-monopoly
        "military_service":     (-0.70, 2.0),   # equal military service
        "economy_taxes":        (+0.20, 1.0),   # moderate free market
        "governance_corruption": (-0.70, 1.5),
        "civil_rights":         (-0.70, 2.0),
        "environment":          (-0.40, 1.0),
        "welfare":              (-0.20, 1.0),
        "healthcare":           (-0.30, 1.0),
        "housing":              (-0.40, 1.0),
        "education":            (-0.40, 1.5),
    },

    "religious": {
        # Ultra-Orthodox: Haredi exemption, religious law, social welfare
        "judiciary":            (+0.70, 1.5),   # weakening secular court fine
        "settlements":          (+0.60, 1.0),
        "security":             (+0.30, 0.5),
        "religion_state":       (+0.90, 2.0),   # religious institutions first
        "military_service":     (+0.90, 2.0),   # exemptions for Torah students
        "economy_taxes":        (-0.40, 1.0),   # welfare for communities
        "governance_corruption": (0.00, 0.5),
        "civil_rights":         (+0.80, 1.5),   # traditional values
        "environment":          (0.00, 0.5),
        "welfare":              (-0.60, 2.0),   # state support for Haredi families
        "healthcare":           (-0.30, 1.0),
        "housing":              (-0.50, 1.5),
        "education":            (+0.80, 2.0),   # yeshiva autonomy / funding
    },

    "secular_progressive": {
        # Very secular, progressive, green, anti-corruption
        "judiciary":            (-0.90, 2.0),
        "settlements":          (-0.90, 2.0),
        "security":             (-0.60, 1.0),
        "religion_state":       (-0.95, 2.0),   # strongest separation
        "military_service":     (-0.80, 2.0),
        "economy_taxes":        (-0.70, 1.5),
        "governance_corruption": (-0.90, 2.0),
        "civil_rights":         (-0.90, 2.0),
        "environment":          (-0.85, 2.0),
        "welfare":              (-0.75, 1.5),
        "healthcare":           (-0.70, 1.5),
        "housing":              (-0.70, 1.5),
        "education":            (-0.70, 1.5),
    },

    "center_neutral": {
        # Moderate: no strong opinions, neutral on most
        "judiciary":            (0.00, 1.0),
        "settlements":          (0.00, 1.0),
        "security":             (+0.20, 1.0),
        "religion_state":       (-0.20, 1.0),
        "military_service":     (-0.30, 1.0),
        "economy_taxes":        (0.00, 1.0),
        "governance_corruption": (-0.40, 1.0),
        "civil_rights":         (-0.20, 1.0),
        "environment":          (-0.20, 1.0),
        "welfare":              (-0.10, 1.0),
        "healthcare":           (-0.10, 1.0),
        "housing":              (-0.20, 1.0),
        "education":            (0.00, 1.0),
    },
}

# Expected top party per profile (for validation)
# Party name (Hebrew, displayed by the API)
EXPECTED_TOP: dict[str, list[str]] = {
    "right_wing":          ["Likud", "United Torah Judaism"],
    "center_right":        ["Yesh Atid", "Likud", "New Hope"],
    "left_wing":           ["Labor", "Yesh Atid"],
    "liberal":             ["Yesh Atid", "Labor"],
    "religious":           ["United Torah Judaism", "Likud"],
    "secular_progressive": ["Labor", "Yesh Atid"],
    "center_neutral":      [],  # any is OK
}


# ─────────────────────────────────────────────────────────────────────────────
# API helpers
# ─────────────────────────────────────────────────────────────────────────────

_RUNTIME_BASE_URL: list[str] = [BASE_URL]  # mutable container for runtime URL override


def _get_base_url() -> str:
    return _RUNTIME_BASE_URL[0]


def _post(client: httpx.Client, path: str, **kwargs) -> dict:
    resp = client.post(f"{_get_base_url()}{path}", **kwargs)
    resp.raise_for_status()
    return resp.json()


def _get(client: httpx.Client, path: str) -> dict:
    resp = client.get(f"{_get_base_url()}{path}")
    resp.raise_for_status()
    return resp.json()


def run_profile(
    client: httpx.Client,
    profile_name: str,
    profile: dict[str, tuple[float, float]],
    verbose: bool = False,
) -> dict:
    """
    Simulate a full session for a voter profile.
    Returns the raw results JSON.
    """
    session_id = str(uuid.uuid4())

    # 1. Create session
    _post(client, "/api/sessions", json={"session_id": session_id})

    # 2. Get questions one by one, answer based on profile
    answered = 0
    skipped = 0
    questions_seen: list[dict] = []
    max_questions = 30  # safety ceiling

    for _ in range(max_questions):
        resp = _get(client, f"/api/questions/next?session_id={session_id}")
        if resp is None or (isinstance(resp, dict) and not resp):
            break

        q = resp
        question_id = q["id"]
        policy_item_id = q["policy_item_id"]
        topic_slug = q.get("topic_slug", "")

        # Determine answer based on topic → profile mapping
        topic_mapping = profile.get(topic_slug)
        if topic_mapping:
            answer_value, salience = topic_mapping
        else:
            # Default: neutral answer with low salience
            answer_value = 0.0
            salience = 0.5

        # Apply answer_polarity (some questions invert the axis)
        polarity = q.get("answer_polarity", 1.0)
        effective_value = answer_value * (polarity if polarity else 1.0)
        # Clamp to [-1, +1]
        effective_value = max(-1.0, min(1.0, effective_value))

        # Salience must be exactly 0.5, 1.0, or 2.0 (API validation)
        if salience >= 1.8:
            salience = 2.0
        elif salience >= 0.8:
            salience = 1.0
        else:
            salience = 0.5

        if verbose:
            phase = q.get("phase", "?")
            text = q.get("question_text_en", "")[:60]
            print(f"  Q{answered+1:2d} [{phase}] [{topic_slug}] {text}…")
            print(f"       → answer={effective_value:+.2f} salience={salience}")

        _post(client, "/api/answers", json={
            "session_id": session_id,
            "question_id": question_id,
            "policy_item_id": policy_item_id,
            "answer_value": effective_value,
            "salience": salience,
        })

        questions_seen.append({
            "topic": topic_slug,
            "value": effective_value,
            "salience": salience,
            "text": q.get("question_text_en", "")[:60],
        })
        answered += 1

        # Check if we can stop
        can_show = q.get("can_show_results", False)
        stability = q.get("ranking_stability", 0)
        if can_show and answered >= 15:
            if verbose:
                print(f"  Converged after {answered} questions (stability={stability:.3f})")
            break

    # 3. Get results
    results = _get(client, f"/api/results/{session_id}")
    results["_session_id"] = session_id
    results["_questions_answered"] = answered
    results["_questions_seen"] = questions_seen
    return results


def print_results(profile_name: str, results: dict, verbose: bool = False):
    """Print a formatted result table for a profile."""
    parties = results.get("parties", [])
    answered = results.get("_questions_answered", "?")

    SEP = "─" * 70
    print(f"\n{'═' * 70}")
    print(f" PROFILE: {profile_name.upper()}   (answered {answered} questions)")
    print(SEP)
    print(f"  {'#':<3} {'Party':<30} {'Match':>6} {'Confidence':>11} {'Evidence':>9} {'Coverage':>9}")
    print(SEP)

    for i, p in enumerate(parties[:8], 1):
        party_name = p.get("name_he") or p.get("name", "?")
        match = p.get("match_score", 0) * 100
        conf = p.get("confidence", 0) * 100
        ev = p.get("evidence_strength", 0) * 100
        cov = p.get("coverage", 0) * 100
        new_flag = " ⚠NEW" if p.get("is_new_party") else ""
        sect_flag = " §" if p.get("is_sectoral") else ""
        print(f"  {i:<3} {party_name:<30} {match:5.1f}%  {conf:8.1f}%  {ev:7.1f}%  {cov:7.1f}%{new_flag}{sect_flag}")

    # Validation
    expected = EXPECTED_TOP.get(profile_name, [])
    if expected:
        top_names = [p.get("name", "") for p in parties[:3]]
        ok = any(e in top_names for e in expected)
        status = "✓ PASS" if ok else "✗ FAIL"
        print(SEP)
        print(f"  Expected top: {expected}")
        print(f"  Got top-3:    {top_names}")
        print(f"  Validation:   {status}")

    # Representation gap
    gap = results.get("representation_gap", {})
    if gap.get("has_gap"):
        print(SEP)
        print(f"  ⚠ Representation gap: {gap.get('explanation', '')[:60]}")

    # Confidence breakdown for top party
    if verbose and parties:
        p = parties[0]
        bd = p.get("confidence_breakdown", {})
        if bd:
            print(SEP)
            print(f"  Confidence breakdown for [{p.get('name', '?')}]:")
            for k, v in bd.items():
                bar_fill = int(v * 20)
                bar = "█" * bar_fill + "░" * (20 - bar_fill)
                print(f"    {k:<25} [{bar}] {v * 100:.1f}%")

    if verbose and results.get("_questions_seen"):
        print(SEP)
        print("  Questions answered:")
        for q in results["_questions_seen"]:
            print(f"    [{q['topic']:20}] {q['value']:+.2f} sal={q['salience']} | {q['text']}")


def main():
    parser = argparse.ArgumentParser(description="Simulate voter profiles and test matching algorithm")
    parser.add_argument("--profile", type=str, help="Run only this profile", default=None)
    parser.add_argument("--base-url", type=str, default=BASE_URL, help="API base URL")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show question details")
    parser.add_argument("--json-out", type=str, help="Save results JSON to file")
    args = parser.parse_args()

    _RUNTIME_BASE_URL[0] = args.base_url

    profiles_to_run = (
        {args.profile: PROFILES[args.profile]}
        if args.profile and args.profile in PROFILES
        else PROFILES
    )

    if args.profile and args.profile not in PROFILES:
        print(f"Unknown profile '{args.profile}'. Available: {list(PROFILES.keys())}")
        sys.exit(1)

    all_results = {}
    with httpx.Client(timeout=60.0) as client:
        # Sanity-check: can we reach the API?
        try:
            resp = client.get(f"{_get_base_url()}/api/topics")
            resp.raise_for_status()
        except Exception as e:
            print(f"ERROR: Cannot reach API at {BASE_URL}: {e}")
            print("Make sure the backend is running: uv run uvicorn backend.app.main:app --reload")
            sys.exit(1)

        for name, profile in profiles_to_run.items():
            print(f"\nRunning profile: {name}…", end="", flush=True)
            try:
                results = run_profile(client, name, profile, verbose=args.verbose)
                all_results[name] = results
                print(f" done ({results.get('_questions_answered', '?')} questions)")
                print_results(name, results, verbose=args.verbose)
            except httpx.HTTPError as e:
                print(f"\nERROR for profile {name}: {e}")
                if hasattr(e, 'response') and e.response is not None:
                    print(f"  Response: {e.response.text[:200]}")

    # Summary validation
    print(f"\n{'═' * 70}")
    print(" SUMMARY")
    print("─" * 70)
    passes = fails = 0
    for name, results in all_results.items():
        expected = EXPECTED_TOP.get(name, [])
        if not expected:
            print(f"  {name:<25}  (no expected top defined)")
            continue
        parties = results.get("parties", [])
        top_names = [p.get("name", "") for p in parties[:3]]
        ok = any(e in top_names for e in expected)
        status = "✓" if ok else "✗"
        top = parties[0].get("name", "?") if parties else "?"
        conf = parties[0].get("confidence", 0) * 100 if parties else 0
        match = parties[0].get("match_score", 0) * 100 if parties else 0
        print(f"  {status} {name:<25}  top={top:<25} {match:.0f}% match  {conf:.0f}% conf")
        if ok:
            passes += 1
        else:
            fails += 1

    print("─" * 70)
    print(f"  Result: {passes} passed, {fails} failed")

    if args.json_out:
        with open(args.json_out, "w", encoding="utf-8") as f:
            json.dump(all_results, f, ensure_ascii=False, indent=2, default=str)
        print(f"\n  Results saved to: {args.json_out}")


if __name__ == "__main__":
    main()








