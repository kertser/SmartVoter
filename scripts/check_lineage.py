"""Check lineage edges in DB."""
from backend.app.db.session import SessionLocal
from backend.app.models.party_lineage_edge import PartyLineageEdge
from backend.app.models.party_instance import PartyInstance
from backend.app.models.political_brand import PoliticalBrand

db = SessionLocal()
edges = db.query(PartyLineageEdge).all()
instances = {i.id: i for i in db.query(PartyInstance).all()}
brands = {b.id: b for b in db.query(PoliticalBrand).all()}

print(f"Total lineage edges: {len(edges)}")
for e in edges:
    f_inst = instances.get(e.from_party_instance_id)
    t_inst = instances.get(e.to_party_instance_id)
    f_brand = brands.get(f_inst.political_brand_id) if f_inst else None
    t_brand = brands.get(t_inst.political_brand_id) if t_inst else None
    f_name = f_brand.canonical_name if f_brand else "?"
    t_name = t_brand.canonical_name if t_brand else "?"
    print(f"  {e.relation_type.value:10} w={e.continuity_weight:.2f} | {f_name} -> {t_name}")
db.close()

