#!/usr/bin/env python3
"""
pipeline.py — Main pipeline for Russian-French Dictionary of Idioms

Steps:
  1. Parse SL PDF: find and extract a specific entry by ID
  2. Structure the entry into an intermediate format (dict)
  3a. Generate RF XML template from structured entry
  3b. Fill French content via Claude API
  3c. Locate French published translation of example
  3d. Extract and format French example text

Usage:
  python3 pipeline.py --entry Б-41 --sl_pdf /path/to/sl.pdf
  python3 pipeline.py --entry Б-36 --sl_pdf /path/to/sl.pdf --output xml/entries/B/

Escape doors (manual intervention flags):
  --no_api     : skip Claude API call, output template only (step 3a)
  --no_fr_search : skip French translation search (step 3c)
  --review     : pause for human review after each step
"""

import argparse
import json
import os
import re
import sys
import csv
from pathlib import Path
from typing import Optional

# ============================================================
# CONFIGURATION
# ============================================================

REPO_ROOT = Path(__file__).parent.parent
BIBLIOGRAPHY = REPO_ROOT / "bibliography" / "sl_bibliography.csv"
XML_OUTPUT   = REPO_ROOT / "xml" / "entries"
PDF_TEMP     = REPO_ROOT / "pipeline" / "_temp"

# Anthropic API — key from environment or .env file
try:
    from dotenv import load_dotenv
    # Load from repo root .env if present
    load_dotenv(REPO_ROOT / ".env")
except ImportError:
    pass  # dotenv optional
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
CLAUDE_MODEL = "claude-sonnet-4-5"

# ============================================================
# STEP 1: PDF PARSER
# ============================================================

def deinterleave_columns(raw_text: str) -> str:
    """
    Full-page PDF extraction of two-column layout produces interleaved lines:
    left-col-line-1, right-col-line-1, left-col-line-2, right-col-line-2...
    
    Strategy: find all entry boundaries (LETTER-NUM •) and extract
    the text between them, ignoring lines that belong to other entries
    (identified by containing a different entry ID pattern).
    """
    # Rejoin hyphenated line breaks first
    text = re.sub(r'([а-яёА-ЯЁa-zA-Z])-\n\s*([а-яёА-ЯЁa-zA-Z])', r'\1\2', raw_text)
    return text


def find_entry_in_pdf(pdf_path: str, entry_id: str) -> Optional[str]:
    """
    Find and extract a single SL entry from the PDF.
    
    Strategy:
    1. Search for the entry ID pattern (e.g. "Б-41 •")
    2. Extract text from that point until the next entry ID
    3. Return raw text of the entry
    
    Returns None if entry not found.
    """
    try:
        import pdfplumber
    except ImportError:
        print("ERROR: pdfplumber not installed. Run: pip install pdfplumber")
        sys.exit(1)

    # Build search pattern — entry IDs look like "Б-41 •" or "Б-41•"
    # The bullet • (U+2022) follows the entry number in SL
    letter = entry_id.split('-')[0]  # e.g. "Б"
    number = entry_id.split('-')[1]  # e.g. "41"
    
    # Pattern to match the start of our target entry
    # e.g. "Б-41 •" or "Б-41•" possibly with stress marks
    entry_pattern = re.compile(
        rf'{re.escape(letter)}-{re.escape(number)}\s*[•·]',
        re.UNICODE
    )
    
    # Pattern to match start of ANY entry (to know when current entry ends)
    any_entry_pattern = re.compile(
        r'[А-ЯЁ]-\d+\s*[•·]',
        re.UNICODE
    )

    full_text = ""
    entry_text = ""
    found = False
    
    print(f"Searching for entry {entry_id} in {pdf_path}...")
    
    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages):
            # Use full-page extraction (no column split)
            # Rationale: column split at any % causes entry IDs to be split
            # across the boundary. Full extraction keeps "Б-41 •" intact.
            # Cross-column text contamination is handled in the parser.
            text = page.extract_text() or ""
            if not text.strip():
                continue
            full_text += f"\n[PAGE {page_num + 1}]\n" + text
    
    # Rejoin hyphenated line breaks (common in two-column layout)
    # e.g. "say-\ning" → "saying", "ХО́-\nДИТ" → "ХО́ДИТ"
    full_text = re.sub(r'([а-яёА-ЯЁa-zA-Z])-\n\s*([а-яёА-ЯЁa-zA-Z])', r'\1\2', full_text)
    
    # Deinterleave hyphenated breaks
    full_text = deinterleave_columns(full_text)
    
    # Find the entry using string search (more reliable than line-by-line)
    # Pattern: "Б-41 •" — entry ID followed by bullet
    start_match = entry_pattern.search(full_text)
    if not start_match:
        print(f"WARNING: Entry {entry_id} not found in PDF.")
        return None
    
    # Find the start of the next entry to know where this one ends
    search_from = start_match.end()
    end_match = any_entry_pattern.search(full_text, search_from)
    
    if end_match:
        entry_text = full_text[start_match.start():end_match.start()]
    else:
        # Last entry in the dictionary — take remaining text (up to 3000 chars)
        entry_text = full_text[start_match.start():start_match.start() + 3000]
    
    # Clean up cross-column contamination:
    # Remove lines that are clearly from the adjacent column
    # (lines that start mid-sentence in English when we expect Russian, etc.)
    # Simple heuristic: remove very short lines (< 4 chars) that are noise
    lines = entry_text.split('\n')
    clean_lines = []
    for line in lines:
        stripped = line.strip()
        # Skip page number lines like "[ 10 ]"
        if re.match(r'^\[\s*\d+\s*\]$', stripped):
            continue
        # Skip isolated single letters (margin headers)
        if re.match(r'^[А-ЯЁA-Z]$', stripped):
            continue
        clean_lines.append(line)
    
    entry_text = '\n'.join(clean_lines).strip()
    
    print(f"Found entry {entry_id} ({len(entry_text)} chars)")
    return entry_text


