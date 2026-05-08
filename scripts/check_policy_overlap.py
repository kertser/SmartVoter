"""Check if same policy items get positions from multiple party brands (dedup root cause)."""
from backend.app.db.session import SessionLocal
from backend.app.models.party_position import PartyPosition
from backend.app.models.party_instance import PartyInstance
from backend.app.models.political_brand import PoliticalBrand
from backend.app.models.policy_item import PolicyItem
from collections import defaultdict

db = SessionLocal()
brands = {b.id: b for b in db.query(PoliticalBrand).all()}
instances = {i.id: i for i in db.query(PartyInstance).all()}
policy_items = {pi.id: pi for pi in db.query(PolicyItem).all()}

# For each policy_item, which brands have positions on it?
pi_to_brands = defaultdict(set)
pi_to_details = defaultdict(list)
for p in db.query(PartyPosition).all():
    inst = instances.get(p.party_instance_id)
    if inst:
        brand = brands.get(inst.political_brand_id)
        if brand:
            pi_to_brands[p.policy_item_id].add(brand.canonical_name)
            pi_to_details[p.policy_item_id].append((brand.canonical_name, p.position_mean, p.evidence_strength))

print("Policy items with positions from MULTIPLE brands (potential duplicates):")
count = 0
for pi_id, brand_set in pi_to_brands.items():
    if len(brand_set) < 2:
        continue
    count += 1
    pi = policy_items.get(pi_id)
    pi_name = pi.title[:50] if pi else str(pi_id)
    print(f"\n  [{pi_name}]")
    for brand_name, pos_mean, ev_str in pi_to_details[pi_id]:
        print(f"    Brand: {brand_name[:40]:40} pos={pos_mean:+.2f} ev={ev_str:.2f}")

print(f"\nTotal policy items with multi-brand coverage: {count}")
db.close()

