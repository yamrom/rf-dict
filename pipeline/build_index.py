#!/usr/bin/env python3
"""
build_index.py — Parse SL Yale Index docx and build three lookup dictionaries

Output (saved to pipeline/sl_index.json):
  keyword_to_entries:  { "АЗАРТ": ["А-15"], "АВОСЬ": ["А-5"], ... }
  entry_to_idioms:     { "А-15": ["войти в азарт", "впадать/впасть в азарт", ...], ... }
  idiom_to_entry:      { "войти в азарт": {"entry": "А-15", "keyword": "АЗАРТ"}, ... }

Usage:
  python3 build_index.py
  python3 build_index.py --lookup войти в азарт
  python3 build_index.py --entry А-15
  python3 build_index.py --stats
"""

import re
import json
import argparse
from pathlib import Path
from docx import Document
from collections import defaultdict

SL_INDEX = Path('/Users/yamrom/work/rf_dict/SL/docs/Sophia_Lubensky_Index 1.docx')
OUTPUT   = Path('/Users/yamrom/work/rf_dict/rf_dict/pipeline/sl_index.json')

# Entry ID pattern: А-15, Б-41, etc.
ENTRY_ID_PAT = re.compile(r'\b([А-ЯЁA-Z]-\d+)\b')


def parse_index(doc_path=SL_INDEX):
    """
    Parse the index docx into three dictionaries.
    """
    doc = Document(doc_path)

    keyword_to_entries = defaultdict(set)   # keyword → set of entry IDs
    entry_to_idioms    = defaultdict(list)  # entry ID → list of idiom strings
    idiom_to_entry     = {}                 # idiom string → {entry, keyword}

    current_keyword = None
    pending_text    = None   # Body Text that may need the next Normal appended

    for para in doc.paragraphs:
        style = para.style.name
        text  = para.text.strip()

        if not text:
            continue

        # ── New keyword heading ──────────────────────────────────
        if style in ('Heading 1', 'Heading 2', 'Heading 3') and not ENTRY_ID_PAT.match(text):
            # Flush any pending text that has no wrapped entry ID
            if pending_text:
                _process_block(pending_text, current_keyword,
                               keyword_to_entries, entry_to_idioms, idiom_to_entry)
                pending_text = None
            current_keyword = text.strip()
            continue

        # ── Entry ID on its own line (wrapped from previous Body Text) ──
        if style in ('Normal', 'Heading 3') and ENTRY_ID_PAT.match(text):
            if pending_text:
                # Append the wrapped entry ID to the pending text
                combined = pending_text.rstrip(', ') + ', ' + text
                _process_block(combined, current_keyword,
                               keyword_to_entries, entry_to_idioms, idiom_to_entry)
                pending_text = None
            else:
                # Standalone entry ID line with no preceding text — skip
                pass
            continue

        # ── Body Text: one or more idiom+entry pairs ─────────────
        if style == 'Body Text':
            # Flush previous pending if any (it was complete)
            if pending_text:
                _process_block(pending_text, current_keyword,
                               keyword_to_entries, entry_to_idioms, idiom_to_entry)

            # Check if this text ends with a complete entry ID or not
            if ENTRY_ID_PAT.search(text):
                # Has at least one entry ID — but may be mid-stream at end
                # Check if it ends cleanly (last token is an entry ID)
                stripped = text.rstrip()
                last_token = stripped.split()[-1] if stripped.split() else ''
                if ENTRY_ID_PAT.match(last_token):
                    # Ends with entry ID — complete, process now
                    _process_block(text, current_keyword,
                                   keyword_to_entries, entry_to_idioms, idiom_to_entry)
                    pending_text = None
                else:
                    # Ends mid-idiom with entry ID somewhere inside but trailing text
                    # e.g. "войти в азарт, А-15 впадать/впасть в азарт, А-15 прийти в азарт,"
                    # The last idiom is incomplete — hold it
                    pending_text = text
            else:
                # No entry ID at all — this is a wrapped idiom text without entry ID yet
                pending_text = text

    # Flush final pending
    if pending_text and current_keyword:
        _process_block(pending_text, current_keyword,
                       keyword_to_entries, entry_to_idioms, idiom_to_entry)

    # Convert sets to sorted lists
    keyword_to_entries = {k: sorted(v) for k, v in keyword_to_entries.items()}
    entry_to_idioms    = {k: v for k, v in entry_to_idioms.items()}

    return keyword_to_entries, entry_to_idioms, idiom_to_entry