def save_raw_entry(entry_id: str, raw_text: str) -> Path:
    """Save raw extracted entry text to temp file."""
    Path(PDF_TEMP).mkdir(parents=True, exist_ok=True)
    # Sanitize entry_id for filename
    safe_id = entry_id.replace('-', '_').replace('/', '_')
    out_path = Path(PDF_TEMP) / f"raw_{safe_id}.txt"
    out_path.write_text(raw_text, encoding='utf-8')
    print(f"Raw entry saved to {out_path}")
    return out_path


# ============================================================
# STEP 2: STRUCTURE PARSER
# ============================================================

def parse_entry_structure(raw_text: str, entry_id: str) -> dict:
    """
    Parse raw SL entry text into structured dict.
    
    Extracts:
    - entry_id
    - headwords (canonical + variants)
    - grammar (raw string)
    - senses (list of dicts with labels, definition, equivalents, examples)
    - etym_note
    
    This is a best-effort parse — complex entries get flagged for review.
    """
    entry = {
        "entry_id": entry_id,
        "headwords": [],
        "grammar_raw": "",
        "senses": [],
        "etym_note": "",
        "raw_text": raw_text,
        "parse_flags": []  # warnings for human review
    }
    
    lines = raw_text.strip().split('\n')
    full = ' '.join(l.strip() for l in lines if l.strip())
    
    # --- Extract headwords ---
    # Everything before the first '[' is head matter
    head_match = re.match(r'^(.+?)(?=\[)', full, re.DOTALL)
    if head_match:
        head_text = head_match.group(1).strip()
        # Remove entry number and bullet
        head_text = re.sub(rf'^{re.escape(entry_id)}\s*[•·]\s*', '', head_text)
        # Split on semicolon to get canonical + variants
        headwords = [h.strip() for h in re.split(r';\s*', head_text) if h.strip()]
        entry["headwords"] = headwords
    else:
        entry["parse_flags"].append("could_not_parse_headwords")

    # --- Extract grammar ---
    gram_match = re.search(r'\[([^\]]+)\]', full)
    if gram_match:
        entry["grammar_raw"] = gram_match.group(1).strip()
    
    # --- Extract senses ---
    # Look for numbered senses "1." "2." or single sense
    # For now extract everything after grammar as sense text
    after_gram = re.sub(r'^.*?\[[^\]]+\]\s*', '', full, count=1)
    
    # Check for multiple senses
    sense_split = re.split(r'\s+(?=\d+\.\s)', after_gram)
    
    for i, sense_text in enumerate(sense_split, 1):
        sense = {
            "sense_num": str(i),
            "usage_labels": [],
            "definition_en": "",
            "equivalents_en": [],
            "examples": [],
            "raw": sense_text.strip()
        }
        
        # Extract usage labels (italic words before definition)
        label_match = re.match(
            r'^((?:coll|iron|lit|obs|obsoles|old-fash|rare|disapprov|'
            r'humor|elev|offic|vulg|rhet|substand|highly coll|'
            r'folk poet|euph|derog|condes|impol|rude)\s*[,.]?\s*)+',
            sense_text, re.IGNORECASE
        )
        if label_match:
            label_str = label_match.group(0)
            sense["usage_labels"] = [
                l.strip().rstrip('.,') 
                for l in re.split(r'[,\s]+', label_str) 
                if l.strip()
            ]
            sense_text = sense_text[len(label_str):].strip()
        
        # Extract English equivalents — stop at first Cyrillic character
        # (Cyrillic marks the start of the Russian example text)
        # Equivalents follow ≈ and end before any Cyrillic or ♦ bullet
        equiv_match = re.search(r'[≈]\s*(.+?)(?=[А-ЯЁа-яё]|♦|◆|$)', sense_text)
        if equiv_match:
            equiv_text = equiv_match.group(1).strip().rstrip(';')
            sense["equivalents_en"] = [
                e.strip().strip(';')
                for e in re.split(r';\s*(?=[a-zA-Z])', equiv_text)
                if e.strip()
            ]
        
        # Extract examples — SL uses ♦ (U+2666) bullet before each example
        # Also handle ◆ (U+25C6) variant and cases where bullet may be missing
        # Fall back: extract Cyrillic text blocks after the equivalents
        examples_raw = re.findall(r'[♦◆]\s*(.+?)(?=[♦◆]|$)', sense_text, re.DOTALL)
        if not examples_raw:
            # No bullet found — extract everything from first Cyrillic char
            cyrillic_start = re.search(r'[А-ЯЁа-яё]', sense_text)
            if cyrillic_start:
                examples_raw = [sense_text[cyrillic_start.start():]]
        for ex_raw in examples_raw:
            # Try to split Russian text from English translation
            # English translation follows Russian in parentheses or after period
            # Extract citation: (Шолохов 2) or (Шолохов 2) followed by (2a)
            cite_match = re.search(
                r'\(([А-ЯЁа-яё][А-ЯЁа-яё\w\-]+)\s+(\d+)\)',
                ex_raw
            )
            en_cite_match = re.search(r'\((\d+)([a-z])\)', ex_raw)
            
            sl_code   = ""
            sl_suffix = ""
            ru_text   = ex_raw.strip()
            en_text   = ""
            
            if cite_match:
                sl_code = f"{cite_match.group(1)}-{cite_match.group(2)}"
                # Russian text ends at the citation
                ru_end = cite_match.end()
                ru_text = ex_raw[:ru_end].strip()
                en_text = ex_raw[ru_end:].strip()
            
            if en_cite_match:
                sl_suffix = en_cite_match.group(2)
            
            ex = {
                "ru_text": ru_text,
                "en_text": en_text,
                "sl_code": sl_code,
                "sl_suffix": sl_suffix
            }
            
            sense["examples"].append(ex)
        
        if not sense["examples"] and not equiv_match:
            entry["parse_flags"].append(f"sense_{i}_needs_review")
        
        entry["senses"].append(sense)
    
    # --- Extract etymological note ---
    etym_match = re.search(r'<\s*(.+?)$', full)
    if etym_match:
        entry["etym_note"] = etym_match.group(1).strip()
    
    return entry


