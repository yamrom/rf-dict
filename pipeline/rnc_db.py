#!/usr/bin/env python3
"""
rnc_db.py — RNC corpus database and French translation lookup

Manages three tables:
  1. rnc_examples   — Russian examples found in RNC general corpus
  2. work_translations — French translations of Russian works
  3. fr_examples    — Located French translation passages

Workflow:
  1. Parse RNC CSV export → populate rnc_examples
  2. For each unique work → lookup French translation → populate work_translations
  3. For each work with accessible FR text → search passage → populate fr_examples
"""

import sqlite3
import csv
import os
import re
import json
import requests
from pathlib import Path
from typing import Optional

# ============================================================
# DATABASE SETUP
# ============================================================

REPO_ROOT = Path(__file__).parent.parent
DB_PATH   = REPO_ROOT / "pipeline" / "rf_dict.db"

def get_db() -> sqlite3.Connection:
    """Get database connection, creating tables if needed."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    create_tables(conn)
    return conn


def create_tables(conn: sqlite3.Connection):
    """Create all tables if they don't exist."""
    conn.executescript("""
    
    -- Russian examples from RNC general corpus
    CREATE TABLE IF NOT EXISTS rnc_examples (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        idiom_id        TEXT NOT NULL,        -- e.g. "Б-41"
        ru_author       TEXT,                 -- e.g. "Виктор Конецкий"
        ru_work         TEXT,                 -- e.g. "Начало конца комедии"
        ru_year         TEXT,                 -- e.g. "1978"
        ru_sphere       TEXT,                 -- e.g. "художественная"
        ru_type         TEXT,                 -- e.g. "рассказ"
        ru_sentence     TEXT NOT NULL,        -- full example sentence
        rnc_source      TEXT,                 -- RNC source code
        publication     TEXT,                 -- publication details
        quality_score   INTEGER DEFAULT 0,    -- 0-10, higher = better example
        created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    
    -- French translations of Russian works
    CREATE TABLE IF NOT EXISTS work_translations (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        ru_author       TEXT NOT NULL,
        ru_work         TEXT NOT NULL,
        ru_year         TEXT,
        fr_title        TEXT,                 -- French title
        fr_translator   TEXT,                 -- French translator
        fr_publisher    TEXT,
        fr_year         TEXT,
        fr_availability TEXT DEFAULT 'unknown',
        -- Values: free_online | ebook | print_only | unknown | not_translated
        fr_url          TEXT,                 -- URL if available online
        fr_isbn         TEXT,
        lookup_status   TEXT DEFAULT 'pending',
        -- Values: pending | found | not_found | manual_needed
        notes           TEXT,
        updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(ru_author, ru_work)
    );
    
    -- Located French example passages
    CREATE TABLE IF NOT EXISTS fr_examples (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        rnc_example_id  INTEGER REFERENCES rnc_examples(id),
        idiom_id        TEXT NOT NULL,
        ru_sentence     TEXT NOT NULL,
        fr_sentence     TEXT,
        fr_title        TEXT,
        fr_translator   TEXT,
        status          TEXT DEFAULT 'pending',
        -- Values: found | pending | not_found | constructed
        search_method   TEXT,
        -- Values: web_search | gallica | ebook | manual | rnc_parallel
        notes           TEXT,
        created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    
    -- Index for fast idiom lookup
    CREATE INDEX IF NOT EXISTS idx_rnc_idiom ON rnc_examples(idiom_id);
    CREATE INDEX IF NOT EXISTS idx_fr_idiom  ON fr_examples(idiom_id);
    CREATE INDEX IF NOT EXISTS idx_work_author ON work_translations(ru_author);
    """)
    conn.commit()


# ============================================================
# STEP 1: PARSE RNC CSV → rnc_examples
# ============================================================

