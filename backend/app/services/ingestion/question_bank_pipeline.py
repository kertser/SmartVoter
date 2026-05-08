"""
Question Bank Pipeline — Bulk pre-generation of a diverse question graph/tree.

PURPOSE
-------
Instead of generating questions on-the-fly during questionnaire sessions,
this pipeline pre-generates a large bank of questions (up to
settings.max_questions_to_generate, default 300) that are stored in the DB
and organised into a tree structure:

    Depth 0 — Topic root questions (is_root_question=True)
               One broad "values discovery" question per topic.

    Depth 1 — Policy-item follow-ups (parent = topic root)
               Specific closed-proposition questions for each policy item
               within the topic. These are the "meat" of the bank.

    Depth 2 — Directional drill-downs (parent = policy-item question)
               Generated for the two opposing directions a user might answer
               a depth-1 question (strong support vs. strong opposition).
               These surface as adaptive follow-ups when the selector detects
               high salience and a clear directional lean.

CURRENT-EVENTS AWARENESS
------------------------
Questions are generated with explicit awareness of the current date (May 2026)
and the current Israeli political landscape.

Topics that are NO LONGER relevant (as of May 2026) are excluded from
question generation:
  - Gaza hostage situation: hostages have been released
  - Speculation about whether a ceasefire will happen: ceasefire is ongoing

Questions ARE expected to reflect current ongoing debates:
  - Haredi military draft implementation (law passed 2024, still fiercely contested)
  - Ongoing Gaza war reconstruction and post-war governance
  - Coalition budget cuts (healthcare, universities, welfare)
  - Housing crisis (record-high prices, insufficient supply)
  - Judicial reform implementation fallout
  - Cost-of-living crisis (food, energy, rent)
  - West Bank settlement expansion policy
  - Iran nuclear program threat

TREE STRUCTURE
--------------
Questions are linked via parent_question_id:

    Topic root (depth=0)
        ├── Policy-item Q (depth=1, topic scope)
        │       ├── "Strong support" drill-down (depth=2, trigger_answer_min=0.5)
        │       └── "Strong opposition" drill-down (depth=2, trigger_answer_max=-0.5)
        └── Policy-item Q (depth=1, topic scope)
                └── ...

The selector in selector.py already works correctly with this structure —
it uses topic_slug, evidence_quality, salience, and party separation without
needing to explicitly traverse the tree. The tree is primarily useful for:
  1. Organising questions in the admin UI
  2. Enabling future tree-aware selection (follow parent answer direction)
  3. Backup / export organisation

DEDUPLICATION
-------------
Before inserting a new question, the pipeline checks whether a semantically
similar question already exists (by comparing lowercase English text prefix)
to avoid generating near-duplicate questions.

Usage
-----
From admin panel: POST /api/admin/llm/generate-question-bank
Or directly:
    from backend.app.services.ingestion.question_bank_pipeline import run_question_bank_pipeline
    stats = run_question_bank_pipeline(db, settings, max_questions=300)
"""
import logging
import uuid
import hashlib
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy.orm import Session

from backend.app.models.policy_item import PolicyItem, ReviewStatus
from backend.app.models.question import Question, AnswerScaleType
from backend.app.models.topic import Topic
from backend.app.services.llm import get_llm_provider
from backend.app.services.llm.audit_service import AuditedLLMService
from backend.app.services.llm.question_format import check_question_format

if TYPE_CHECKING:
    from backend.app.config import Settings

logger = logging.getLogger(__name__)

# ── Global rate-limit guard ───────────────────────────────────────────────────
# Limits the number of in-flight LLM calls across ALL worker threads.
# Even with many ThreadPoolExecutor workers, at most _MAX_CONCURRENT_LLM
# calls will actually hit the API at the same time.
# Adjust down if you still get 429s; adjust up if you have a higher tier.
_MAX_CONCURRENT_LLM = 3
_llm_semaphore = threading.Semaphore(_MAX_CONCURRENT_LLM)
# Minimum gap (seconds) between each token acquisition to spread bursts.
_LLM_REQUEST_GAP = 0.5

# ── Current-events context injected into all generation prompts ───────────────

