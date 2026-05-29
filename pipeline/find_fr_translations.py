#!/usr/bin/env python3
"""
find_fr_translations.py — Find French translations for SL bibliography entries

For each entry in sl_bibliography.csv, uses Claude to find known French translations
including title, translator, publisher, year, and availability (free/commercial).

Usage:
  python pipeline/find_fr_translations.py --lookup        # process all missing entries
  python pipeline/find_fr_translations.py --author Chekhov  # single author
  python pipeline/find_fr_translations.py --stats         # show current coverage
"""

import os
import csv
import json
import time
import argparse
import anthropic
from pathlib import Path

PIPELINE_DIR = Path(__file__).parent
REPO_ROOT    = PIPELINE_DIR.parent
BIBLIO_CSV   = REPO_ROOT / "bibliography" / "sl_bibliography.csv"
OUTPUT_CSV   = REPO_ROOT / "bibliography" / "sl_bibliography_fr.csv"
CACHE_JSON   = PIPELINE_DIR / "fr_translation_cache.json"

ANTHROPIC_KEY = os.environ.get("ANTHROPIC_API_KEY", "")


SYSTEM_PROMPT = """You are a specialist in Russian literature and its French translations.
For each Russian literary work provided, you will identify all known French translations.

Return ONLY valid JSON. No prose, no explanation outside the JSON.

For each work return:
{
  "found": true/false,
  "translations": [
    {
      "title_fr": "French title",
      "translator": "Translator name(s)",
      "publisher": "French publisher",
      "year": "year of first French publication",
      "notes": "any relevant notes (e.g. abridged, available on Gallica, etc.)",
      "freely_available": true/false,
      "url": "URL if freely available online, else null"
    }
  ],
  "confidence": "high/medium/low"
}

If no French translation exists or is known, return {"found": false, "translations": [], "confidence": "high"}

Key free sources to check:
- Gallica (gallica.bnf.fr) — French national library, many 19th century translations
- Wikisource (fr.wikisource.org) — free literary texts
- Project Gutenberg French section
- Archive.org
"""


def load_bibliography() -> list:
    """Load all bibliography entries."""
    with open(BIBLIO_CSV, encoding='utf-8') as f:
        return list(csv.DictReader(f))


def load_cache() -> dict:
    """Load cached translation lookups."""
    if CACHE_JSON.exists():
        with open(CACHE_JSON, encoding='utf-8') as f:
            return json.load(f)
    return {}


def save_cache(cache: dict):
    """Save cache to JSON."""
    with open(CACHE_JSON, 'w', encoding='utf-8') as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)


def lookup_translation(row: dict, client: anthropic.Anthropic) -> dict:
    """Ask Claude to find French translations for one bibliography entry."""

    author    = row.get('Author_Transliterated', '').strip()
    author_ru = row.get('Author_RU', '').strip()
    work_ru   = row.get('Work_RU', '').strip()
    work_en   = row.get('Work_EN', '').strip()
    year_en   = row.get('Year_EN', '').strip()

    prompt = f"""Find all known French translations of this Russian literary work:

Author (Russian): {author_ru}
Author (transliterated): {author}
Work (Russian title): {work_ru}
Work (English title): {work_en}
{f'Year of English translation: {year_en}' if year_en else ''}

Return JSON with all French translations you know of."""

    response = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=800,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}]
    )

    text = response.content[0].text.strip()
    # Strip markdown if present
    import re
    text = re.sub(r'^```(?:json)?\s*', '', text, flags=re.MULTILINE)
    text = re.sub(r'\s*```$', '', text, flags=re.MULTILINE)

    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        return {"found": False, "translations": [], "confidence": "low",
                "error": text[:200]}


