#!/usr/bin/env python3
"""
idiom_match.py — Semantic paraphrase-based idiom matching

For each Russian idiom:
1. Generate Russian paraphrase (plain language, no idioms)
2. Translate paraphrase to French
3. Compare against French idiom paraphrases
4. Find best matching French idiom (Type A) or use paraphrase as definition (Type B)

Usage:
  python3 pipeline/idiom_match.py --idiom "беда не приходит одна" --entry Б-41
  python3 pipeline/idiom_match.py --all_pilot
  python3 pipeline/idiom_match.py --build_fr_db  # build French idiom paraphrase DB
"""

import os
import sys
import json
import sqlite3
import argparse
import time
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
DB_PATH   = REPO_ROOT / "pipeline" / "rf_dict.db"

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
CLAUDE_MODEL = "claude-sonnet-4-5"

# ============================================================
# PILOT PAGE IDIOMS — for testing
# ============================================================

PILOT_IDIOMS = {
    "Б-36": {
        "ru": "в бегах",
        "grammar": "[PrepP; Invar; subj-compl with быть]",
        "en_gloss": "hiding from the police, on the run"
    },
    "Б-37": {
        "ru": "толстокожий как бегемот (слон, носорог)",
        "grammar": "[coll, disapprov; AdjP; modif]",
        "en_gloss": "insensitive, unfeeling person"
    },
    "Б-38": {
        "ru": "спасаться/спастись бегством",
        "grammar": "[VP; subj: human or animal]",
        "en_gloss": "to run away from danger or threat"
    },
    "Б-39": {
        "ru": "на бегу",
        "grammar": "[PrepP; Invar; adv]",
        "en_gloss": "hastily, while running or rushing"
    },
    "Б-40": {
        "ru": "семь бед — один ответ",
        "grammar": "[saying]",
        "en_gloss": "one might as well be hanged for a sheep as a lamb"
    },
    "Б-41": {
        "ru": "беда не приходит одна",
        "grammar": "[saying]",
        "en_gloss": "troubles never come singly, when it rains it pours"
    },
    "Б-42": {
        "ru": "лиха беда",
        "grammar": "[obsoles, coll; NP; Invar; impers predic]",
        "en_gloss": "one has only to do something, one need only"
    },
    "Б-43": {
        "ru": "лиха беда начало (начать)",
        "grammar": "[saying]",
        "en_gloss": "the first step is the hardest, well begun is half done"
    },
    "Б-44": {
        "ru": "не беда",
        "grammar": "[coll; NP; Invar; subj-compl with быть]",
        "en_gloss": "it doesn't matter, no big deal"
    },
}


# ============================================================
# DATABASE SETUP
# ============================================================