CURRENT_DATE_CONTEXT = """
CURRENT DATE: May 2026, Israel.

RECENTLY RESOLVED — do NOT generate questions about these (they are no longer current):
- Gaza hostage release: All remaining hostages have been released. Do not generate
  questions specifically about "releasing the hostages" or "hostage deal negotiations"
  as a pending political decision. The Gaza war's aftermath and reconstruction ARE
  still relevant political issues.
- Ceasefire speculation: There is an ongoing ceasefire arrangement.

CURRENTLY RELEVANT Israeli political debates (May 2026) — questions SHOULD reflect:
- Haredi military draft: The Haredi draft law was legislated in 2024 but
  implementation remains fiercely contested, with ongoing coalition disputes.
- Gaza aftermath: Who governs post-war Gaza? Israeli civilian administration role?
  Palestinian state? International forces? This is a live debate.
- Judicial reform implementation: The reform was partially legislated;
  court-government tensions are ongoing.
- Coalition budget cuts: Deep cuts to hospitals, universities, welfare programs
  are causing public protests and coalition instability.
- Housing crisis: Record-high housing prices, insufficient supply, young families
  unable to afford apartments — a top voter concern.
- Cost-of-living crisis: Food prices, energy, rent — already serious since 2023.
- West Bank settlement policy: continued expansion vs. international pressure.
- Iran nuclear program: Iranian nuclear capabilities and Israeli response options.
- Ultra-Orthodox economic participation: Employment incentives vs. yeshiva support.
- Education funding: State secular vs. religious school budget parity.
"""

# ── Deduplication helper ──────────────────────────────────────────────────────

def _question_fingerprint(text: str) -> str:
    """Short hash of the first 120 chars of lowercase text, used for deduplication."""
    normalized = text.lower().strip()[:120]
    return hashlib.md5(normalized.encode()).hexdigest()[:16]


def _is_duplicate(db: Session, question_en: str, policy_item_id: uuid.UUID | None) -> bool:
    """
    Return True if a near-identical question already exists in the DB.
    Checks both fingerprint match and simple prefix overlap for the same policy item.
    """
    fp = _question_fingerprint(question_en)
    # Check by fingerprint stored in llm_prompt_version (secondary field; low cost)
    prefix_80 = question_en.lower().strip()[:80]
    existing = (
        db.query(Question)
        .filter(Question.policy_item_id == policy_item_id)
        .all()
    )
    for q in existing:
        if q.question_text_en and q.question_text_en.lower().strip()[:80] == prefix_80:
            return True
    return False


# ── Root question generation helper ──────────────────────────────────────────