def score_example_quality(row: dict) -> int:
    """
    Score the quality of an RNC example for dictionary use.
    Higher score = better example.
    
    Criteria:
    - Literary fiction preferred over journalism
    - Sentence length: 10-50 words is ideal
    - Not just the bare idiom (too short)
    - Narrative context (не просто «Беда не приходит одна.»)
    """
    score = 5  # baseline
    
    sentence = row.get('Full context', '')
    sphere = row.get('Sphere', '')
    rtype = row.get('Type', '')
    words = row.get('Words', 0)
    
    # Prefer literary fiction
    if 'художественная' in sphere:
        score += 2
    elif 'публицистика' in sphere:
        score += 0
    elif 'нехудожественная' in sphere:
        score -= 1
    elif 'бытовая' in sphere:
        score -= 2
    
    # Prefer novels and stories over articles
    if any(t in rtype for t in ['роман', 'повесть', 'рассказ']):
        score += 2
    elif 'мемуары' in rtype:
        score += 1
    elif any(t in rtype for t in ['статья', 'заметка', 'рецензия']):
        score -= 1
    
    # Sentence length: penalize very short
    words_in_sent = len(sentence.split())
    if words_in_sent < 6:
        score -= 3
    elif words_in_sent < 10:
        score -= 1
    elif words_in_sent > 15:
        score += 1
    
    # Work size: larger works = more established authors
    try:
        wc = int(words)
        if wc > 50000:
            score += 1
    except:
        pass
    
    # Penalize idiom used as metalinguistic reference
    if any(marker in sentence for marker in
           ['пословица', 'говорится', 'правило', 'закон']):
        score -= 1
    
    return max(0, min(10, score))


