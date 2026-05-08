"""Check party instances in DB for deduplication analysis."""
from backend.app.db.session import SessionLocal
from backend.app.models.party_instance import PartyInstance
from backend.app.models.political_brand import PoliticalBrand
from backend.app.models.party_position import PartyPosition

db = SessionLocal()
instances = db.query(PartyInstance).all()
brands = {b.id: b for b in db.query(PoliticalBrand).all()}
pos_counts = {}
for p in db.query(PartyPosition).all():
    pos_counts[p.party_instance_id] = pos_counts.get(p.party_instance_id, 0) + 1

print(f"Total party_instances: {len(instances)}")
print()
for inst in sorted(instances, key=lambda i: (brands[i.political_brand_id].canonical_name if i.political_brand_id in brands else '', i.knesset_number or 0)):
    brand = brands.get(inst.political_brand_id)
    brand_name = brand.canonical_name if brand else "NO BRAND"
    n_positions = pos_counts.get(inst.id, 0)
    kn = inst.knesset_number or "?"
    status = inst.status.value
    official = inst.official_name[:60]
    print(f"  KN{kn} | {status:10} | pos:{n_positions:3} | [{brand_name}] | {official}")

# Check for brands with multiple active instances
print("\n--- Brands with multiple instances ---")
from collections import defaultdict
brand_instances = defaultdict(list)
for inst in instances:
    brand_instances[inst.political_brand_id].append(inst)

for brand_id, insts in brand_instances.items():
    if len(insts) > 1:
        brand = brands.get(brand_id)
        print(f"\nBrand: {brand.canonical_name if brand else brand_id}")
        for inst in insts:
            n_pos = pos_counts.get(inst.id, 0)
            print(f"  KN{inst.knesset_number or '?'} | {inst.status.value:10} | pos:{n_pos} | {inst.official_name}")

db.close()