def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS idiom_paraphrases (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        entry_id        TEXT NOT NULL,
        idiom_ru        TEXT NOT NULL,
        ru_paraphrase   TEXT,
        fr_translation  TEXT,
        created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(entry_id)
    );
    
    CREATE TABLE IF NOT EXISTS fr_idiom_db (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        fr_idiom        TEXT NOT NULL UNIQUE,
        fr_paraphrase   TEXT,
        fr_source       TEXT,  -- e.g. 'CNRTL', 'Wiktionnaire'
        ru_translation  TEXT,  -- translation of paraphrase to Russian
        created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    
    CREATE TABLE IF NOT EXISTS idiom_matches (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        entry_id        TEXT NOT NULL,
        fr_idiom        TEXT,
        similarity_score INTEGER,  -- 0-10
        match_type      TEXT,      -- 'A' (idiomatic) or 'B' (paraphrase only)
        explanation     TEXT,
        ru_paraphrase   TEXT,
        fr_paraphrase   TEXT,
        created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(entry_id)
    );
    """)
    conn.commit()
    return conn


# ============================================================
# CLAUDE API CALL
# ============================================================

def call_claude(prompt: str, max_tokens: int = 1000) -> str:
    """Call Claude API and return response text."""
    if not ANTHROPIC_API_KEY:
        raise ValueError("ANTHROPIC_API_KEY not set")
    
    import anthropic
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    
    message = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}]
    )
    return message.content[0].text.strip()


def call_claude_json(prompt: str, max_tokens: int = 1000) -> dict:
    """Call Claude API and parse JSON response."""
    response = call_claude(prompt, max_tokens)
    
    # Strip markdown code blocks if present
    import re
    response = re.sub(r'^```(?:json)?\s*', '', response, flags=re.MULTILINE)
    response = re.sub(r'\s*```$', '', response, flags=re.MULTILINE)
    
    try:
        return json.loads(response.strip())
    except json.JSONDecodeError as e:
        print(f"JSON parse error: {e}")
        print(f"Response was: {response[:200]}")
        return {}


# ============================================================
# STEP 1: GENERATE RUSSIAN PARAPHRASE + FRENCH TRANSLATION
# ============================================================

def generate_paraphrase(entry_id: str, idiom_ru: str, 
                         grammar: str, en_gloss: str) -> dict:
    """
    Generate:
    1. Russian plain-language paraphrase of the idiom
    2. French translation of that paraphrase
    """
    prompt = f"""You are working on a Russian–French dictionary of idioms.

Russian idiom: «{idiom_ru}»
Grammatical type: {grammar}
Approximate English meaning: {en_gloss}

Please provide:

1. A plain Russian paraphrase of this idiom — describe its meaning in ordinary Russian,
   without using the idiom itself or other idioms. 1–2 clear sentences.
   Capture: the core meaning, when/why it is used, and any pragmatic nuance
   (irony, resignation, encouragement, etc.).

2. A French translation of that Russian paraphrase — translate your Russian paraphrase
   into natural French. This should read as plain, clear French prose, not a translation
   of the idiom itself.

Return ONLY valid JSON in this exact format:
{{
  "ru_paraphrase": "...",
  "fr_translation": "...",
  "pragmatic_note": "brief note on usage context (1 sentence)"
}}"""

    print(f"  Generating paraphrase for {entry_id}: «{idiom_ru}»...")
    result = call_claude_json(prompt)
    
    if result:
        print(f"  RU: {result.get('ru_paraphrase','')[:80]}")
        print(f"  FR: {result.get('fr_translation','')[:80]}")
    
    return result


# ============================================================
# STEP 2: MATCH AGAINST FRENCH IDIOM DATABASE
# ============================================================

# Seed French idioms for pilot testing
# In production this comes from CNRTL/PolylexFLE database
SEED_FR_IDIOMS = [
    {
        "fr_idiom": "un malheur ne vient jamais seul",
        "fr_paraphrase": "Quand un problème ou un malheur survient, d'autres ont tendance à suivre peu après, sans laisser de répit.",
        "fr_source": "CNRTL"
    },
    {
        "fr_idiom": "autant être pendu pour un mouton que pour un agneau",
        "fr_paraphrase": "Puisqu'on risque déjà une punition pour une faute mineure, autant commettre une faute plus grave et en tirer davantage profit.",
        "fr_source": "CNRTL"
    },
    {
        "fr_idiom": "il n'y a que le premier pas qui coûte",
        "fr_paraphrase": "Commencer une tâche est la partie la plus difficile ; une fois démarré, le reste est plus facile.",
        "fr_source": "CNRTL"
    },
    {
        "fr_idiom": "ce n'est pas grave",
        "fr_paraphrase": "La situation ou l'événement n'a pas d'importance significative et ne mérite pas d'inquiétude.",
        "fr_source": "courant"
    },
    {
        "fr_idiom": "prendre ses jambes à son cou",
        "fr_paraphrase": "Partir en courant très vite pour fuir un danger ou une situation difficile.",
        "fr_source": "CNRTL"
    },
    {
        "fr_idiom": "à la va-vite",
        "fr_paraphrase": "De manière précipitée, sans prendre le temps de faire les choses correctement, en hâte.",
        "fr_source": "CNRTL"
    },
    {
        "fr_idiom": "avoir la peau dure",
        "fr_paraphrase": "Être insensible aux critiques, aux émotions des autres ou aux difficultés de la vie.",
        "fr_source": "CNRTL"
    },
    {
        "fr_idiom": "prendre la fuite",
        "fr_paraphrase": "S'enfuir, quitter précipitamment un lieu pour échapper à un danger ou une menace.",
        "fr_source": "courant"
    },
    {
        "fr_idiom": "être en cavale",
        "fr_paraphrase": "Être en fuite, se cacher pour échapper à la justice ou aux autorités.",
        "fr_source": "fam."
    },
    {
        "fr_idiom": "bien mal acquis ne profite jamais",
        "fr_paraphrase": "Les biens obtenus de façon malhonnête ou injuste finissent toujours par causer du tort à celui qui les possède.",
        "fr_source": "CNRTL"
    },
    {
        "fr_idiom": "quand le vin est tiré il faut le boire",
        "fr_paraphrase": "Quand on a commencé quelque chose, on doit aller jusqu'au bout, même si cela devient difficile.",
        "fr_source": "CNRTL"
    },
    {
        "fr_idiom": "épais comme une bûche",
        "fr_paraphrase": "Très stupide ou insensible, incapable de comprendre des choses subtiles ou de ressentir ce que vivent les autres.",
        "fr_source": "fam."
    },
]


def seed_fr_idiom_db(conn: sqlite3.Connection):
    """Populate French idiom database with seed entries."""
    for item in SEED_FR_IDIOMS:
        conn.execute("""
            INSERT OR IGNORE INTO fr_idiom_db 
            (fr_idiom, fr_paraphrase, fr_source)
            VALUES (?, ?, ?)
        """, (item['fr_idiom'], item['fr_paraphrase'], item['fr_source']))
    conn.commit()
    print(f"Seeded {len(SEED_FR_IDIOMS)} French idioms into database")


def match_against_fr_db(entry_id: str, fr_translation: str, 
                          ru_paraphrase: str,
                          conn: sqlite3.Connection) -> dict:
    """
    Match the French translation of the Russian paraphrase 
    against all French idiom paraphrases in the database.
    Ask Claude to find the best match and score it.
    """
    # Get all French idioms from DB
    fr_idioms = conn.execute(
        "SELECT fr_idiom, fr_paraphrase, fr_source FROM fr_idiom_db"
    ).fetchall()
    
    if not fr_idioms:
        print("  No French idioms in database — seeding...")
        seed_fr_idiom_db(conn)
        fr_idioms = conn.execute(
            "SELECT fr_idiom, fr_paraphrase, fr_source FROM fr_idiom_db"
        ).fetchall()
    
    # Build the list of French idioms with their paraphrases
    fr_list = "\n".join([
        f"{i+1}. «{row['fr_idiom']}»: {row['fr_paraphrase']}"
        for i, row in enumerate(fr_idioms)
    ])
    
    prompt = f"""You are working on a Russian–French dictionary of idioms.

A Russian idiom has been paraphrased in plain language, and that paraphrase 
has been translated into French:

French translation of Russian paraphrase:
«{fr_translation}»

Below is a list of French idiomatic expressions with their own plain-language paraphrases.
Find the French idiom whose paraphrase most closely matches the meaning above.

French idioms:
{fr_list}

Evaluate each candidate and return the best match.
If the best match has a similarity score of 6 or above, it is a Type A match 
(equivalent idiomatic expression). Below 6 is Type B (no good idiomatic equivalent).

Return ONLY valid JSON:
{{
  "best_match_number": N,
  "best_fr_idiom": "...",
  "similarity_score": N,
  "match_type": "A" or "B",
  "explanation": "brief explanation of why this is or isn't a good match (2-3 sentences)",
  "register_note": "any difference in register or usage between the two idioms"
}}

If no idiom scores 6 or above, set match_type to "B", best_fr_idiom to null, 
and similarity_score to the highest score found."""

    print(f"  Matching against {len(fr_idioms)} French idioms...")
    result = call_claude_json(prompt, max_tokens=600)
    
    # Enrich result with the matched idiom's paraphrase
    if result and result.get('best_match_number'):
        idx = result['best_match_number'] - 1
        if 0 <= idx < len(fr_idioms):
            result['fr_paraphrase'] = fr_idioms[idx]['fr_paraphrase']
            result['fr_source'] = fr_idioms[idx]['fr_source']
    
    return result


# ============================================================
# MAIN PIPELINE FUNCTION
# ============================================================

def process_entry(entry_id: str, idiom_info: dict, 
                   conn: sqlite3.Connection,
                   force: bool = False) -> dict:
    """
    Full pipeline for one entry:
    1. Generate Russian paraphrase + French translation
    2. Match against French idiom database
    3. Store results
    """
    # Check if already processed
    existing = conn.execute(
        "SELECT * FROM idiom_matches WHERE entry_id=?", (entry_id,)
    ).fetchone()
    
    if existing and not force:
        print(f"\n{entry_id}: Already processed (use --force to rerun)")
        return dict(existing)
    
    print(f"\n{'='*55}")
    print(f"Processing {entry_id}: «{idiom_info['ru']}»")
    print('='*55)
    
    # Step 1: Generate paraphrase
    paraphrase = generate_paraphrase(
        entry_id,
        idiom_info['ru'],
        idiom_info.get('grammar', ''),
        idiom_info.get('en_gloss', '')
    )
    
    if not paraphrase:
        print(f"  ERROR: Failed to generate paraphrase for {entry_id}")
        return {}
    
    # Store paraphrase
    conn.execute("""
        INSERT OR REPLACE INTO idiom_paraphrases
        (entry_id, idiom_ru, ru_paraphrase, fr_translation)
        VALUES (?, ?, ?, ?)
    """, (
        entry_id,
        idiom_info['ru'],
        paraphrase.get('ru_paraphrase', ''),
        paraphrase.get('fr_translation', '')
    ))
    conn.commit()
    
    # Small delay to avoid API rate limiting
    time.sleep(1)
    
    # Step 2: Match against French idiom database
    match = match_against_fr_db(
        entry_id,
        paraphrase.get('fr_translation', ''),
        paraphrase.get('ru_paraphrase', ''),
        conn
    )
    
    if not match:
        print(f"  ERROR: Matching failed for {entry_id}")
        return {}
    
    match_type = match.get('match_type', 'B')
    fr_idiom = match.get('best_fr_idiom', '')
    score = match.get('similarity_score', 0)
    
    print(f"\n  Result: Type {match_type} match")
    if fr_idiom:
        print(f"  French idiom: «{fr_idiom}» (score: {score}/10)")
    print(f"  Explanation: {match.get('explanation','')[:100]}")
    
    # Store match
    conn.execute("""
        INSERT OR REPLACE INTO idiom_matches
        (entry_id, fr_idiom, similarity_score, match_type,
         explanation, ru_paraphrase, fr_paraphrase)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        entry_id,
        fr_idiom,
        score,
        match_type,
        match.get('explanation', ''),
        paraphrase.get('ru_paraphrase', ''),
        match.get('fr_paraphrase', '')
    ))
    conn.commit()
    
    return {
        'entry_id': entry_id,
        'idiom_ru': idiom_info['ru'],
        'ru_paraphrase': paraphrase.get('ru_paraphrase', ''),
        'fr_translation': paraphrase.get('fr_translation', ''),
        'fr_idiom': fr_idiom,
        'similarity_score': score,
        'match_type': match_type,
        'explanation': match.get('explanation', ''),
        'pragmatic_note': paraphrase.get('pragmatic_note', '')
    }


