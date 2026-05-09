"""Show policy items with 3+ servable questions."""
from backend.app.db.session import SessionLocal
from backend.app.models.question import Question
from backend.app.models.policy_item import PolicyItem
from collections import defaultdict

db = SessionLocal()
qs = db.query(Question).filter(Question.human_review_status.in_(["approved","llm_generated"])).all()
print(f"Total servable questions: {len(qs)}")

by_pi = defaultdict(list)
for q in qs:
    by_pi[q.policy_item_id].append(q)

print("Policy items with 3+ questions:")
for pi_id, qlist in sorted(by_pi.items(), key=lambda x: -len(x[1])):
    if len(qlist) >= 3:
        pi = db.query(PolicyItem).filter(PolicyItem.id == pi_id).first() if pi_id else None
        label = pi.title[:40] if pi else "ROOT/None"
        print(f"  [{label}] ({len(qlist)} qs):")
        for q in qlist[:5]:
            print(f"    - {q.question_text_en[:80]}")
db.close()

