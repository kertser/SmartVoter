"""Quick DB diagnostics."""
import sys
sys.path.insert(0, ".")

from backend.app.db.session import SessionLocal
from backend.app.models.party_instance import PartyInstance
from backend.app.models.political_brand import PoliticalBrand
from backend.app.models.vote import Vote
from backend.app.models.person_party_membership import PersonPartyMembership
from backend.app.models.person import Person
import sqlalchemy as sa

db = SessionLocal()

print("=== ACTIVE PARTY INSTANCES ===")
rows = (
    db.query(
        PartyInstance.official_name,
        PartyInstance.knesset_number,
        PartyInstance.status,
        PartyInstance.political_brand_id,
        PoliticalBrand.canonical_name,
        PoliticalBrand.names_json,
    )
    .outerjoin(PoliticalBrand, PoliticalBrand.id == PartyInstance.political_brand_id)
    .filter(PartyInstance.status == "active")
    .order_by(PartyInstance.knesset_number.desc())
    .all()
)
for official, kn, status, brand_id, canonical, names_json in rows:
    print(f"  kn={kn} | {repr(official[:35])} | canonical={repr(str(canonical or '')[:25])} | names={names_json}")

print(f"\nTotal active: {len(rows)}")

# Duplicates by official_name
from collections import Counter
names_count = Counter(r[0] for r in rows)
dupes = {k: v for k, v in names_count.items() if v > 1}
print(f"\n=== DUPLICATES BY official_name ===")
for name, cnt in sorted(dupes.items(), key=lambda x: -x[1]):
    print(f"  {cnt}x {repr(name[:50])}")

print("\n=== SAMPLE VOTES WITH BILL_ID SET ===")
votes_with_bill = db.query(Vote).filter(Vote.bill_id.isnot(None)).limit(10).all()
print(f"Votes with bill_id: {db.query(Vote).filter(Vote.bill_id.isnot(None)).count()}")
for v in votes_with_bill[:5]:
    print(f"  {v.date} kn={v.knesset_number} bill={v.bill_id} title={repr(str(v.title_he or '')[:50])}")

print("\n=== PERSON PARTY MEMBERSHIP - ENGLISH PARTY NAMES ===")
# Find persons whose current party maps to an English canonical name
results = db.execute(sa.text("""
    SELECT DISTINCT pb.canonical_name, pb.names_json, pi.official_name, COUNT(*) as cnt
    FROM person_party_memberships ppm
    JOIN party_instances pi ON pi.id = ppm.party_instance_id
    LEFT JOIN political_brands pb ON pb.id = pi.political_brand_id
    WHERE ppm.end_date IS NULL
    GROUP BY pb.canonical_name, pb.names_json, pi.official_name
    ORDER BY cnt DESC
    LIMIT 20
""")).fetchall()
for canonical, names_json, official, cnt in results:
    he_name = (names_json or {}).get("he") if names_json else None
    print(f"  {cnt} members | canonical={repr(str(canonical or '')[:30])} | he={repr(str(he_name or '')[:25])} | official={repr(str(official or '')[:30])}")

db.close()