def _process_block(text, keyword, keyword_to_entries, entry_to_idioms, idiom_to_entry):
    """
    Parse one block of text containing one or more 'idiom, ENTRY-ID' pairs.
    
    Examples of text:
      "войти в азарт, А-15"
      "войти в азарт, А-15 впадать/впасть в азарт, А-15 входить в азарт, А-15"
      "авось да небось, А-5"
    """
    if not keyword or not text.strip():
        return

    # Split the block into individual idiom+entry tokens
    # Strategy: find all entry IDs and their positions, then extract
    # the idiom text preceding each entry ID

    matches = list(ENTRY_ID_PAT.finditer(text))
    if not matches:
        return

    for i, m in enumerate(matches):
        entry_id = m.group(1)

        # Idiom text is everything between the previous entry ID (or start) and this one
        if i == 0:
            idiom_start = 0
        else:
            idiom_start = matches[i-1].end()

        idiom_raw = text[idiom_start:m.start()].strip().strip(',').strip()

        # Clean up the idiom text
        idiom = _clean_idiom(idiom_raw)

        if not idiom:
            continue

        # Record in all three dictionaries
        keyword_to_entries[keyword].add(entry_id)

        if idiom not in entry_to_idioms[entry_id]:
            entry_to_idioms[entry_id].append(idiom)

        if idiom not in idiom_to_entry:
            idiom_to_entry[idiom] = {'entry': entry_id, 'keyword': keyword}


def _clean_idiom(text):
    """Clean up raw idiom text from the index."""
    if not text:
        return ''
    # Remove leading/trailing punctuation and whitespace
    text = text.strip().strip(',').strip(';').strip()
    # Collapse multiple spaces
    text = re.sub(r'\s+', ' ', text)
    # Remove leading entry-ID artifacts
    text = re.sub(r'^[А-ЯЁA-Z]-\d+\s*', '', text)
    return text.strip()


def save_index(keyword_to_entries, entry_to_idioms, idiom_to_entry, output=OUTPUT):
    """Save all three dictionaries to a single JSON file."""
    data = {
        'keyword_to_entries': keyword_to_entries,
        'entry_to_idioms':    entry_to_idioms,
        'idiom_to_entry':     idiom_to_entry,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    with open(output, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"Saved to {output}")
    return output


def load_index(path=OUTPUT):
    """Load the pre-built index from JSON."""
    with open(path, encoding='utf-8') as f:
        data = json.load(f)
    return (data['keyword_to_entries'],
            data['entry_to_idioms'],
            data['idiom_to_entry'])


def print_stats(kw, ei, ie):
    print(f"Keywords:  {len(kw):6d}")
    print(f"Entries:   {len(ei):6d}")
    print(f"Idioms:    {len(ie):6d}")

    # Entries with most idioms
    top = sorted(ei.items(), key=lambda x: len(x[1]), reverse=True)[:10]
    print("\nEntries with most idioms:")
    for entry, idioms in top:
        print(f"  {entry}: {len(idioms)} idioms — {idioms[0][:50]}")

    # Letter distribution of entries
    from collections import Counter
    letters = Counter(e.split('-')[0] for e in ei)

    print("Entries and keywords per letter:")
    kw_letters = Counter(k[0] for k in kw)  # first char of keyword
    for letter in sorted(set(list(letters.keys()) + list(kw_letters.keys()))):
        n_entries  = letters.get(letter, 0)
        n_keywords = kw_letters.get(letter, 0)
        print(f"  {letter}: {n_entries} entries, {n_keywords} keywords")


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description='Build SL index lookup dictionaries')
    ap.add_argument('--build',  action='store_true', help='Parse index and save JSON')
    ap.add_argument('--stats',  action='store_true', help='Show statistics')
    ap.add_argument('--lookup', nargs='+', help='Look up an idiom string')
    ap.add_argument('--entry',  help='Show all idioms for an entry')
    ap.add_argument('--keyword', help='Show all entries for a keyword')
    args = ap.parse_args()

    if args.build or not OUTPUT.exists():
        print(f"Parsing {SL_INDEX}...")
        kw, ei, ie = parse_index()
        save_index(kw, ei, ie)
    else:
        print(f"Loading from {OUTPUT}...")
        kw, ei, ie = load_index()

    print_stats(kw, ei, ie)

    if args.lookup:
        idiom = ' '.join(args.lookup)
        if idiom in ie:
            print(f"\nLookup: '{idiom}'")
            print(f"  Entry:   {ie[idiom]['entry']}")
            print(f"  Keyword: {ie[idiom]['keyword']}")
        else:
            # Try partial match
            matches = [k for k in ie if idiom.lower() in k.lower()]
            print(f"\nNo exact match for '{idiom}'")
            if matches:
                print(f"Partial matches ({len(matches)}):")
                for m in matches[:10]:
                    print(f"  '{m}' → {ie[m]['entry']}")

    if args.entry:
        if args.entry in ei:
            idioms = ei[args.entry]
            print(f"\nEntry {args.entry}: {len(idioms)} idioms")
            for idiom in idioms:
                kwd = ie.get(idiom, {}).get('keyword', '?')
                print(f"  [{kwd}] {idiom}")
        else:
            print(f"Entry {args.entry} not found")

    if args.keyword:
        kwd = args.keyword.upper()
        if kwd in kw:
            print(f"\nKeyword '{kwd}': entries {kw[kwd]}")
            for entry_id in kw[kwd]:
                print(f"  {entry_id}:")
                for idiom in ei.get(entry_id, []):
                    print(f"    {idiom}")
        else:
            print(f"Keyword '{kwd}' not found")
