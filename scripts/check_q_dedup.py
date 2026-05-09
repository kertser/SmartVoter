"""Quick sanity check on questions.json after deduplication."""
import json
from pathlib import Path
from collections import Counter

data = json.loads((Path(__file__).parent.parent / "backend/app/seed/data/questions.json").read_text(encoding="utf-8"))

# Duplicate EN texts?
texts = [q["question_text_en"] for q in data]
c = Counter(texts)
dups = [(t, n) for t, n in c.items() if n > 1]
if dups:
    print("DUPLICATE EN texts:")
    for t, n in dups:
        print(f"  x{n}: {t[:90]}")
else:
    print("No duplicate EN texts found.")

# Suspicious non-Latin/Hebrew/Russian characters
suspicious = []
for i, q in enumerate(data):
    for field in ["question_text_en", "question_text_he", "question_text_ru"]:
        text = q.get(field, "") or ""
        for ch in text:
            cp = ord(ch)
            if cp > 127 and not (0x0590 <= cp <= 0x05FF) and not (0x0400 <= cp <= 0x04FF) and cp not in (
                0x200E, 0x200F, 0x2019, 0x201C, 0x201D, 0x2013, 0x2014, 0x00AB, 0x00BB, 0xA0,
                0x00E9, 0x00E8, 0x00EA,  # accented Latin
            ):
                suspicious.append((i, field, q.get("policy_slug"), ch, hex(cp)))
if suspicious:
    print("SUSPICIOUS characters:")
    for s in suspicious:
        print(s)
else:
    print("All characters look clean!")

# Print changed slugs
changed_slugs = {"eco_02", "eco_03", "rel_03", "mil_01"}
print("\nChanged questions:")
for q in data:
    if q.get("policy_slug") in changed_slugs:
        print(f"  [{q['policy_slug']}] pol={q['answer_polarity']:+.0f}: {q['question_text_en'][:90]}")