def save_structured_entry(entry: dict) -> Path:
    """Save structured entry as JSON to temp file."""
    Path(PDF_TEMP).mkdir(parents=True, exist_ok=True)
    safe_id = entry["entry_id"].replace('-', '_').replace('/', '_')
    out_path = Path(PDF_TEMP) / f"structured_{safe_id}.json"
    out_path.write_text(
        json.dumps(entry, ensure_ascii=False, indent=2),
        encoding='utf-8'
    )
    print(f"Structured entry saved to {out_path}")
    return out_path


# ============================================================
# STEP 3a: XML TEMPLATE GENERATOR
# ============================================================

def load_bibliography() -> dict:
    """Load bibliography CSV into dict keyed by SL code."""
    bib = {}
    if not BIBLIOGRAPHY.exists():
        print(f"WARNING: Bibliography not found at {BIBLIOGRAPHY}")
        return bib
    with open(BIBLIOGRAPHY, encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            bib[row['SL_code']] = row
    return bib


# Abbreviation mapping EN → FR
ABBR_MAP = {
    # Phrase types
    "saying":   "prov.",
    "NP":       "SN",
    "VP":       "SV",
    "AdjP":     "SAdj",
    "AdvP":     "SAdv",
    "PrepP":    "SP",
    "Interj":   "Interj",
    # Usage labels
    "coll":         "fam.",
    "highly coll":  "très fam.",
    "obs":          "obs.",
    "obsoles":      "obsoles.",
    "old-fash":     "vieilli",
    "iron":         "iron.",
    "lit":          "litt.",
    "rhet":         "rhét.",
    "elev":         "sout.",
    "offic":        "offic.",
    "vulg":         "vulg.",
    "substand":     "substand.",
    "disapprov":    "désapprobat.",
    "humor":        "humor.",
    "derog":        "dérog.",
    "condes":       "condes.",
    "impol":        "impoli",
    "rude":         "grossier",
    "euph":         "euph.",
    "folk poet":    "folk poet.",
    # Form restrictions
    "Invar":            "Invar",
    "fixed WO":         "OdM fixe",
    "usu. this WO":     "usu. cet OdM",
    "these forms only": "ces formes seulement",
    "impers":           "impers.",
    "predic":           "préd.",
    "usu. neg":         "usu. nég.",
    "imper":            "impér.",
    # Grammar
    "subj":         "suj.",
    "obj":          "obj.",
    "human":        "humain",
    "collect":      "collect.",
    "anim":         "anim.",
    "inanim":       "inanim.",
    "s.o.":         "qn",
    "s.th.":        "qch",
}

def translate_grammar(grammar_raw: str) -> str:
    """Translate SL grammar string from English to French abbreviations."""
    result = grammar_raw
    # Sort by length descending to avoid partial replacements
    for en, fr in sorted(ABBR_MAP.items(), key=lambda x: -len(x[0])):
        result = re.sub(r'\b' + re.escape(en) + r'\b', fr, result)
    return result


def generate_xml_template(entry: dict, bib: dict) -> str:
    """
    Generate XML entry template from structured SL entry.
    Translates grammar and labels to French.
    Leaves French content fields as TODO placeholders.
    """
    eid = entry["entry_id"]
    
    # Head matter
    headwords = entry.get("headwords", [])
    canonical = headwords[0] if headwords else ""
    variants = headwords[1:] if len(headwords) > 1 else []
    
    # Grammar
    grammar_raw = entry.get("grammar_raw", "")
    grammar_fr  = translate_grammar(grammar_raw)
    
    lines = [f'<?xml version="1.0" encoding="UTF-8"?>']
    lines.append(f'<entry id="{eid}" sl_ref="{eid}" status="draft">')
    lines.append('')
    lines.append('  <head_matter>')
    lines.append('    <canonical>')
    lines.append(f'      <text>{canonical}</text>')
    lines.append('    </canonical>')
    for v in variants:
        lines.append('    <variant>')
        lines.append(f'      <text>{v}</text>')
        lines.append('    </variant>')
    lines.append('  </head_matter>')
    lines.append('')
    lines.append('  <grammar>')
    
    # Detect phrase type
    phrase_type = "saying"
    for pt in ["saying", "NP", "VP", "AdjP", "AdvP", "PrepP", "Interj"]:
        if pt in grammar_raw:
            phrase_type = pt
            break
    lines.append(f'    <phrase_type>{phrase_type}</phrase_type>')
    lines.append(f'    <raw_grammar>[{grammar_fr}]</raw_grammar>')
    lines.append('  </grammar>')
    lines.append('')
    
    for sense in entry.get("senses", []):
        sn = sense.get("sense_num", "1")
        lines.append(f'  <sense n="{sn}">')
        
        # Usage labels translated
        labels = sense.get("usage_labels", [])
        if labels:
            lines.append('    <usage_labels>')
            for lbl in labels:
                fr_lbl = ABBR_MAP.get(lbl.lower(), lbl)
                lines.append(f'      <label>{fr_lbl}</label>')
            lines.append('    </usage_labels>')
        
        # Definition — TODO for human/Claude to fill
        lines.append('    <!-- DÉFINITION: traduire/adapter en français -->')
        lines.append('    <definition lang="fr" type="full">TODO</definition>')
        lines.append('')
        
        # French equivalents — TODO
        lines.append('    <!-- ÉQUIVALENTS FRANÇAIS: à compléter -->')
        lines.append('    <french_equivalents>')
        lines.append('      <equiv register="prov" primary="true">')
        lines.append('        <text>TODO</text>')
        lines.append('      </equiv>')
        lines.append('      <equiv register="cour">')
        lines.append('        <text>TODO</text>')
        lines.append('      </equiv>')
        lines.append('      <equiv register="fam">')
        lines.append('        <text>TODO</text>')
        lines.append('      </equiv>')
        lines.append('    </french_equivalents>')
        lines.append('')
        
        # Examples
        lines.append('    <examples>')
        for ex in sense.get("examples", []):
            ru_text = ex.get("ru_text", "").strip()
            sl_code = ex.get("sl_code", "")
            sl_suffix = ex.get("sl_suffix", "")
            
            # Lookup bibliography
            bib_entry = bib.get(sl_code + sl_suffix, bib.get(sl_code, {}))
            author_ru = bib_entry.get("Author_RU", "")
            work_ru   = bib_entry.get("Work_RU", "")
            work_fr   = bib_entry.get("Work_FR", "TODO")
            translator_fr = bib_entry.get("Translator_FR", "TODO")
            
            lines.append('      <example type="literary">')
            lines.append(f'        <ru>{ru_text}</ru>')
            lines.append('        <!-- TRADUCTION FRANÇAISE: chercher dans corpus/bibliothèque -->')
            lines.append('        <fr status="pending">TODO</fr>')
            lines.append('        <bibref>')
            lines.append(f'          <sl_code>{sl_code}</sl_code>')
            lines.append(f'          <sl_suffix>{sl_suffix}</sl_suffix>')
            lines.append('          <ru_source>')
            lines.append(f'            <author>{author_ru}</author>')
            lines.append(f'            <work>{work_ru}</work>')
            lines.append('          </ru_source>')
            lines.append('          <fr_source>')
            lines.append(f'            <work_fr>{work_fr}</work_fr>')
            lines.append(f'            <translator>{translator_fr}</translator>')
            lines.append('          </fr_source>')
            lines.append('        </bibref>')
            lines.append('      </example>')
        lines.append('    </examples>')
        lines.append('')
        lines.append('  </sense>')
    
    if entry.get("etym_note"):
        lines.append(f'  <etym_note>{entry["etym_note"]}</etym_note>')
    
    lines.append('')
    lines.append('</entry>')
    
    return '\n'.join(lines)


# ============================================================
# STEP 3b: CLAUDE API — FILL FRENCH CONTENT
# ============================================================

def fill_french_content(xml_template: str, raw_entry: str) -> str:
    """
    Call Claude API to fill French equivalents and definition.
    Uses the SL raw entry as source material.
    Returns updated XML string with French content filled.
    """
    if not ANTHROPIC_API_KEY:
        print("WARNING: ANTHROPIC_API_KEY not set. Skipping Claude API step.")
        return xml_template
    
    try:
        import anthropic
    except ImportError:
        print("WARNING: anthropic package not installed. Skipping Claude API step.")
        return xml_template
    
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    
    prompt = f"""You are working on a Russian-French Dictionary of Idioms modeled on Lubensky's Russian-English dictionary.

Here is the original SL (Russian-English) entry:
<sl_entry>
{raw_entry}
</sl_entry>

Here is an XML template for the Russian-French entry with TODO placeholders:
<xml_template>
{xml_template}
</xml_template>

Please fill in the French content:
1. Replace the <definition> TODO with a French definition (adapt from the English, do not translate literally)
2. Replace the <french_equivalents> TODO items with appropriate French equivalents organized by register:
   - prov. (proverbial) — if applicable
   - sout. (soutenu/literary)
   - cour. (courant/standard)  
   - fam. (familier)
   - pop./arg. if applicable
3. Add or remove <equiv> elements as needed — registers depend on the idiom
4. Do NOT modify the <examples> section — leave French examples as TODO
5. Return ONLY the complete XML, no commentary

The output must be valid XML starting with <?xml version="1.0" encoding="UTF-8"?>"""

    message = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}]
    )
    
    response = message.content[0].text.strip()
    
    # Extract XML if wrapped in code blocks
    xml_match = re.search(r'```xml\s*(.*?)\s*```', response, re.DOTALL)
    if xml_match:
        response = xml_match.group(1)
    
    return response