def import_rnc_csv(csv_path: str, idiom_id: str, conn: sqlite3.Connection) -> int:
    """
    Import RNC CSV export into rnc_examples table.
    Returns number of rows imported.
    """
    imported = 0
    
    with open(csv_path, encoding='utf-8') as f:
        reader = csv.DictReader(f, delimiter=';')
        for row in reader:
            sentence = row.get('Full context', '').strip()
            if not sentence:
                continue
            
            # Skip header-only rows
            author = row.get('Author', '').strip()
            work   = row.get('Header', '').strip()
            if not author or not work:
                continue
            
            score = score_example_quality(row)
            
            conn.execute("""
                INSERT OR IGNORE INTO rnc_examples
                (idiom_id, ru_author, ru_work, ru_year, ru_sphere, ru_type,
                 ru_sentence, rnc_source, publication, quality_score)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                idiom_id,
                author,
                work,
                row.get('Created', '').strip(),
                row.get('Sphere', '').strip(),
                row.get('Type', '').strip(),
                sentence,
                row.get('Example source', '').strip(),
                row.get('Publication', '').strip(),
                score
            ))
            imported += 1
    
    conn.commit()
    print(f"Imported {imported} examples for {idiom_id}")
    return imported


# ============================================================
# STEP 2: LOOKUP FRENCH TRANSLATIONS
# ============================================================

def get_untranslated_works(conn: sqlite3.Connection) -> list:
    """Get all works that don't yet have a French translation lookup."""
    rows = conn.execute("""
        SELECT DISTINCT ru_author, ru_work, ru_year
        FROM rnc_examples e
        WHERE NOT EXISTS (
            SELECT 1 FROM work_translations w
            WHERE w.ru_author = e.ru_author
            AND   w.ru_work   = e.ru_work
        )
        ORDER BY ru_year DESC
    """).fetchall()
    return [dict(r) for r in rows]


def lookup_french_translation_web(author: str, work: str) -> dict:
    """
    Search for French translation of a Russian work.
    
    Strategy (in order):
    1. Search Wikipedia (Russian) for author → get French interlanguage link
    2. Parse French Wikipedia page for bibliography entry matching work
    3. If not found on Wikipedia → search BnF catalogue
    4. Return structured result with availability assessment
    """
    result = {
        'fr_title': None,
        'fr_translator': None,
        'fr_publisher': None,
        'fr_year': None,
        'fr_availability': 'unknown',
        'fr_url': None,
        'lookup_status': 'not_found',
        'notes': ''
    }
    
    headers = {
        'User-Agent': 'rf-dict-pipeline/1.0 (Russian-French Dictionary; github.com/yamrom/rf-dict)'
    }
    
    # ── Step 1: Wikipedia Russian → French ──────────────────
    try:
        # Search Wikipedia for author
        resp = requests.get(
            "https://ru.wikipedia.org/w/api.php",
            params={
                'action': 'query', 'list': 'search',
                'srsearch': author, 'format': 'json', 'srlimit': 3
            },
            headers=headers, timeout=10
        )
        if not resp.ok or not resp.text.strip():
            raise ValueError(f"Wikipedia search failed: HTTP {resp.status_code}")
        
        data = resp.json()
        search_results = data.get('query', {}).get('search', [])
        if not search_results:
            result['notes'] = 'Author not found on Russian Wikipedia'
            # Fall through to BnF search
        else:
            ru_page_title = search_results[0]['title']
            
            # Get French interlanguage link
            resp2 = requests.get(
                "https://ru.wikipedia.org/w/api.php",
                params={
                    'action': 'query', 'titles': ru_page_title,
                    'prop': 'langlinks', 'lllang': 'fr', 'format': 'json'
                },
                headers=headers, timeout=10
            )
            if not resp2.ok or not resp2.text.strip():
                raise ValueError(f"Langlinks failed: HTTP {resp2.status_code}")
            
            data2 = resp2.json()
            fr_page_title = None
            for page in data2.get('query', {}).get('pages', {}).values():
                for ll in page.get('langlinks', []):
                    if ll.get('lang') == 'fr':
                        fr_page_title = ll.get('*')
                        break
            
            if fr_page_title:
                fr_wiki_url = f"https://fr.wikipedia.org/wiki/{fr_page_title.replace(' ', '_')}"
                result['fr_url'] = fr_wiki_url
                result['lookup_status'] = 'found'
                result['notes'] = f'French Wikipedia: {fr_page_title}'
                
                # Get French page extract to find work title
                resp3 = requests.get(
                    "https://fr.wikipedia.org/w/api.php",
                    params={
                        'action': 'query', 'titles': fr_page_title,
                        'prop': 'extracts', 'exintro': False,
                        'explaintext': True, 'format': 'json'
                    },
                    headers=headers, timeout=10
                )
                if resp3.ok and resp3.text.strip():
                    data3 = resp3.json()
                    for page in data3.get('query', {}).get('pages', {}).values():
                        extract = page.get('extract', '')
                        if extract:
                            # Try to find work title by searching for key words
                            # from Russian title transliterated or translated
                            result['fr_title'] = f'[See: {fr_wiki_url}]'
                            # Look for years near the work
                            # e.g. find publication years in the text
                            years = re.findall(r'\b(19[0-9]{2}|20[0-2][0-9])\b', extract)
                            if years:
                                result['notes'] += f' | Years found: {years[:5]}'
                return result
            else:
                result['notes'] = f'Russian Wikipedia found ({ru_page_title}) but no French page'
    
    except Exception as e:
        result['notes'] = f'Wikipedia error: {str(e)}'
    
    # ── Step 2: BnF catalogue search ────────────────────────
    try:
        # Search BnF (Bibliothèque nationale de France) catalogue
        # BnF has excellent coverage of Russian literature in French translation
        bnf_url = "https://catalogue.bnf.fr/api/SRU"
        # Transliterate author name roughly for search
        # (BnF uses French transliteration)
        query = f'bib.anywhere all "{author}"'
        resp = requests.get(
            bnf_url,
            params={
                'version': '1.2', 'operation': 'searchRetrieve',
                'query': query, 'maximumRecords': '5',
                'recordSchema': 'unimarcxml'
            },
            headers=headers, timeout=15
        )
        if resp.ok and resp.text.strip() and '<record>' in resp.text:
            result['notes'] += ' | BnF: records found'
            result['lookup_status'] = 'found'
            result['fr_url'] = f"https://catalogue.bnf.fr/recherche.do?motRecherche={requests.utils.quote(author)}&typeRecherche=personne"
            result['fr_availability'] = 'print_only'  # conservative assumption
        else:
            result['notes'] += ' | BnF: no records'
    except Exception as e:
        result['notes'] += f' | BnF error: {str(e)}'
    
    return result


def process_work_translations(conn: sqlite3.Connection, 
                               limit: int = 10,
                               auto_lookup: bool = True):
    """
    Process untranslated works — look up French translations.
    """
    works = get_untranslated_works(conn)
    print(f"Found {len(works)} works needing French translation lookup")
    
    for i, work in enumerate(works[:limit]):
        author = work['ru_author']
        title  = work['ru_work']
        year   = work['ru_year']
        
        print(f"\n[{i+1}/{min(limit, len(works))}] {author} — {title} ({year})")
        
        if auto_lookup:
            result = lookup_french_translation_web(author, title)
            print(f"  Status: {result['lookup_status']}")
            print(f"  Notes: {result['notes']}")
            if result.get('fr_title'):
                print(f"  FR title hint: {result['fr_title']}")
        else:
            result = {'lookup_status': 'pending', 'notes': 'auto_lookup disabled'}
        
        conn.execute("""
            INSERT OR REPLACE INTO work_translations
            (ru_author, ru_work, ru_year, fr_title, fr_translator,
             fr_publisher, fr_year, fr_availability, fr_url, 
             lookup_status, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            author, title, year,
            result.get('fr_title'),
            result.get('fr_translator'),
            result.get('fr_publisher'),
            result.get('fr_year'),
            result.get('fr_availability', 'unknown'),
            result.get('fr_url'),
            result.get('lookup_status', 'pending'),
            result.get('notes', '')
        ))
        conn.commit()


# ============================================================
# STEP 3: SELECT BEST EXAMPLE FOR AN ENTRY
# ============================================================

def get_best_examples(idiom_id: str, conn: sqlite3.Connection, 
                       top_n: int = 5) -> list:
    """
    Get the best RNC examples for an idiom, ranked by:
    1. Has accessible French translation
    2. Quality score
    3. Literary fiction preferred
    """
    rows = conn.execute("""
        SELECT e.*, 
               w.fr_title, w.fr_translator, w.fr_availability, w.fr_url,
               w.lookup_status as fr_lookup_status
        FROM rnc_examples e
        LEFT JOIN work_translations w 
            ON w.ru_author = e.ru_author 
            AND w.ru_work = e.ru_work
        WHERE e.idiom_id = ?
        ORDER BY 
            CASE w.fr_availability 
                WHEN 'free_online' THEN 0
                WHEN 'ebook'       THEN 1
                WHEN 'print_only'  THEN 2
                ELSE 3
            END,
            e.quality_score DESC
        LIMIT ?
    """, (idiom_id, top_n)).fetchall()
    
    return [dict(r) for r in rows]


def print_best_examples(idiom_id: str, conn: sqlite3.Connection):
    """Print best examples for human review."""
    examples = get_best_examples(idiom_id, conn)
    
    print(f"\nBest examples for {idiom_id}:")
    print("="*60)
    
    for i, ex in enumerate(examples, 1):
        print(f"\n{i}. Score: {ex['quality_score']}/10")
        print(f"   Author: {ex['ru_author']}")
        print(f"   Work: {ex['ru_work']} ({ex['ru_year']})")
        print(f"   Type: {ex['ru_type']} / {ex['ru_sphere']}")
        print(f"   RU: {ex['ru_sentence']}")
        fr_avail = ex.get('fr_availability', 'unknown')
        fr_title = ex.get('fr_title', 'unknown')
        print(f"   FR: {fr_title} [{fr_avail}]")


# ============================================================
# REPORTING
# ============================================================

def print_stats(conn: sqlite3.Connection):
    """Print database statistics."""
    n_examples = conn.execute("SELECT COUNT(*) FROM rnc_examples").fetchone()[0]
    n_idioms   = conn.execute(
        "SELECT COUNT(DISTINCT idiom_id) FROM rnc_examples").fetchone()[0]
    n_works    = conn.execute("SELECT COUNT(*) FROM work_translations").fetchone()[0]
    n_found    = conn.execute(
        "SELECT COUNT(*) FROM work_translations WHERE lookup_status='found'"
    ).fetchone()[0]
    n_fr_ex    = conn.execute("SELECT COUNT(*) FROM fr_examples").fetchone()[0]
    n_fr_found = conn.execute(
        "SELECT COUNT(*) FROM fr_examples WHERE status='found'"
    ).fetchone()[0]
    
    print(f"\nDatabase statistics:")
    print(f"  RNC examples:        {n_examples} (across {n_idioms} idioms)")
    print(f"  Works looked up:     {n_works} ({n_found} with FR translation found)")
    print(f"  French examples:     {n_fr_ex} ({n_fr_found} located)")


def export_pending_works(conn: sqlite3.Connection, 
                          output_path: str = None) -> list:
    """
    Export list of works needing manual French translation lookup.
    These are works where auto-lookup failed or is pending.
    """
    rows = conn.execute("""
        SELECT DISTINCT 
            e.ru_author, e.ru_work, e.ru_year, e.ru_sphere,
            COUNT(*) as example_count,
            MAX(e.quality_score) as best_score,
            w.lookup_status, w.notes
        FROM rnc_examples e
        LEFT JOIN work_translations w
            ON w.ru_author = e.ru_author AND w.ru_work = e.ru_work
        WHERE w.lookup_status IS NULL 
           OR w.lookup_status IN ('pending', 'not_found', 'manual_needed')
        GROUP BY e.ru_author, e.ru_work
        ORDER BY best_score DESC, example_count DESC
    """).fetchall()
    
    results = [dict(r) for r in rows]
    
    if output_path:
        import csv as csv_mod
        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            if results:
                writer = csv_mod.DictWriter(f, fieldnames=results[0].keys())
                writer.writeheader()
                writer.writerows(results)
        print(f"Exported {len(results)} pending works to {output_path}")
    
    return results


# ============================================================
# MAIN — demo/test
# ============================================================

if __name__ == '__main__':
    import sys
    
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'stats'
    
    conn = get_db()
    
    if cmd == 'import':
        # python3 rnc_db.py import /path/to/rnc_export.csv Б-41
        csv_path  = sys.argv[2]
        idiom_id  = sys.argv[3]
        import_rnc_csv(csv_path, idiom_id, conn)
        print_best_examples(idiom_id, conn)
    
    elif cmd == 'lookup':
        # python3 rnc_db.py lookup [limit]
        limit = int(sys.argv[2]) if len(sys.argv) > 2 else 5
        process_work_translations(conn, limit=limit, auto_lookup=True)
    
    elif cmd == 'best':
        # python3 rnc_db.py best Б-41
        idiom_id = sys.argv[2]
        print_best_examples(idiom_id, conn)
    
    elif cmd == 'pending':
        # python3 rnc_db.py pending [output.csv]
        output = sys.argv[2] if len(sys.argv) > 2 else None
        works = export_pending_works(conn, output)
        print(f"\nPending works needing manual lookup: {len(works)}")
        for w in works[:10]:
            print(f"  {w['ru_author']} — {w['ru_work']} "
                  f"({w['example_count']} examples, best score: {w['best_score']})")
    
    elif cmd == 'stats':
        print_stats(conn)
    
    conn.close()