def print_results(conn: sqlite3.Connection):
    """Print all matching results in a readable format."""
    rows = conn.execute("""
        SELECT m.*, p.fr_translation
        FROM idiom_matches m
        LEFT JOIN idiom_paraphrases p ON p.entry_id = m.entry_id
        ORDER BY m.entry_id
    """).fetchall()
    
    print(f"\n{'='*60}")
    print(f"IDIOM MATCHING RESULTS ({len(rows)} entries)")
    print('='*60)
    
    type_a = [r for r in rows if r['match_type'] == 'A']
    type_b = [r for r in rows if r['match_type'] == 'B']
    
    print(f"Type A (idiomatic match): {len(type_a)}")
    print(f"Type B (paraphrase only): {len(type_b)}")
    
    for row in rows:
        print(f"\n{row['entry_id']} — Type {row['match_type']} "
              f"(score: {row['similarity_score']}/10)")
        print(f"  RU paraphrase: {row['ru_paraphrase'][:90]}")
        print(f"  FR translation: {(row['fr_translation'] or '')[:90]}")
        if row['match_type'] == 'A':
            print(f"  ✅ FR idiom: «{row['fr_idiom']}»")
            print(f"  FR paraphrase: {(row['fr_paraphrase'] or '')[:90]}")
        else:
            print(f"  ⚠️  No idiomatic match found")
        print(f"  Note: {(row['explanation'] or '')[:100]}")


