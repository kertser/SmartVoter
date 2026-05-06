import sys; sys.path.insert(0, ".")
from backend.app.db.session import SessionLocal
from backend.app.api.public import list_parties

db = SessionLocal()
parties = list_parties(group_by_brand=True, db=db)
print(f"Total after dedup: {len(parties)}")
active = [p for p in parties if p["status"] == "active"]
print(f"Active: {len(active)}")
for p in active:
    he = str(p.get("name_he") or "")[:40]
    name = str(p.get("name") or "")[:25]
    official = str(p.get("official_name") or "")[:40]
    print(f"  kn={p['knesset_number']} | he={repr(he)} | name={repr(name)}")
print()
print("Non-active sample:")
for p in parties[:5]:
    if p["status"] != "active":
        he = str(p.get("name_he") or "")[:40]
        print(f"  kn={p['knesset_number']} status={p['status']} | he={repr(he)}")
db.close()

