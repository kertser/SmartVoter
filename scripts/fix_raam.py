"""
Fix missing Raam party instance in DB.
Run: docker exec smartvoter-backend-1 uv run python scripts/fix_raam.py
"""
import uuid
import datetime
import sys
from backend.app.db.session import SessionLocal
from backend.app.models.party_instance import PartyInstance, PartyStatus
from backend.app.models.political_brand import PoliticalBrand

db = SessionLocal()

# Find the Ra'am brand
brand = db.query(PoliticalBrand).filter(PoliticalBrand.canonical_name == "Ra'am").first()
print(f"Ra'am brand: {brand.id if brand else 'NOT FOUND'}", flush=True)

# Check if Raam party instance exists
existing = db.query(PartyInstance).filter(PartyInstance.official_name == 'Raam').first()
print(f"Existing Raam party instance: {'YES' if existing else 'MISSING'}", flush=True)

if not existing and brand:
    pi = PartyInstance(
        id=uuid.UUID('20000000-0000-0000-0000-000000000010'),
        political_brand_id=brand.id,
        official_name='Raam',
        election_cycle='2022',
        knesset_number=25,
        start_date=datetime.date(2022, 11, 1),
        end_date=None,
        status=PartyStatus.active,
        left_right_score=-0.30,
    )
    db.add(pi)
    db.commit()
    print("✓ Inserted Raam party instance with lr=-0.30", flush=True)
elif existing:
    if existing.left_right_score is None:
        existing.left_right_score = -0.30
        db.commit()
        print("✓ Updated Raam left_right_score to -0.30", flush=True)
    else:
        print(f"Raam already has lr={existing.left_right_score}", flush=True)
else:
    print("ERROR: Ra'am brand not found in DB. Ensure seed data is loaded.", flush=True)
    sys.exit(1)

db.close()
print("Done.", flush=True)

