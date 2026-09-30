"""Compile a resume .typ to PDF and refuse to pass it unless it meets the house rules.

    python career/resume/build.py career/resume/base.typ [-o out.pdf] [--png]

Checks: exactly one page, every glyph black, every link absolute https/mailto,
no placeholder text, and how much of the page is used (aim for 97-100%).
Links are listed so the agent can verify each one with WebFetch before sending.
"""

import argparse
import os
import re
import sys
from pathlib import Path

import pymupdf
import typst

PLACEHOLDER = re.compile(r"TODO|TBD|XX+|lorem|\?\?|\[.*?\]\(", re.I)


def check(pdf_path: Path) -> list[str]:
    doc = pymupdf.open(pdf_path)
    errors = []
    if doc.page_count != 1:
        errors.append(f"{doc.page_count} pages, must be 1")
    page = doc[0]
    colors, bottom = set(), 0.0
    for block in page.get_text("dict")["blocks"]:
        for line in block.get("lines", []):
            for span in line["spans"]:
                if span["text"].strip():
                    colors.add(span["color"])
                    bottom = max(bottom, span["bbox"][3])
    if colors - {0}:
        errors.append(f"non-black text colors: {[hex(c) for c in colors - {0}]}")
    text = page.get_text()
    if PLACEHOLDER.search(text):
        errors.append(f"placeholder text: {PLACEHOLDER.search(text).group(0)!r}")
    links = [l["uri"] for l in page.get_links() if l.get("uri")]
    for uri in links:
        if not re.match(r"^(https://|mailto:)[^\s]+$", uri):
            errors.append(f"bad link {uri!r}")
    fill = bottom / page.rect.height
    print(f"pages={doc.page_count} fill={fill:.1%} links={len(links)} words={len(text.split())}")
    for uri in sorted(set(links)):
        print("  link", uri)
    if fill < 0.93:
        errors.append(f"page only {fill:.0%} full, add a bullet or project")
    return errors


def load_phone(root: Path) -> str | None:
    """The phone number stays out of the public repo: env RESUME_PHONE or gitignored private/phone.txt."""
    if os.environ.get("RESUME_PHONE"):
        return os.environ["RESUME_PHONE"].strip()
    f = root.parent / "private" / "phone.txt"
    return f.read_text().strip() if f.exists() else None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("src", type=Path)
    ap.add_argument("-o", "--out", type=Path)
    ap.add_argument("--png", action="store_true", help="also write a preview PNG next to the PDF")
    args = ap.parse_args()
    out = args.out or args.src.with_suffix(".pdf")
    root = Path(__file__).resolve().parent
    inputs = {"phone": phone} if (phone := load_phone(root)) else {}
    typst.compile(str(args.src), output=str(out), root=str(root.parent.parent), sys_inputs=inputs)
    errors = check(out)
    if args.png:
        pymupdf.open(out)[0].get_pixmap(dpi=130).save(out.with_suffix(".png"))
    for e in errors:
        print("FAIL", e, file=sys.stderr)
    print("ok" if not errors else "not ok", out)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
