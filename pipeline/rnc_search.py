#!/usr/bin/env python3
"""
NOTE (May 2026): The `rnc` Python library is currently broken against
the ruscorpora.ru website (HTML structure changed, div.content not found).

WORKAROUND: Use manual CSV export from ruscorpora.ru:
  1. Go to ruscorpora.ru → select "Параллельный французский" or main corpus
  2. Search for the idiom lemmas
  3. Click "Скачать" → CSV
  4. Save to pipeline/rnc_exports/ENTRY_ID_idiom.csv
  5. Import: python3 pipeline/rnc_db.py import pipeline/rnc_exports/FILE.csv ENTRY_ID

The PILOT_QUERIES dict below still serves as the query reference —
use those lemma strings when searching manually on ruscorpora.ru.
"""
rnc_search.py — Programmatic RNC search for dictionary idioms

Replaces manual CSV export from ruscorpora.ru website.
Uses the `rnc` Python library to search the general corpus
and optionally the Russian-French parallel corpus.

Usage:
  python3 pipeline/rnc_search.py --idiom "беда не приходить один" --entry Б-41
  python3 pipeline/rnc_search.py --idiom "беда не приходить один" --entry Б-41 --pages 3
  python3 pipeline/rnc_search.py --entry Б-41 --query_file pipeline/rnc_queries.json
