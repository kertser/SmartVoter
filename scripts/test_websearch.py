"""Quick test script for OpenAI Responses API web search."""
import os
import sys
from dotenv import load_dotenv

load_dotenv()

from openai import OpenAI

api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    print("No OPENAI_API_KEY found")
    sys.exit(1)

client = OpenAI(api_key=api_key)

# --- Test 1: simple call without web search ---
print("=== Test 1: simple gpt-4o call ===")
try:
    r = client.responses.create(
        model="gpt-4o",
        input="Say hello.",
    )
    print("output_text:", getattr(r, "output_text", "<no attr>")[:80])
    print("output len:", len(r.output))
    for i, item in enumerate(r.output):
        print(f"  item[{i}] type={getattr(item, 'type', None)}")
except Exception as e:
    print("FAIL:", e)

print()

# --- Test 2: with web search ---
print("=== Test 2: gpt-4o + web_search_preview ===")
try:
    r = client.responses.create(
        model="gpt-4o",
        tools=[{"type": "web_search_preview"}],
        input="What Israeli opinion polls were published this week about the next Knesset?",
    )
    print("output_text (first 500):", getattr(r, "output_text", "<no attr>")[:500])
    print("output len:", len(r.output))
    for i, item in enumerate(r.output):
        itype = getattr(item, "type", None)
        print(f"  item[{i}] type={itype}")
        if hasattr(item, "content"):
            for j, block in enumerate(item.content):
                btype = getattr(block, "type", None)
                btext = getattr(block, "text", "")
                print(f"    block[{j}] type={btype} text={str(btext)[:120]}")
except Exception as e:
    print("FAIL:", type(e).__name__, e)

print()

# --- Test 3: try with gpt-4o-mini ----
print("=== Test 3: gpt-4o-mini + web_search_preview ===")
try:
    r = client.responses.create(
        model="gpt-4o-mini",
        tools=[{"type": "web_search_preview"}],
        input="What is today's date?",
    )
    print("output_text:", getattr(r, "output_text", "<no attr>")[:200])
except Exception as e:
    print("FAIL:", type(e).__name__, e)

