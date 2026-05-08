"""Check brand names_json for dedup analysis."""
from backend.app.db.session import SessionLocal
from backend.app.models.political_brand import PoliticalBrand
from backend.app.models.party_instance import PartyInstance, PartyStatus
from backend.app.models.party_position import PartyPosition
from collections import defaultdict

db = SessionLocal()
brands = db.query(PoliticalBrand).all()
instances = db.query(PartyInstance).all()

pos_counts = defaultdict(int)
for p in db.query(PartyPosition).all():
    pos_counts[p.party_instance_id] += 1

# Map brand_id -> instances
brand_instances = defaultdict(list)
brand_pos_total = defaultdict(int)
for inst in instances:
    brand_instances[inst.political_brand_id].append(inst)
    brand_pos_total[inst.political_brand_id] += pos_counts[inst.id]

print("Brands with positions:")
for brand in brands:
    total_pos = brand_pos_total.get(brand.id, 0)
    if total_pos == 0:
        continue
    names = brand.names_json or {}
    print(f"\n  [{brand.canonical_name}] total_pos={total_pos}")
    print(f"    names_json={names}")
    for inst in brand_instances[brand.id]:
        n = pos_counts.get(inst.id, 0)
        print(f"    KN{inst.knesset_number} {inst.status.value:10} pos={n} | {inst.official_name[:60]}")

db.close()

