"""Check evidence strength values in party positions."""
from backend.app.db.session import SessionLocal
from backend.app.models.party_position import PartyPosition
from backend.app.models.party_instance import PartyInstance
from backend.app.models.political_brand import PoliticalBrand

db = SessionLocal()
brands = {b.id: b for b in db.query(PoliticalBrand).all()}
instances = {i.id: i for i in db.query(PartyInstance).all()}

# Get a sample of positions for each brand with data
from collections import defaultdict
brand_pos = defaultdict(list)
for p in db.query(PartyPosition).all():
    inst = instances.get(p.party_instance_id)
    if inst:
        brand_pos[inst.political_brand_id].append(p)

print("Evidence strength per brand (showing first instance with data):")
for brand_id, positions in brand_pos.items():
    brand = brands.get(brand_id)
    if not brand:
        continue
    evs = [p.evidence_strength for p in positions]
    types = list({p.evidence_type or 'None' for p in positions})
    avg_ev = sum(evs) / len(evs)
    print(f"  {brand.canonical_name[:40]:40} avg_ev={avg_ev:.3f} n={len(positions)} types={types[:3]}")
db.close()

