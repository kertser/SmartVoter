"""
Check question counts and policy items to understand repetition.
"""
from backend.app.db.session import SessionLocal
from backend.app.models.question import Question
from backend.app.models.policy_item import PolicyItem
from backend.app.models.topic import Topic
from collections import defaultdict

db = SessionLocal()
questions = db.query(Question).all()
policy_items = {pi.id: pi for pi in db.query(PolicyItem).all()}
topics = {t.id: t for t in db.query(Topic).all()}

print(f"Total questions: {len(questions)}")
print()

# Count by status
status_counts = defaultdict(int)
for q in questions:
    status_counts[q.human_review_status.value] += 1
print("By status:")
for status, count in sorted(status_counts.items()):
    print(f"  {status}: {count}")
print()

# Count by policy_item
pi_question_counts = defaultdict(list)
for q in questions:
    if q.policy_item_id:
        pi_question_counts[q.policy_item_id].append(q)

print("Policy items with multiple questions:")
for pi_id, qs in pi_question_counts.items():
    if len(qs) > 1:
        pi = policy_items.get(pi_id)
        topic = topics.get(pi.topic_id) if pi and pi.topic_id else None
        print(f"  {len(qs)} questions | [{topic.slug if topic else '?'}] {pi.title[:60] if pi else '?'}")
        for q in qs[:3]:
            print(f"    - {q.human_review_status.value}: {q.question_text_en[:80]}")

print()
# root questions
root_qs = [q for q in questions if q.is_root_question]
print(f"Root questions: {len(root_qs)}")
for rq in root_qs:
    topic = None
    if rq.topic_id:
        topic = topics.get(rq.topic_id)
    print(f"  [{topic.slug if topic else '?'}] {rq.question_text_en[:80]}")

db.close()