def save_results_csv(rows: list, results: dict):
    """Save updated bibliography with French translations to CSV."""
    fieldnames = list(rows[0].keys())
    # Add new fields if not present
    for field in ['Work_FR_2', 'Translator_FR_2', 'Publisher_FR_2', 'Year_FR_2',
                  'Work_FR_3', 'Translator_FR_3', 'Publisher_FR_3', 'Year_FR_3',
                  'FR_available_free', 'FR_url', 'FR_lookup_confidence']:
        if field not in fieldnames:
            fieldnames.append(field)

    with open(OUTPUT_CSV, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for row in rows:
            sl_code = row.get('SL_code', '')
            result  = results.get(sl_code, {})

            if result.get('found') and result.get('translations'):
                translations = result['translations']

                # First translation goes into existing Work_FR etc. columns
                t0 = translations[0]
                if not row.get('Work_FR', '').strip():
                    row['Work_FR']        = t0.get('title_fr', '')
                    row['Translator_FR']  = t0.get('translator', '')
                    row['Publisher_FR']   = t0.get('publisher', '')
                    row['Year_FR']        = t0.get('year', '')

                # Second translation
                if len(translations) > 1:
                    t1 = translations[1]
                    row['Work_FR_2']       = t1.get('title_fr', '')
                    row['Translator_FR_2'] = t1.get('translator', '')
                    row['Publisher_FR_2']  = t1.get('publisher', '')
                    row['Year_FR_2']       = t1.get('year', '')

                # Third translation
                if len(translations) > 2:
                    t2 = translations[2]
                    row['Work_FR_3']       = t2.get('title_fr', '')
                    row['Translator_FR_3'] = t2.get('translator', '')
                    row['Publisher_FR_3']  = t2.get('publisher', '')
                    row['Year_FR_3']       = t2.get('year', '')

                # Free availability
                free_urls = [t.get('url','') for t in translations
                             if t.get('freely_available') and t.get('url')]
                row['FR_available_free'] = 'yes' if free_urls else 'no'
                row['FR_url']            = free_urls[0] if free_urls else ''

            row['FR_lookup_confidence'] = result.get('confidence', '')

            # Fill empty new fields
            for field in fieldnames:
                if field not in row:
                    row[field] = ''

            writer.writerow(row)

    print(f"Saved to {OUTPUT_CSV}")


def print_stats(rows: list, results: dict):
    """Print coverage statistics."""
    total    = len(rows)
    has_fr   = sum(1 for r in rows if r.get('Work_FR','').strip())
    looked_up = len(results)
    found    = sum(1 for r in results.values() if r.get('found'))
    free     = sum(1 for r in results.values()
                   if any(t.get('freely_available')
                          for t in r.get('translations', [])))

    print(f"Bibliography entries:      {total}")
    print(f"Already had FR translation:{has_fr}")
    print(f"Looked up via Claude:      {looked_up}")
    print(f"  Found translation:       {found}")
    print(f"  Freely available online: {free}")
    print(f"  Not found:               {looked_up - found}")
    print(f"Still to look up:          {total - looked_up}")


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--lookup',  action='store_true',
                    help='Look up French translations for all missing entries')
    ap.add_argument('--author',  help='Look up specific author (transliterated name)')
    ap.add_argument('--stats',   action='store_true', help='Show current coverage')
    ap.add_argument('--save',    action='store_true',
                    help='Save results to sl_bibliography_fr.csv')
    ap.add_argument('--limit',   type=int, default=0,
                    help='Limit number of entries to process')
    args = ap.parse_args()

    rows  = load_bibliography()
    cache = load_cache()

    if args.stats:
        print_stats(rows, cache)

    elif args.author:
        # Look up single author
        matches = [r for r in rows
                   if args.author.lower() in r.get('Author_Transliterated','').lower()]
        if not matches:
            print(f"Author '{args.author}' not found")
        else:
            client = anthropic.Anthropic(api_key=ANTHROPIC_KEY)
            for row in matches:
                sl_code = row['SL_code']
                print(f"\n{sl_code}: {row['Author_RU']} — {row['Work_RU']}")
                result = lookup_translation(row, client)
                cache[sl_code] = result
                save_cache(cache)

                if result.get('found'):
                    for t in result['translations']:
                        print(f"  ✓ {t.get('title_fr','')}")
                        print(f"    Translator: {t.get('translator','')}")
                        print(f"    Publisher:  {t.get('publisher','')} {t.get('year','')}")
                        if t.get('freely_available'):
                            print(f"    FREE: {t.get('url','')}")
                else:
                    print(f"  ✗ No French translation found")
                time.sleep(1)

    elif args.lookup:
        if not ANTHROPIC_KEY:
            print("ERROR: ANTHROPIC_API_KEY not set")
            exit(1)

        client = anthropic.Anthropic(api_key=ANTHROPIC_KEY)

        # Process entries not yet in cache
        to_process = [r for r in rows if r['SL_code'] not in cache]
        if args.limit:
            to_process = to_process[:args.limit]

        print(f"Looking up {len(to_process)} entries...")
        for i, row in enumerate(to_process):
            sl_code = row['SL_code']
            author  = row.get('Author_Transliterated', '')
            work    = row.get('Work_EN', '') or row.get('Work_RU', '')

            print(f"[{i+1}/{len(to_process)}] {author} — {work[:40]}")

            result = lookup_translation(row, client)
            cache[sl_code] = result
            save_cache(cache)

            status = '✓' if result.get('found') else '✗'
            n_trans = len(result.get('translations', []))
            free = any(t.get('freely_available')
                      for t in result.get('translations', []))
            print(f"  {status} {n_trans} translation(s) "
                  f"{'[FREE available]' if free else ''}")

            time.sleep(1.5)

        print(f"\nDone. Processed {len(to_process)} entries.")
        print_stats(rows, cache)

        if args.save:
            save_results_csv(rows, cache)

    else:
        ap.print_help()
        print("\nExamples:")
        print("  python pipeline/find_fr_translations.py --stats")
        print("  python pipeline/find_fr_translations.py --author Chekhov")
        print("  python pipeline/find_fr_translations.py --author Bulgakov")
        print("  python pipeline/find_fr_translations.py --lookup --limit 50 --save")
        print("  python pipeline/find_fr_translations.py --lookup --save  # all 247")