# ============================================================
# STEP 3c/3d: FRENCH TRANSLATION LOCATOR
# ============================================================

def find_french_translation(entry: dict, bib: dict) -> dict:
    """
    For each example in the entry, attempt to find the published
    French translation.
    
    Strategy (multi-pass):
    1. Check if FR text file exists locally in library cache
    2. Search web for passage (Google Books, Gallica)
    3. Flag as pending if not found
    
    Returns dict mapping example index → french text or None
    """
    results = {}
    
    for sense in entry.get("senses", []):
        for i, ex in enumerate(sense.get("examples", [])):
            sl_code = ex.get("sl_code", "")
            sl_suffix = ex.get("sl_suffix", "")
            ru_text = ex.get("ru_text", "")
            
            if not sl_code:
                results[i] = None
                continue
            
            # Check bibliography for FR work
            bib_key = sl_code + sl_suffix if sl_suffix else sl_code
            bib_entry = bib.get(bib_key, bib.get(sl_code, {}))
            work_fr = bib_entry.get("Work_FR", "")
            
            if not work_fr:
                print(f"  Example {i}: No French translation known for {sl_code}")
                results[i] = {"status": "no_fr_translation", "text": None}
                continue
            
            # Extract anchor words from Russian text for searching
            # Use proper nouns and rare content words
            anchors = extract_anchor_words(ru_text)
            
            print(f"  Example {i}: Source={sl_code}, FR work={work_fr}")
            print(f"  Anchors: {anchors}")
            
            # For now: flag as pending with metadata
            # Full web search implemented in next phase
            results[i] = {
                "status": "pending",
                "sl_code": sl_code,
                "work_fr": work_fr,
                "anchors": anchors,
                "text": None
            }
    
    return results