def _generate_root_question_worker(
    topic_data: dict,
    settings: "Settings",
    db_factory,
) -> dict:
    """
    Worker: generate ONE new depth-0 root question for a topic.
    Always creates a new question — never updates an existing one.
    Call multiple times (in parallel) to build a pool of root questions per topic.

    Returns a result dict with keys:
      action: "created" | "error"
      topic_id, topic_slug, question_id (if created), error (if error)
    """
    thread_db = db_factory()
    try:
        from backend.app.models.question import Question, AnswerScaleType
        from backend.app.models.policy_item import ReviewStatus
        from backend.app.services.llm.audit_service import AuditedLLMService
        from backend.app.services.llm.question_format import check_question_format

        topic_id = uuid.UUID(topic_data["id"])

        llm_raw = get_llm_provider(settings)
        svc = AuditedLLMService(llm_raw, thread_db)

        input_data = {
            "topic_name_en": topic_data["name_en"],
            "topic_name_he": topic_data.get("name_he", ""),
            "topic_name_ru": topic_data.get("name_ru") or "",
            "topic_description": topic_data.get("description") or f"Policy questions related to {topic_data['name_en']}",
            # Cache-bust so each parallel call generates a distinct question
            "_cache_bust": str(uuid.uuid4()),
        }

        with _llm_semaphore:
            time.sleep(_LLM_REQUEST_GAP)
            result = svc.generate_root_question(input_data, entity_id=topic_id)
        question_en = result.get("question_en") or result.get("question", "")
        if not question_en:
            return {"action": "error", "topic_id": str(topic_id), "topic_slug": topic_data["slug"],
                    "error": "LLM returned empty root question"}

        fmt = check_question_format(
            question_en=question_en,
            question_he=result.get("question_he", ""),
            question_ru=result.get("question_ru", ""),
        )
        if not fmt["is_valid"]:
            return {"action": "error", "topic_id": str(topic_id), "topic_slug": topic_data["slug"],
                    "error": f"open_ended: {fmt['issue']}"}

        # Deduplication check against existing root questions for this topic
        prefix = question_en.lower().strip()[:80]
        existing_roots = (
            thread_db.query(Question)
            .filter(
                Question.topic_id == topic_id,
                Question.is_root_question == True,  # noqa: E712
            )
            .all()
        )
        for eq in existing_roots:
            if eq.question_text_en and eq.question_text_en.lower().strip()[:80] == prefix:
                return {"action": "error", "topic_id": str(topic_id), "topic_slug": topic_data["slug"],
                        "error": "duplicate root question text"}

        neutrality_score = float(result.get("neutrality_score", 0.7))
        q = Question(
            id=uuid.uuid4(),
            is_root_question=True,
            topic_id=topic_id,
            policy_item_id=None,
            question_text_en=question_en,
            question_text_he=result.get("question_he", ""),
            question_text_ru=result.get("question_ru"),
            answer_scale_type=AnswerScaleType.likert_5,
            neutrality_score=neutrality_score,
            llm_prompt_version=result.get("_prompt_version", "bank-root-v1.0"),
            human_review_status=ReviewStatus.needs_review,
            tree_depth=0,
            is_stale=False,
        )
        thread_db.add(q)
        thread_db.commit()
        thread_db.refresh(q)
        return {"action": "created", "topic_id": str(topic_id), "topic_slug": topic_data["slug"],
                "question_id": str(q.id)}
    except Exception as exc:
        thread_db.rollback()
        logger.error("question_bank root worker failed for topic %s: %s", topic_data.get("slug"), exc)
        return {"action": "error", "topic_id": topic_data["id"], "topic_slug": topic_data.get("slug", ""),
                "error": str(exc)}
    finally:
        thread_db.close()


# ── Per-item generation helpers ────────────────────────────────────────────────

def _generate_depth1_question(
    pi_data: dict,
    parent_id: uuid.UUID | None,
    settings: "Settings",
    db_factory,
) -> dict:
    """
    Worker: generate a depth-1 (policy-item) question for a single policy item.
    Creates its own DB session.
    """
    thread_db = db_factory()
    try:
        llm_raw = get_llm_provider(settings)
        llm = AuditedLLMService(llm_raw, thread_db)
        pi_id = pi_data["id"]

        input_data = {
            "title": pi_data["title"],
            "description": pi_data["description"],
            "directional_axis": pi_data["directional_axis"],
            "current_context": CURRENT_DATE_CONTEXT,
        }

        with _llm_semaphore:
            time.sleep(_LLM_REQUEST_GAP)
            result = llm.generate_question_bank_item(input_data, entity_id=pi_id)

        question_en = result.get("question_en") or result.get("question", "")
        if not question_en:
            return {"created": False, "reason": "empty_question", "policy_item_id": str(pi_id)}

        fmt = check_question_format(
            question_en=question_en,
            question_he=result.get("question_he", ""),
            question_ru=result.get("question_ru", ""),
        )
        if not fmt["is_valid"]:
            logger.warning(
                "question_bank: rejected open-ended Q for policy_item %s — %s",
                pi_id, fmt["issue"],
            )
            return {"created": False, "reason": f"open_ended:{fmt['issue']}", "policy_item_id": str(pi_id)}

        if _is_duplicate(thread_db, question_en, pi_id):
            return {"created": False, "reason": "duplicate", "policy_item_id": str(pi_id)}

        neutrality_score = (
            0.4 if result.get("is_loaded")
            else 0.9 if result.get("neutrality_risk") == "low"
            else 0.7 if result.get("neutrality_risk") == "medium"
            else 0.5
        )

        q = Question(
            id=uuid.uuid4(),
            policy_item_id=pi_id,
            topic_id=pi_data.get("topic_id"),
            is_root_question=False,
            question_text_en=question_en,
            question_text_he=result.get("question_he", ""),
            question_text_ru=result.get("question_ru", ""),
            answer_scale_type=AnswerScaleType.likert_5,
            neutrality_score=neutrality_score,
            llm_prompt_version=result.get("_prompt_version", "bank-v1.0"),
            answer_polarity=1.0,
            human_review_status=ReviewStatus.needs_review,
            # Tree fields
            parent_question_id=parent_id,
            tree_depth=1,
            subtopic_tag=result.get("subtopic_tag") or pi_data.get("directional_axis", "")[:50] or None,
            generation_date=datetime.now(timezone.utc),
            is_stale=False,
        )
        thread_db.add(q)
        thread_db.commit()
        thread_db.refresh(q)

        return {
            "created": True,
            "question_id": str(q.id),
            "question_en": question_en,
            "policy_item_id": str(pi_id),
            "depth": 1,
        }
    except Exception as exc:
        thread_db.rollback()
        logger.error("question_bank depth-1 worker failed for %s: %s", pi_data["id"], exc)
        return {"created": False, "error": str(exc), "policy_item_id": str(pi_data["id"])}
    finally:
        thread_db.close()