# ============================================================
# MAIN
# ============================================================

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Idiom paraphrase matching pipeline'
    )
    parser.add_argument('--entry',   help='Single entry ID e.g. Б-41')
    parser.add_argument('--all_pilot', action='store_true',
                        help='Process all pilot page entries')
    parser.add_argument('--results', action='store_true',
                        help='Show stored results')
    parser.add_argument('--seed_fr', action='store_true',
                        help='Seed French idiom database')
    parser.add_argument('--force',   action='store_true',
                        help='Reprocess even if already done')
    
    args = parser.parse_args()
    
    if not ANTHROPIC_API_KEY:
        print("ERROR: ANTHROPIC_API_KEY not set")
        print("Set it in .env or: export ANTHROPIC_API_KEY='sk-ant-...'")
        sys.exit(1)
    
    conn = get_db()
    
    if args.seed_fr:
        seed_fr_idiom_db(conn)
    
    elif args.results:
        print_results(conn)
    
    elif args.entry:
        if args.entry not in PILOT_IDIOMS:
            print(f"Unknown entry: {args.entry}")
            print(f"Available: {list(PILOT_IDIOMS.keys())}")
            sys.exit(1)
        result = process_entry(
            args.entry, PILOT_IDIOMS[args.entry], conn, args.force
        )
        if result:
            print(f"\n✓ Done: {args.entry}")
    
    elif args.all_pilot:
        print(f"Processing all {len(PILOT_IDIOMS)} pilot entries...")
        for entry_id, info in PILOT_IDIOMS.items():
            result = process_entry(entry_id, info, conn, args.force)
            time.sleep(2)  # Respect API rate limits
        print_results(conn)
    
    else:
        parser.print_help()
        print("\nQuick test:")
        print("  python3 pipeline/idiom_match.py --entry Б-41")
        print("  python3 pipeline/idiom_match.py --all_pilot")
        print("  python3 pipeline/idiom_match.py --results")
    
    conn.close()
