"""
Cleanup script: removes obviously mislinked LLM-generated questions.

A question is "mislinked" if its English text contains strong topical keywords
that clearly belong to a DIFFERENT policy area than the policy item it is
linked to.

Also trims any policy item that has more than MAX_PER_PI servable llm_generated
questions to prevent the questionnaire from being dominated by one topic.

Run with:
    uv run python scripts/cleanup_mislinked_questions.py [--dry-run]
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.app.db.session import SessionLocal
from backend.app.models.question import Question
from backend.app.models.policy_item import PolicyItem
from backend.app.models.topic import Topic
from backend.app.models.user_answer import UserAnswer
from backend.app.models.policy_item import ReviewStatus
from collections import defaultdict

DRY_RUN = "--dry-run" in sys.argv
MAX_PER_PI = 3   # keep at most this many llm_generated questions per policy item

# Keywords that indicate a question clearly belongs to a DIFFERENT topic.
# Tuple: (required_keyword_in_question_text, forbidden_pi_title_keywords)
# If a question contains the required_keyword AND it is linked to a pi whose
# title matches one of the forbidden_pi_title_keywords, it is mislinked.
MISMATCH_RULES: list[tuple[str, list[str]]] = [
    # Haredi/draft questions under non-military / non-religion policy items
    ("haredi", [
        "pm under indictment", "basic necessities", "gaza ceasefire", "two-state",
        "civil marriage", "freedom of press", "attorney general", "state comptroller",
        "carbon tax", "public transit", "income tax", "housing market",
        "rent control", "affordable housing", "kashrut", "vat exemption",
        "school choice", "mental health", "public vs private", "welfare spending",
        "child allowance", "offshore gas", "override clause", "judicial review",
        "judicial appointments", "arab minority", "lgbtq", "anti-discrimination",
        "settlement expansion", "west bank annexation", "evacuation",
        "mandatory service length",
    ]),
    # Gaza civilian administration questions under non-security policy items
    ("civilian administration in gaza", [
        "carbon tax", "freedom of press", "income tax", "rent control",
        "basic necessities", "mental health", "welfare spending", "child allowance",
        "judicial review", "judicial appointments", "kashrut", "lgbtq",
        "attorney general", "state comptroller",
    ]),
    ("israeli administration in gaza", [
        "carbon tax", "freedom of press", "income tax",
    ]),
    # Hospital/healthcare questions under clearly non-healthcare policy items
    ("public hospitals", [
        "defense budget", "state comptroller", "kashrut", "carbon tax",
        "attorney general", "income tax", "freedom of press",
        "pm under indictment", "basic necessities",
    ]),
    # Housing questions under non-housing policy items
    ("affordable housing for young families", [
        "freedom of press", "kashrut", "carbon tax", "judicial review",
        "attorney general", "state comptroller",
    ]),
]


def title_matches(pi_title: str, keywords: list[str]) -> bool:
    t = (pi_title or "").lower()
    return any(kw in t for kw in keywords)


def is_mislinked(q_text: str, pi_title: str) -> bool:
    qt = q_text.lower()
    for keyword, forbidden_pi_words in MISMATCH_RULES:
        if keyword in qt and title_matches(pi_title, forbidden_pi_words):
            return True
    return False


def main() -> None:
    db = SessionLocal()
    mode = "DRY RUN" if DRY_RUN else "LIVE"
    print(f"=== Cleanup mislinked questions [{mode}] ===\n")
    try:
        qs = db.query(Question).all()
        pi_by_id: dict = {}
        for q in qs:
            if q.policy_item_id and q.policy_item_id not in pi_by_id:
                pi = db.query(PolicyItem).filter(PolicyItem.id == q.policy_item_id).first()
                pi_by_id[q.policy_item_id] = pi

        to_delete: list[Question] = []

        # Rule 1: clearly mislinked questions (any status — a Haredi question
        # linked to "Gaza Ceasefire" is wrong no matter how it was approved)
        for q in qs:
            pi = pi_by_id.get(q.policy_item_id)
            pi_title = pi.title if pi else ""
            if is_mislinked(q.question_text_en, pi_title):
                to_delete.append(q)
                print(f"  MISMATCH [{pi_title[:35]:35s}]: {q.question_text_en[:70]}")

        # Rule 2: trim excess llm_generated per policy item (keep approved + max MAX_PER_PI llm_generated)
        by_pi: dict = defaultdict(list)
        for q in qs:
            by_pi[q.policy_item_id].append(q)

        delete_ids = {q.id for q in to_delete}
        for pi_id, qlist in by_pi.items():
            pi = pi_by_id.get(pi_id)
            pi_title = pi.title if pi else "ROOT"
            llm_qs = [q for q in qlist if q.human_review_status == ReviewStatus.llm_generated
                      and q.id not in delete_ids]
            excess = llm_qs[MAX_PER_PI:]
            for q in excess:
                delete_ids.add(q.id)
                to_delete.append(q)
                print(f"  EXCESS [{pi_title[:35]:35s}] (>{MAX_PER_PI} llm): {q.question_text_en[:70]}")

        print(f"\nTotal to delete: {len(set(q.id for q in to_delete))}")
        if DRY_RUN:
            print("(dry run — nothing deleted)")
            return

        deleted = 0
        seen = set()
        for q in to_delete:
            if q.id in seen:
                continue
            seen.add(q.id)
            db.query(UserAnswer).filter(UserAnswer.question_id == q.id).delete()
            db.query(Question).filter(Question.id == q.id).delete()
            deleted += 1

        db.commit()
        print(f"Deleted {deleted} questions.")
    except Exception as exc:
        db.rollback()
        print(f"ERROR: {exc}", file=sys.stderr)
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()