def _generate_depth2_followup(
    pi_data: dict,
    parent_q_id: uuid.UUID,
    direction: str,          # "support" or "oppose"
    trigger_min: float | None,
    trigger_max: float | None,
    settings: "Settings",
    db_factory,
) -> dict:
    """
    Worker: generate a depth-2 directional drill-down question.
    direction: "support" (trigger when parent answer >= 0.5) or
               "oppose"  (trigger when parent answer <= -0.5).
    """
    thread_db = db_factory()
    try:
        llm_raw = get_llm_provider(settings)
        llm = AuditedLLMService(llm_raw, thread_db)
        pi_id = pi_data["id"]

        direction_hint = (
            f"deeper follow-up for users who STRONGLY SUPPORT the {pi_data['directional_axis']} policy axis"
            if direction == "support"
            else f"deeper follow-up for users who STRONGLY OPPOSE the {pi_data['directional_axis']} policy axis"
        )

        input_data = {
            "title": pi_data["title"],
            "description": pi_data["description"],
            "directional_axis": pi_data["directional_axis"],
            "direction_hint": direction_hint,
            "current_context": CURRENT_DATE_CONTEXT,
        }

        with _llm_semaphore:
            time.sleep(_LLM_REQUEST_GAP)
            result = llm.generate_question_bank_item(input_data, entity_id=pi_id)

        question_en = result.get("question_en") or result.get("question", "")
        if not question_en:
            return {"created": False, "reason": "empty_question"}

        fmt = check_question_format(
            question_en=question_en,
            question_he=result.get("question_he", ""),
            question_ru=result.get("question_ru", ""),
        )
        if not fmt["is_valid"]:
            return {"created": False, "reason": f"open_ended:{fmt['issue']}"}

        if _is_duplicate(thread_db, question_en, pi_id):
            return {"created": False, "reason": "duplicate"}

        neutrality_score = (
            0.4 if result.get("is_loaded")
            else 0.9 if result.get("neutrality_risk") == "low"
            else 0.7 if result.get("neutrality_risk") == "medium"
            else 0.5
        )

        q = Question(
            id=uuid.uuid4(),
            policy_item_id=pi_id,
            topic_id=pi_data.get("topic_id"),
            is_root_question=False,
            question_text_en=question_en,
            question_text_he=result.get("question_he", ""),
            question_text_ru=result.get("question_ru", ""),
            answer_scale_type=AnswerScaleType.likert_5,
            neutrality_score=neutrality_score,
            llm_prompt_version=result.get("_prompt_version", "bank-depth2-v1.0"),
            answer_polarity=1.0,
            human_review_status=ReviewStatus.needs_review,
            # Tree fields
            parent_question_id=parent_q_id,
            tree_depth=2,
            trigger_answer_min=trigger_min,
            trigger_answer_max=trigger_max,
            subtopic_tag=f"{direction}_{pi_data.get('directional_axis', '')[:40]}",
            generation_date=datetime.now(timezone.utc),
            is_stale=False,
        )
        thread_db.add(q)
        thread_db.commit()
        thread_db.refresh(q)

        return {
            "created": True,
            "question_id": str(q.id),
            "question_en": question_en,
            "direction": direction,
            "depth": 2,
        }
    except Exception as exc:
        thread_db.rollback()
        logger.error("question_bank depth-2 worker failed: %s", exc)
        return {"created": False, "error": str(exc)}
    finally:
        thread_db.close()