def extract_anchor_words(ru_text: str) -> list:
    """
    Extract distinctive words from Russian text for use as
    search anchors in French translation.
    
    Returns capitalized words (proper nouns) + long content words.
    """
    words = ru_text.split()
    anchors = []
    
    for w in words:
        # Clean punctuation
        clean = re.sub(r'[«».,!?…:;()\[\]"]', '', w)
        clean = clean.strip()
        if not clean:
            continue
        
        # Proper nouns: capitalized mid-sentence
        if len(clean) > 2 and clean[0].isupper() and clean not in ('Не', 'НЕ', 'На', 'За', 'По', 'При'):
            anchors.append(clean)
        # Long content words (rare, specific)
        elif len(clean) >= 8:
            anchors.append(clean)
    
    return anchors[:6]  # Return top 6 anchors


# ============================================================
# MAIN
# ============================================================

def run_pipeline(entry_id: str, 
                 sl_pdf: Optional[str] = None,
                 output_dir: Optional[str] = None,
                 no_api: bool = False,
                 no_fr_search: bool = False,
                 review: bool = False):
    """
    Run the full pipeline for a single entry.
    """
    print(f"\n{'='*60}")
    print(f"Pipeline: {entry_id}")
    print(f"{'='*60}\n")
    
    bib = load_bibliography()
    print(f"Bibliography loaded: {len(bib)} entries\n")
    
    # STEP 1: Extract from PDF
    if sl_pdf and os.path.exists(sl_pdf):
        print("STEP 1: Extracting from SL PDF...")
        raw_text = find_entry_in_pdf(sl_pdf, entry_id)
        if raw_text:
            raw_path = save_raw_entry(entry_id, raw_text)
        else:
            print(f"Entry {entry_id} not found in PDF. Exiting.")
            return
    else:
        # Try loading from temp file
        safe_id = entry_id.replace('-', '_').replace('/', '_')
        raw_path = Path(PDF_TEMP) / f"raw_{safe_id}.txt"
        if raw_path.exists():
            print(f"STEP 1: Loading raw entry from {raw_path}")
            raw_text = raw_path.read_text(encoding='utf-8')
        else:
            print("STEP 1: No PDF path provided and no cached raw entry found.")
            print("        Provide --sl_pdf to extract from the PDF.")
            return
    
    if review:
        print("\n--- REVIEW STEP 1: Raw entry text ---")
        print(raw_text[:500] + "..." if len(raw_text) > 500 else raw_text)
        input("Press Enter to continue...")
    
    # STEP 2: Parse structure
    print("\nSTEP 2: Parsing entry structure...")
    entry = parse_entry_structure(raw_text, entry_id)
    struct_path = save_structured_entry(entry)
    
    if entry["parse_flags"]:
        print(f"  ⚠ Parse flags: {entry['parse_flags']}")
    
    print(f"  Headwords: {entry['headwords']}")
    print(f"  Grammar: {entry['grammar_raw']}")
    print(f"  Senses: {len(entry['senses'])}")
    
    if review:
        print("\n--- REVIEW STEP 2: Structured entry ---")
        print(json.dumps(entry, ensure_ascii=False, indent=2)[:800])
        input("Press Enter to continue...")
    
    # STEP 3a: Generate XML template
    print("\nSTEP 3a: Generating XML template...")
    xml_template = generate_xml_template(entry, bib)
    
    # STEP 3b: Fill French content via Claude API
    if not no_api:
        print("\nSTEP 3b: Filling French content via Claude API...")
        xml_filled = fill_french_content(xml_template, raw_text)
    else:
        print("\nSTEP 3b: Skipped (--no_api)")
        xml_filled = xml_template
    
    # STEP 3c/3d: Locate French translation
    if not no_fr_search:
        print("\nSTEP 3c: Locating French translations for examples...")
        fr_results = find_french_translation(entry, bib)
        for i, result in fr_results.items():
            print(f"  Example {i}: {result}")
    
    if review:
        print("\n--- REVIEW STEP 3: Generated XML ---")
        print(xml_filled[:800])
        input("Press Enter to continue...")
    
    # Save output XML
    if output_dir:
        out_dir = Path(output_dir)
    else:
        # Default: xml/entries/<letter>/
        letter = entry_id.split('-')[0]
        out_dir = XML_OUTPUT / letter
    
    out_dir.mkdir(parents=True, exist_ok=True)
    safe_id = entry_id.replace('-', '_').replace('/', '_')
    
    # Use entry letter for filename prefix
    letter_lower = entry_id.split('-')[0].lower()
    num = entry_id.split('-')[1]
    out_file = out_dir / f"entry_{letter_lower.upper()}{num}.xml"
    
    out_file.write_text(xml_filled, encoding='utf-8')
    print(f"\n✓ Entry saved to {out_file}")
    
    return str(out_file)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="SL → RF Dictionary Pipeline"
    )
    parser.add_argument("--entry",      required=True, help="Entry ID e.g. Б-41")
    parser.add_argument("--sl_pdf",     default=None,  help="Path to SL PDF")
    parser.add_argument("--output",     default=None,  help="Output directory for XML")
    parser.add_argument("--no_api",     action="store_true", help="Skip Claude API step")
    parser.add_argument("--no_fr_search", action="store_true", help="Skip FR translation search")
    parser.add_argument("--review",     action="store_true", help="Pause for review at each step")
    
    args = parser.parse_args()
    
    run_pipeline(
        entry_id     = args.entry,
        sl_pdf       = args.sl_pdf,
        output_dir   = args.output,
        no_api       = args.no_api,
        no_fr_search = args.no_fr_search,
        review       = args.review
    )