"""

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent

# ============================================================
# QUERY PATTERNS FOR PILOT PAGE ENTRIES
# ============================================================
# Each entry has:
#   - lemmas: vocabulary (lemma) forms for search
#   - query: optional structured query with distance constraints
#   - sphere_filter: preferred text spheres
#   - min_sentence_words: minimum useful sentence length

PILOT_QUERIES = {
    "Б-36": {
        "idiom_ru": "В БЕГАХ",
        "query": "в бегах",
        "search_type": "lexform",   # exact form — preposition essential
        "sphere_filter": ["художественная"],
        "min_sentence_words": 8,
        "notes": "PrepP; frozen phrase — must search exact form 'в бегах'"
    },
    "Б-37": {
        "idiom_ru": "КАК БЕГЕМОТ",
        "query": "бегемот",
        "sphere_filter": ["художественная"],
        "min_sentence_words": 8,
        "notes": "comparative; толстокожий как бегемот"
    },
    "Б-38": {
        "idiom_ru": "СПАСАТЬСЯ БЕГСТВОМ",
        "query": "спасаться бегство",
        "sphere_filter": ["художественная"],
        "min_sentence_words": 8,
    },
    "Б-39": {
        "idiom_ru": "НА БЕГУ",
        "query": "на бегу",
        "search_type": "lexform",   # exact form — preposition essential
        "sphere_filter": ["художественная"],
        "min_sentence_words": 8,
        "notes": "PrepP adverbial; frozen phrase — must search exact form 'на бегу'"
    },
    "Б-40": {
        "idiom_ru": "СЕМЬ БЕД ОДИН ОТВЕТ",
        "query": "семь беда ответ",
        "sphere_filter": ["художественная", "публицистика"],
        "min_sentence_words": 6,
    },
    "Б-41": {
        "idiom_ru": "БЕДА НЕ ПРИХОДИТ ОДНА",
        "query": "беда приходить один",
        "sphere_filter": ["художественная"],
        "min_sentence_words": 8,
    },
    "Б-42": {
        "idiom_ru": "ЛИХА БЕДА",
        "query": "лихой беда",
        "sphere_filter": ["художественная"],
        "min_sentence_words": 6,
        "notes": "obsoles, coll"
    },
    "Б-43": {
        "idiom_ru": "ЛИХА БЕДА НАЧАЛО",
        "query": "лихой беда начало",
        "sphere_filter": ["художественная", "публицистика"],
        "min_sentence_words": 6,
    },
    "Б-44": {
        "idiom_ru": "НЕ БЕДА",
        "query": "не беда",
        "search_type": "lexform",   # negation is essential part of idiom
        "sphere_filter": ["художественная"],
        "min_sentence_words": 8,
        "notes": "coll; negation integral to idiom meaning"
    },
}


# ============================================================
# SEARCH FUNCTIONS
# ============================================================

def search_main_corpus(entry_id: str, 
                        pages: int = 3,
                        output_csv: str = None,
                        sphere_filter: list = None) -> list:
    """
    Search RNC main corpus for idiom examples.
    
    Returns list of example dicts with:
      author, work, year, sphere, type, sentence
    """
    try:
        import rnc
    except ImportError:
        print("ERROR: rnc package not installed. Run: pip install rnc")
        sys.exit(1)
    
    if entry_id not in PILOT_QUERIES:
        print(f"ERROR: No query defined for {entry_id}")
        print(f"Available: {list(PILOT_QUERIES.keys())}")
        sys.exit(1)
    
    config = PILOT_QUERIES[entry_id]
    query  = config.get('query') or config.get('lemmas')
    idiom  = config['idiom_ru']
    
    print(f"Searching RNC for {entry_id}: {idiom}")
    print(f"Query: {query}")
    print(f"Pages: {pages} (~{pages * 5 * 5} examples)")
    
    # Output CSV path
    if not output_csv:
        rnc_dir = REPO_ROOT / "pipeline" / "rnc_exports"
        rnc_dir.mkdir(exist_ok=True)
        safe_id = entry_id.replace('-', '')
        output_csv = str(rnc_dir / f"{safe_id}_{idiom.replace(' ', '_')[:30]}.csv")
    
    # Search
    corp = rnc.MainCorpus(
        query=query,
        p_count=pages,
        file=output_csv,
        out='normal',
        text='lexgramm',  # lemma search — finds all inflected forms
        sort='i_grtagging',
        dpp=5,   # documents per page
        spd=5,   # sentences per document
    )
    
    try:
        corp.request_examples()
    except Exception as e:
        print(f"Search error: {e}")
        return []
    
    print(f"Found {len(corp)} examples, "
          f"from {corp.amount_of_docs} documents")
    
    # Filter by sphere if specified
    spheres = sphere_filter or config.get('sphere_filter', [])
    if spheres:
        before = len(corp)
        corp.filter(lambda ex: any(s in (ex.gr_tags or '') 
                                   for s in spheres))
        print(f"After sphere filter: {len(corp)} "
              f"(removed {before - len(corp)})")
    
    # Filter by minimum sentence length
    min_words = config.get('min_sentence_words', 6)
    before = len(corp)
    corp.filter(lambda ex: len((ex.text or '').split()) >= min_words)
    print(f"After length filter: {len(corp)} "
          f"(removed {before - len(corp)})")
    
    # Convert to list of dicts
    results = []
    for ex in corp:
        results.append({
            'idiom_id':    entry_id,
            'ru_author':   getattr(ex, 'author', '') or '',
            'ru_work':     getattr(ex, 'header', '') or '',
            'ru_year':     getattr(ex, 'date', '') or '',
            'ru_sphere':   getattr(ex, 'gr_tags', '') or '',
            'ru_type':     getattr(ex, 'text_type', '') or '',
            'ru_sentence': (getattr(ex, 'text', '') or '').strip(),
            'publication': getattr(ex, 'src', '') or '',
            'rnc_source':  getattr(ex, 'doc_url', '') or '',
        })
    
    # Save to CSV
    corp.dump()
    print(f"Results saved to {output_csv}")
    
    return results


def search_parallel_corpus(entry_id: str, pages: int = 2) -> list:
    """
    Search RNC Russian-French parallel corpus.
    Returns aligned Russian-French pairs if found.
    Small corpus (67 texts) — low hit rate for idioms.
    """
    try:
        import rnc
    except ImportError:
        print("ERROR: rnc package not installed.")
        return []
    
    config = PILOT_QUERIES.get(entry_id, {})
    query  = config.get('lemmas', config.get('idiom_ru', ''))
    
    print(f"\nSearching RNC parallel (FR) corpus for {entry_id}...")
    
    corp = rnc.ParallelCorpus(
        query=query,
        p_count=pages,
        lang=rnc.Languages.fr,
        out='normal',
        text='lexgramm' if isinstance(query, dict) else 'lexform',
    )
    
    try:
        corp.request_examples()
        print(f"Parallel corpus: {len(corp)} results found")
        
        results = []
        for ex in corp:
            ru_text = getattr(ex, 'ru', '') or ''
            fr_text = getattr(ex, 'fr', '') or ''
            if ru_text and fr_text:
                results.append({
                    'idiom_id':    entry_id,
                    'ru_sentence': ru_text.strip(),
                    'fr_sentence': fr_text.strip(),
                    'ru_author':   getattr(ex, 'author', '') or '',
                    'ru_work':     getattr(ex, 'header', '') or '',
                    'source':      'rnc_parallel',
                })
        return results
        
    except Exception as e:
        print(f"Parallel search: {e} (this is expected — small corpus)")
        return []


def run_all_pilot_entries(pages: int = 2):
    """
    Run RNC search for all pilot page entries (Б-36 to Б-44).
    Import results into database.
    """
    # Import here to avoid circular import
    sys.path.insert(0, str(REPO_ROOT / 'pipeline'))
    from rnc_db import get_db, import_rnc_csv
    
    conn = get_db()
    
    for entry_id in sorted(PILOT_QUERIES.keys()):
        print(f"\n{'='*50}")
        print(f"Processing {entry_id}: "
              f"{PILOT_QUERIES[entry_id]['idiom_ru']}")
        print('='*50)
        
        # Search main corpus
        rnc_dir = REPO_ROOT / "pipeline" / "rnc_exports"
        safe_id = entry_id.replace('-', '')
        idiom   = PILOT_QUERIES[entry_id]['idiom_ru']
        csv_out = str(rnc_dir / 
                      f"{safe_id}_{idiom.replace(' ', '_')[:30]}.csv")
        
        results = search_main_corpus(entry_id, pages=pages, 
                                      output_csv=csv_out)
        
        if results:
            import_rnc_csv(csv_out, entry_id, conn)
        
        # Try parallel corpus
        par_results = search_parallel_corpus(entry_id, pages=1)
        if par_results:
            print(f"  *** Parallel corpus hit for {entry_id}! ***")
            for r in par_results:
                print(f"  RU: {r['ru_sentence'][:80]}")
                print(f"  FR: {r['fr_sentence'][:80]}")
    
    conn.close()
    print("\nAll pilot entries processed.")


# ============================================================
# MAIN
# ============================================================

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='RNC corpus search for RF Dictionary'
    )
    parser.add_argument('--entry',  help='Entry ID e.g. Б-41')
    parser.add_argument('--pages',  type=int, default=3,
                        help='Pages of results (default: 3)')
    parser.add_argument('--all',    action='store_true',
                        help='Run all pilot page entries')
    parser.add_argument('--parallel', action='store_true',
                        help='Also search parallel corpus')
    parser.add_argument('--output', help='Output CSV path')
    parser.add_argument('--import_db', action='store_true',
                        help='Import results into database')
    
    args = parser.parse_args()
    
    if args.all:
        run_all_pilot_entries(pages=args.pages)
    
    elif args.entry:
        results = search_main_corpus(
            args.entry, 
            pages=args.pages,
            output_csv=args.output
        )
        
        if args.parallel:
            par = search_parallel_corpus(args.entry, pages=2)
            if par:
                print(f"\n*** {len(par)} parallel corpus hits! ***")
                for r in par:
                    print(f"RU: {r['ru_sentence']}")
                    print(f"FR: {r['fr_sentence']}")
                    print()
        
        if args.import_db and results:
            sys.path.insert(0, str(REPO_ROOT / 'pipeline'))
            from rnc_db import get_db, import_rnc_csv
            conn = get_db()
            csv_path = args.output or str(
                REPO_ROOT / "pipeline" / "rnc_exports" / 
                f"{args.entry.replace('-','')}_results.csv"
            )
            import_rnc_csv(csv_path, args.entry, conn)
            conn.close()
        
        # Print top results
        print(f"\nTop results ({len(results)} total):")
        for i, r in enumerate(results[:5], 1):
            print(f"\n{i}. {r['ru_author']} — {r['ru_work']} "
                  f"({r['ru_year']})")
            print(f"   {r['ru_sentence'][:100]}")
    
    else:
        parser.print_help()
        print("\nAvailable entries:")
        for eid, cfg in PILOT_QUERIES.items():
            print(f"  {eid}: {cfg['idiom_ru']}")