# ── Staleness marking ─────────────────────────────────────────────────────────

# Keywords found in question text that indicate stale content
_STALE_KEYWORDS = [
    # These hostage/ceasefire references are stale as of May 2026
    "hostage deal",
    "release the hostages",
    "free the hostages",
    "hostage negotiations",
    "ceasefire negotiations",
    "will there be a ceasefire",
    "achieve a ceasefire",
    # Generic stale markers
    "upcoming election",     # no upcoming election currently
]


def mark_stale_questions(db: Session) -> int:
    """
    Scan all questions and mark those containing stale-event keywords as is_stale=True.
    Returns the number of questions marked stale.
    """
    questions = db.query(Question).filter(Question.is_stale == False).all()  # noqa: E712
    marked = 0
    for q in questions:
        text_lower = (q.question_text_en or "").lower()
        if any(kw in text_lower for kw in _STALE_KEYWORDS):
            q.is_stale = True
            marked += 1
            logger.info(
                "Marked question %s as stale (keyword match): %.60s…",
                q.id, q.question_text_en,
            )
    if marked:
        db.commit()
    return marked


# ── Main pipeline ─────────────────────────────────────────────────────────────

def run_question_bank_pipeline(
    db: Session,
    settings: "Settings",
    max_questions: int | None = None,
    depth_levels: int = 2,
    max_workers: int | None = None,
    topics_filter: list[str] | None = None,
    force_regenerate: bool = False,
    root_questions_per_topic: int = 3,
    progress_callback=None,
) -> dict:
    """Bulk-generate a diverse question bank organised as a tree:
      - Depth 0: topic root questions (root_questions_per_topic per topic)
      - Depth 1: policy-item questions (N per topic, up to budget)
      - Depth 2: directional drill-downs (for both support/oppose directions)

    Multiple root questions are generated per topic - they all go into the
    questionnaire pool and are served adaptively.

    All questions are saved to the DB with needs_review status.
    A staleness scan is run on all existing questions at the start.

    Args:
        max_questions: Total questions to generate (defaults to settings.max_questions_to_generate).
        depth_levels: 0=root only, 1=root+policy, 2=full tree (default).
        max_workers: Parallel LLM threads (defaults to settings.question_bank_max_workers).
        topics_filter: If set, only process topics with these slugs.
        force_regenerate: If True, generate root questions even if the topic already
                          has >= root_questions_per_topic. Also regenerates depth-1.
        root_questions_per_topic: How many root (depth-0) questions to target per topic.
        progress_callback: Optional callable(step: str, completed: int, total: int).

    Returns a stats dict with keys: created, skipped, errors, stale_marked, total_budget.
    """
    from backend.app.db.session import SessionLocal

    max_questions = max_questions or settings.max_questions_to_generate
    max_workers = max_workers or getattr(settings, "question_bank_max_workers", 3)
    # Cap workers: semaphore limits actual concurrency to _MAX_CONCURRENT_LLM anyway,
    # but keep thread pool bounded to avoid excessive memory usage.
    workers = min(max(1, max_workers), 10)

    def _db_factory():
        return SessionLocal()

    def _progress(step: str, completed: int, total: int):
        if progress_callback:
            progress_callback(step, completed, total)
        else:
            logger.info("question_bank [%s]: %d/%d", step, completed, total)

    # ── Step 0: Mark stale questions ─────────────────────────────────────────
    stale_marked = mark_stale_questions(db)
    _progress("stale_scan", stale_marked, stale_marked)

    # ── Step 1: Load topics ──────────────────────────────────────────────────
    topic_query = db.query(Topic)
    if topics_filter:
        topic_query = topic_query.filter(Topic.slug.in_(topics_filter))
    topics = topic_query.order_by(Topic.slug).all()

    if not topics:
        return {
            "created": 0, "skipped": 0, "errors": 0,
            "stale_marked": stale_marked, "total_budget": max_questions,
            "message": "No topics found. Seed topics first.",
        }

    n_topics = len(topics)

    # ── Step 2: Build pool of depth-0 root questions ─────────────────────────
    # Each topic gets root_questions_per_topic root questions. We compute how
    # many each topic still needs (target - existing_count) and generate only
    # the missing ones (unless force_regenerate, in which we always generate
    # root_questions_per_topic more regardless of existing count).
    topic_snapshots = [
        {
            "id": str(t.id),
            "slug": t.slug,
            "name_en": t.name_en,
            "name_he": t.name_he,
            "name_ru": t.name_ru,
            "description": t.description,
        }
        for t in topics
    ]

    # Build the work list: (topic_snapshot) repeated N times where N = how many to generate
    root_work: list[dict] = []
    for snap in topic_snapshots:
        tid = uuid.UUID(snap["id"])
        existing_count = db.query(Question).filter(
            Question.topic_id == tid,
            Question.is_root_question == True,  # noqa: E712
            Question.is_stale == False,  # noqa: E712
        ).count()
        if force_regenerate:
            # Always add root_questions_per_topic more (widen the pool)
            need = root_questions_per_topic
        else:
            need = max(0, root_questions_per_topic - existing_count)
        for _ in range(need):
            root_work.append(snap)

    root_created = root_errors = 0
    if root_work:
        _progress("root_generation", 0, len(root_work))
        with ThreadPoolExecutor(max_workers=min(workers, len(root_work))) as executor:
            futures_root = {
                executor.submit(
                    _generate_root_question_worker, snap, settings, _db_factory
                ): snap
                for snap in root_work
            }
            completed_root = 0
            for future in as_completed(futures_root):
                try:
                    res = future.result()
                    if res["action"] == "created":
                        root_created += 1
                    else:
                        root_errors += 1
                        logger.warning("root Q error for %s: %s", res.get("topic_slug"), res.get("error"))
                except Exception as exc:
                    root_errors += 1
                    logger.error("root Q future error: %s", exc)
                completed_root += 1
                _progress("root_generation", completed_root, len(root_work))

    # Reload root map: pick first non-stale root per topic as parent for depth-1
    topic_root_map: dict[uuid.UUID, uuid.UUID | None] = {}
    for topic in topics:
        root_q = (
            db.query(Question)
            .filter(
                Question.topic_id == topic.id,
                Question.is_root_question == True,  # noqa: E712
                Question.is_stale == False,  # noqa: E712
            )
            .first()
        )
        topic_root_map[topic.id] = root_q.id if root_q else None

    # ── Step 3: Collect policy items per topic ───────────────────────────────
    topic_pi_map: dict[uuid.UUID, list[dict]] = {}
    total_pi = 0

    for topic in topics:
        pis = (
            db.query(PolicyItem)
            .filter(
                PolicyItem.topic_id == topic.id,
                PolicyItem.human_review_status.in_([
                    ReviewStatus.approved,
                    ReviewStatus.needs_review,
                    ReviewStatus.llm_generated,
                ]),
            )
            .all()
        )
        snapshots = []
        for pi in pis:
            if not force_regenerate:
                existing_count = (
                    db.query(Question)
                    .filter(
                        Question.policy_item_id == pi.id,
                        Question.tree_depth == 1,
                    )
                    .count()
                )
                if existing_count > 0:
                    continue
            snapshots.append({
                "id": pi.id,
                "title": pi.title,
                "description": pi.description or "",
                "directional_axis": pi.directional_axis or "",
                "topic_id": topic.id,
                "topic_slug": topic.slug,
            })
        topic_pi_map[topic.id] = snapshots
        total_pi += len(snapshots)

    if total_pi == 0:
        return {
            "created": 0, "skipped": 0, "errors": 0,
            "stale_marked": stale_marked, "total_budget": max_questions,
            "message": "No new policy items to process (all already have questions).",
        }

    # ── Step 4: Budget allocation across topics ──────────────────────────────
    # Distribute the question budget proportionally:
    #   depth-1 budget = 60% of max_questions
    #   depth-2 budget = 40% of max_questions (2 follow-ups per depth-1 that fits)
    depth1_budget = int(max_questions * 0.60)
    depth2_budget = max_questions - depth1_budget

    # Per-topic depth-1 limits
    per_topic_depth1 = max(1, depth1_budget // n_topics)

    # Build the complete work queue: (pi_data, parent_id)
    depth1_work: list[tuple[dict, uuid.UUID | None]] = []

    for topic in topics:
        pis_for_topic = topic_pi_map.get(topic.id, [])
        root_q_id = topic_root_map.get(topic.id)
        topic_depth1_count = 0
        for pi_data in pis_for_topic:
            if topic_depth1_count >= per_topic_depth1:
                break
            depth1_work.append((pi_data, root_q_id))
            topic_depth1_count += 1

    # Cap total depth-1 work at budget
    depth1_work = depth1_work[:depth1_budget]

    # ── Step 5: Generate depth-1 questions (parallel) ────────────────────────
    created = skipped = errors = 0
    depth1_results: list[dict] = []  # successful depth-1 results for depth-2 seeding

    _progress("depth1_generation", 0, len(depth1_work))

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(
                _generate_depth1_question, pi_data, parent_id, settings, _db_factory
            ): pi_data
            for (pi_data, parent_id) in depth1_work
        }
        completed_d1 = 0
        for future in as_completed(futures):
            pi_data = futures[future]
            try:
                result = future.result()
                if result.get("created"):
                    created += 1
                    depth1_results.append({
                        "question_id": uuid.UUID(result["question_id"]),
                        "pi_data": pi_data,
                    })
                elif "error" in result:
                    errors += 1
                else:
                    skipped += 1
            except Exception as exc:
                logger.error("question_bank depth-1 future failed: %s", exc)
                errors += 1
            completed_d1 += 1
            _progress("depth1_generation", completed_d1, len(depth1_work))

    # ── Step 6: Generate depth-2 followups if depth_levels >= 2 ─────────────
    if depth_levels >= 2 and depth2_budget > 0 and depth1_results:
        # Two followups per depth-1 question (support + oppose direction)
        # but cap at budget
        d2_pairs_budget = min(len(depth1_results), depth2_budget // 2)
        d2_candidates = depth1_results[:d2_pairs_budget]

        depth2_work = []
        for item in d2_candidates:
            q_id = item["question_id"]
            pi_data = item["pi_data"]
            # Support direction drill-down
            depth2_work.append((pi_data, q_id, "support", 0.5, None))
            # Opposition direction drill-down
            depth2_work.append((pi_data, q_id, "oppose", None, -0.5))

        _progress("depth2_generation", 0, len(depth2_work))

        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures2 = {
                executor.submit(
                    _generate_depth2_followup,
                    pi_data, q_id, direction, t_min, t_max,
                    settings, _db_factory,
                ): (pi_data, direction)
                for (pi_data, q_id, direction, t_min, t_max) in depth2_work
            }
            completed_d2 = 0
            for future in as_completed(futures2):
                try:
                    result = future.result()
                    if result.get("created"):
                        created += 1
                    elif "error" in result:
                        errors += 1
                    else:
                        skipped += 1
                except Exception as exc:
                    logger.error("question_bank depth-2 future failed: %s", exc)
                    errors += 1
                completed_d2 += 1
                _progress("depth2_generation", completed_d2, len(depth2_work))

    stats = {
        "created": created,
        "skipped": skipped,
        "errors": errors,
        "stale_marked": stale_marked,
        "total_budget": max_questions,
        "depth0_created": root_created,
        "depth0_errors": root_errors,
        "depth1_attempted": len(depth1_work),
        "message": (
            f"Question bank generation complete: "
            f"{root_created} root Qs created, "
            f"{created} depth-1/2 created, "
            f"{skipped} skipped, {errors} errors, {stale_marked} marked stale."
        ),
    }
    logger.info("run_question_bank_pipeline → %s", stats)
    return stats


