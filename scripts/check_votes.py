"""Quick check: vote titles and party names in DB."""
import sys
sys.path.insert(0, ".")

from backend.app.db.session import SessionLocal
from backend.app.models.vote import Vote
from backend.app.models.political_brand import PoliticalBrand
from sqlalchemy import func, or_

db = SessionLocal()
try:
    total = db.query(func.count(Vote.id)).scalar()
    # Find votes with combined titles (containing em-dash)
    combined = db.query(Vote.title_he).filter(
        or_(Vote.title_he.contains(" \u2014 "), Vote.title_he.contains(" - "))
    ).limit(5).all()

    print(f"Total votes: {total}")
    print("\nSample combined-title votes:")
    for (t,) in combined:
        print(f"  {t[:100]}")

    # Check a bare הסתייגות
    bare = db.query(Vote.title_he).filter(Vote.title_he == "\u05d4\u05e1\u05ea\u05d9\u05d9\u05d2\u05d5\u05ea").count()
    print(f"\nBare 'הסתייגות' votes: {bare}")

    # Show brand names
    print("\nPolitical brands names_json:")
    for brand in db.query(PoliticalBrand).all():
        print(f"  {brand.canonical_name}: {brand.names_json}")
finally:
    db.close()

