"""DB diagnostics v2."""
import sys; sys.path.insert(0, ".")
from backend.app.db.session import SessionLocal
from backend.app.models.vote import Vote
from backend.app.models.person_party_membership import PersonPartyMembership
from backend.app.models.party_instance import PartyInstance
from backend.app.models.political_brand import PoliticalBrand
from backend.app.models.person import Person

db = SessionLocal()

print("=== VOTES: קריאה שנייה sample ===")
votes = db.query(Vote).filter(Vote.title_he.like('קריאה שנייה%')).limit(5).all()
for v in votes:
    print(f" title_he={repr(v.title_he)} title_en={repr(v.title_en)} type={v.vote_type} bill_id={v.bill_id} ext={v.external_id}")

print("\n=== VOTES: אישור החוק sample ===")
votes2 = db.query(Vote).filter(Vote.title_he == 'אישור החוק').limit(5).all()
for v in votes2:
    print(f" title_he={repr(v.title_he)} title_en={repr(v.title_en)} type={v.vote_type} bill_id={v.bill_id} ext={v.external_id} kn={v.knesset_number} date={v.date}")

print("\n=== VOTES: same date sample ===")
# Votes on same date - do they have same bill IDs?
from sqlalchemy import func
date_groups = (db.query(Vote.date, func.count(Vote.id))
    .group_by(Vote.date)
    .having(func.count(Vote.id) > 5)
    .order_by(Vote.date.desc()).limit(3).all()
)
for date, cnt in date_groups:
    print(f"\n Date {date}: {cnt} votes")
    day_votes = db.query(Vote).filter(Vote.date == date).order_by(Vote.id).limit(8).all()
    for v in day_votes:
        print(f"  {repr((v.title_he or '')[:50])} | bill={v.bill_id} | ext={repr(v.external_id)}")

print("\n=== PERSONS: duplicates by Hebrew name ===")
from sqlalchemy import func
dup_names = (db.query(Person.name_he, func.count(Person.id).label('cnt'))
    .filter(Person.name_he.isnot(None))
    .group_by(Person.name_he)
    .having(func.count(Person.id) > 1)
    .all()
)
print(f"Hebrew name duplicates: {len(dup_names)}")
for name, cnt in dup_names[:10]:
    print(f"  {cnt}x {repr(name)}")

print("\n=== ACTIVE MEMBERSHIPS breakdown ===")
from sqlalchemy import distinct
active = (db.query(PersonPartyMembership)
    .filter(PersonPartyMembership.end_date.is_(None))
    .all()
)
print(f"Total active memberships: {len(active)}")
person_ids = set(m.person_id for m in active)
print(f"Distinct persons: {len(person_ids)}")
# How many persons have 2+ active memberships?
from collections import Counter
m_count = Counter(m.person_id for m in active)
multi = {k: v for k, v in m_count.items() if v > 1}
print(f"Persons with 2+ active memberships: {len(multi)}")
for pid, cnt in list(multi.items())[:5]:
    p = db.query(Person).filter(Person.id == pid).first()
    print(f"  {repr(p.name_he)} - {cnt} memberships")
    for m in db.query(PersonPartyMembership).filter(PersonPartyMembership.person_id == pid, PersonPartyMembership.end_date.is_(None)).all():
        party = db.query(PartyInstance).filter(PartyInstance.id == m.party_instance_id).first()
        print(f"    -> {repr(party.official_name if party else 'N/A')}")

db.close()

