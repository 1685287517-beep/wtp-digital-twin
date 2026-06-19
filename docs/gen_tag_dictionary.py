"""Regenerate docs/tag_dictionary.md from app/tags.py (single source of truth).

    python docs/gen_tag_dictionary.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.tags import TAGS  # noqa: E402

OUT = os.path.join(os.path.dirname(__file__), "tag_dictionary.md")

lines = ["# Tag Dictionary", "",
         "Generated from `app/tags.py`. Do not edit by hand.", "",
         "| Tag | Description | Unit | Type |",
         "|-----|-------------|------|------|"]
for t in TAGS:
    lines.append(f"| `{t.name}` | {t.desc} | {t.unit} | {t.dtype} |")

with open(OUT, "w") as f:
    f.write("\n".join(lines) + "\n")
print(f"wrote {OUT} ({len(TAGS)} tags)")
