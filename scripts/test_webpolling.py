"""Test the full two-step web polling service."""
import os
import sys
import json
import logging
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.app.services.polling.web_polling import _call_openai_web_search

api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    print("No OPENAI_API_KEY")
    sys.exit(1)

print("=== Testing two-step web polling ===\n")
result = _call_openai_web_search(api_key=api_key, model="gpt-4o")

if result is None:
    print("FAIL: returned None")
    sys.exit(1)

print(f"\nPolls found: {len(result.get('polls', []))}")
print(f"Data as of: {result.get('data_as_of')}")
print(f"Notes: {result.get('notes')}")
print()
for poll in result.get("polls", []):
    print(f"  Pollster: {poll.get('pollster')} ({poll.get('publication_date')})")
    print(f"  Source: {poll.get('source_url')}")
    print(f"  Parties: {len(poll.get('parties', []))}")
    for p in poll.get("parties", [])[:5]:
        print(f"    - {p.get('name_he') or p.get('name_en')}: {p.get('seats')} seats / {p.get('vote_share_percent')}%")
    if len(poll.get("parties", [])) > 5:
        print(f"    ... and {len(poll.get('parties', [])) - 5} more")
    print()

print("\nRaw JSON (truncated):")
print(json.dumps(result, ensure_ascii=False, indent=2)[:2000])

