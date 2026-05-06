import sys; sys.path.insert(0, ".")
from backend.app.db.session import SessionLocal
from backend.app.models.vote import Vote
from sqlalchemy import not_, or_

db = SessionLocal()

PROCEDURAL_EXACT = {
    'הסתייגות','הצבעה','הצעת ועדה','הצעת ועדת הכנסת',
    'קריאה שנייה','קריאה ראשונה ושנייה','קריאה ראשונה',
    'אישור החוק','הצעת ועדת הכנסת לסדר היום',
    'הודעת הממשלה','הצעה לסדר היום','בקשה לסדר היום'
}
PROCEDURAL_PREFIXES = (
    'להעביר את הצעת החוק לוועדה','להעביר את הנושא לוועדה',
    'העברת הנושא לוועדה','לכלול את הנושא בסדר היום',
    'העברת הצעת החוק לוועדה','להחזיר את הצעת החוק',
    'קריאה שנייה ושלישית'
)

q = db.query(Vote)
exact_conds = [Vote.title_he == t for t in PROCEDURAL_EXACT]
prefix_conds = [Vote.title_he.like(f'{p}%') for p in PROCEDURAL_PREFIXES]
q_filtered = q.filter(not_(or_(*exact_conds, *prefix_conds)))
total = db.query(Vote).count()
filtered = q_filtered.count()
print(f'Total votes: {total}')
print(f'After filter: {filtered}')
print('Sample substantive votes:')
for v in q_filtered.order_by(Vote.date.desc()).limit(15).all():
    t = (v.title_he or '')[:60]
    print(f'  {v.date} {repr(t)}')

db.close()

