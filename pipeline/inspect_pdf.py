#!/usr/bin/env python3
"""
Diagnostic script: inspect raw PDF text extraction.

Usage: 
  python3 pipeline/inspect_pdf.py /path/to/sl.pdf scan
  python3 pipeline/inspect_pdf.py /path/to/sl.pdf page N
  python3 pipeline/inspect_pdf.py /path/to/sl.pdf find TEXT
  python3 pipeline/inspect_pdf.py /path/to/sl.pdf find_entry ENTRY_ID
  python3 pipeline/inspect_pdf.py /path/to/sl.pdf range N M   # show pages N-M
  python3 pipeline/inspect_pdf.py /path/to/sl.pdf chars N     # show all special chars on page N
"""
import sys
import re
import pdfplumber
import unicodedata

pdf_path = sys.argv[1]
mode     = sys.argv[2] if len(sys.argv) > 2 else "scan"

def extract_columns(page):
    """Extract two-column page in correct order."""
    x0, y0, x1, y1 = page.bbox
    mid_x = x0 + (x1 - x0) * 0.48  # 48% optimal for SL column layout
    left  = page.crop((x0, y0, mid_x, y1)).extract_text() or ""
    right = page.crop((mid_x, y0, x1, y1)).extract_text() or ""
    text  = left + "\n" + right
    # Rejoin hyphenated breaks
    text  = re.sub(r'([а-яёА-ЯЁa-zA-Z])-\n\s*([а-яёА-ЯЁa-zA-Z])', r'\1\2', text)
    return text

def extract_full(page):
    """Extract full page without column split — for diagnosis."""
    return page.extract_text() or ""

def show_chars(text):
    seen = set()
    for ch in text:
        if ord(ch) > 127 and ch not in seen:
            try: name = unicodedata.name(ch)
            except: name = "?"
            print(f"  U+{ord(ch):04X} {ch!r:4} {name}")
            seen.add(ch)

with pdfplumber.open(pdf_path) as pdf:
    total = len(pdf.pages)
    print(f"PDF has {total} pages\n")

    # ── SCAN: find first entry ──────────────────────────────────
    if mode == "scan":
        pat = re.compile(r'[А-ЯЁ]-\d+\s*[•·▪]')
        for p in range(total):
            text = extract_columns(pdf.pages[p])
            m = pat.search(text)
            if m:
                print(f"First entry+bullet on page {p+1}")
                print(f"  Context: {text[max(0,m.start()-20):m.end()+80]!r}")
                show_chars(text)
                break

    # ── PAGE: show raw text of page N ───────────────────────────
    elif mode == "page":
        n = int(sys.argv[3]) - 1
        page = pdf.pages[n]
        print(f"=== PAGE {n+1} (full, no column split) ===")
        print(extract_full(page)[:1500])
        print(f"\n=== PAGE {n+1} (column-aware) ===")
        print(extract_columns(page)[:1500])

    # ── CHARS: show special chars on page N ─────────────────────
    elif mode == "chars":
        n = int(sys.argv[3]) - 1
        text = extract_full(pdf.pages[n])
        print(f"Special chars on page {n+1}:")
        show_chars(text)

    # ── RANGE: show pages N to M ────────────────────────────────
    elif mode == "range":
        start = int(sys.argv[3]) - 1
        end   = int(sys.argv[4])
        for p in range(start, min(end, total)):
            text = extract_columns(pdf.pages[p])
            print(f"\n{'='*50} PAGE {p+1} {'='*50}")
            print(text[:600])

    # ── FIND: search for any text string ────────────────────────
    elif mode == "find":
        target = sys.argv[3]
        print(f"Searching for {target!r}...")
        for p in range(total):
            text = extract_columns(pdf.pages[p])
            if target in text:
                m = re.search(re.escape(target), text)
                print(f"Page {p+1}: {text[max(0,m.start()-30):m.end()+120]!r}")

    # ── FIND_ENTRY: find entry ID + bullet ──────────────────────
    elif mode == "find_entry":
        target = sys.argv[3]
        letter = target.split('-')[0]
        number = target.split('-')[1]
        print(f"Searching for entry {target!r} with bullet...")

        # Try progressively looser patterns
        patterns = [
            # tight: "Б-41 •" or "Б-41•"
            re.compile(rf'{re.escape(letter)}-{re.escape(number)}\s*•'),
            # with en-dash/em-dash
            re.compile(rf'{re.escape(letter)}[–—‐\-]{re.escape(number)}\s*•'),
            # entry ID anywhere near bullet on same line
            re.compile(rf'{re.escape(letter)}.{{0,3}}{re.escape(number)}.{{0,5}}•'),
        ]

        for p in range(total):
            # Try BOTH full-page and column-split extraction
            for extract_fn, label in [
                (extract_full,    "full"),
                (extract_columns, "cols"),
            ]:
                text = extract_fn(pdf.pages[p])
                for pat in patterns:
                    m = pat.search(text)
                    if m:
                        ctx_start = max(0, m.start()-20)
                        ctx_end   = min(len(text), m.end()+400)
                        print(f"\nFound on page {p+1} ({label} extraction):")
                        print(f"  Pattern: {pat.pattern!r}")
                        print(f"  Context:\n{text[ctx_start:ctx_end]}")
                        print(f"  Special chars:")
                        show_chars(text[ctx_start:ctx_end])
                        sys.exit(0)

        print(f"\nNot found with any bullet pattern.")
        print(f"Try: python3 inspect_pdf.py {pdf_path} range 30 60")
        print(f"to inspect pages where Б entries should be.")
