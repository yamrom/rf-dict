#!/usr/bin/env python3
"""
generate_entry.py — Generate a complete RF dictionary entry end-to-end

Pipeline for one entry:
  1. Load index → get all idiom variants for entry
  2. Analyze idiom grammatically (analyze_idiom.py)
  3. Match French equivalent (idiom_match.py)
  4. Get best RNC example (rnc_db.py)
  5. Build XML entry
  6. Render to PDF (xml_to_latex.py)

Usage:
  python3 pipeline/generate_entry.py --entry Б-41
  python3 pipeline/generate_entry.py --entry Б-41 --no-pdf
  python3 pipeline/generate_entry.py --range Б-36 Б-44
"""

import os, sys, json, argparse, time
from pathlib import Path

PIPELINE_DIR = Path(__file__).parent
REPO_ROOT    = PIPELINE_DIR.parent
sys.path.insert(0, str(PIPELINE_DIR))

from analyze_idiom import analyze_idiom, load_index
from idiom_match   import get_db, seed_fr_idiom_db, match_against_fr_db, process_entry as match_entry, PILOT_IDIOMS
from rnc_db        import get_db as get_rnc_db, get_best_examples
from guide_spec    import build_fr_grammar_bracket

ANTHROPIC_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
XML_DIR       = REPO_ROOT / "xml" / "entries"
PDF_DIR       = REPO_ROOT / "pdf"


# ============================================================
# STEP 1: LOAD INDEX
# ============================================================

def get_entry_data(entry_id: str, entry_to_idioms: dict) -> dict:
    """Get canonical idiom from index, but get proper headword variants from SL docx."""
    idioms = entry_to_idioms.get(entry_id, [])
    if not idioms:
        raise ValueError(f"Entry {entry_id} not found in index")

    canonical = idioms[0]

    # Get proper variants from SL docx parser (not from index)
    # Index has too many forms including fragments
    variants = []
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "sl_docx_parser", PIPELINE_DIR / "sl_docx_parser.py"
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        doc   = mod.load_doc()
        index = mod.build_index(doc)
        paras = mod.get_entry_paragraphs(doc, entry_id, index)
        if paras:
            parsed   = mod.parse_entry(entry_id, paras)
            headwords = parsed.get("headwords", [])
            # First headword is canonical, rest are proper variants
            if headwords:
                canonical = headwords[0]
                variants  = headwords[1:] if len(headwords) > 1 else []
    except Exception as e:
        print(f"      (SL docx unavailable, using index canonical: {e})")

    return {
        "entry_id":  entry_id,
        "canonical": canonical,
        "variants":  variants,
        "all_forms": idioms,
    }


# ============================================================
# STEP 2+3: ANALYZE + MATCH (combined Claude calls)
# ============================================================

def analyze_and_match(entry_id: str, canonical: str, conn) -> dict:
    """
    Run grammatical analysis and French matching for one entry.
    Returns combined result dict.
    """
    print(f"  [2] Grammatical analysis...")
    analysis = analyze_idiom(canonical)
    time.sleep(1)

    print(f"  [3] French matching...")
    # Use process_entry from idiom_match which handles both paraphrase and matching
    idiom_info = PILOT_IDIOMS.get(entry_id, {
        "ru":       canonical,
        "grammar":  analysis.get("grammar_bracket", ""),
        "en_gloss": analysis.get("ru_paraphrase", ""),
    })

    # If not in PILOT_IDIOMS, build info from analysis
    if entry_id not in PILOT_IDIOMS:
        idiom_info = {
            "ru":       canonical,
            "grammar":  analysis.get("grammar_bracket", ""),
            "en_gloss": analysis.get("ru_paraphrase", ""),
        }

    match_result = match_entry(entry_id, idiom_info, conn, force=True)

    return {
        "analysis":     analysis,
        "match":        match_result,
    }


# ============================================================
# STEP 4: GET BEST RNC EXAMPLE
# ============================================================

def get_example(entry_id: str) -> dict:
    """Get best RNC example for the entry."""
    conn = get_rnc_db()
    examples = get_best_examples(entry_id, conn, top_n=1)
    conn.close()

    if not examples:
        return {
            "ru_sentence": "",
            "ru_author":   "",
            "ru_work":     "",
            "ru_year":     "",
            "en_sentence": "",
            "status":      "no_example",
        }

    ex = examples[0]
    return {
        "ru_sentence": ex.get("ru_sentence", ""),
        "ru_author":   ex.get("ru_author", ""),
        "ru_work":     ex.get("ru_work", ""),
        "ru_year":     str(ex.get("ru_year", "")),
        "en_sentence": ex.get("en_sentence", ""),
        "status":      "found",
    }


# ============================================================
# STEP 4b: GENERATE FRENCH EXAMPLE
# ============================================================

def generate_fr_example(entry_id: str, canonical: str,
                         fr_definition: str, match_type: str,
                         ru_example: str) -> dict:
    """
    Generate a French example sentence using the French equivalent.
    This is a Level 4 (constructed) example, flagged as such.

    Strategy:
    - If Type A (idiomatic match): generate a sentence using the French idiom
    - If Type B (paraphrase): generate a sentence illustrating the meaning
    - If Russian example available: generate a French sentence parallel to it
    """
    import anthropic
    client = anthropic.Anthropic(api_key=ANTHROPIC_KEY)

    if ru_example:
        prompt = f"""You are working on a Russian-French dictionary of idioms.

Russian idiom: «{canonical}»
French equivalent: «{fr_definition}»
Russian example sentence: {ru_example}

Write a natural French sentence that:
1. Uses the French equivalent «{fr_definition}» naturally
2. Reflects a similar situation or context to the Russian example
3. Reads as authentic literary French prose (not a translation)
4. Is 1-2 sentences long

Return ONLY the French sentence, nothing else."""
    else:
        prompt = f"""You are working on a Russian-French dictionary of idioms.

Russian idiom: «{canonical}»
French equivalent: «{fr_definition}»

Write a natural French example sentence that:
1. Uses the French equivalent «{fr_definition}» naturally in context
2. Illustrates the typical usage of this expression
3. Reads as authentic literary French prose
4. Is 1-2 sentences long

Return ONLY the French sentence, nothing else."""

    response = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=300,
        messages=[{"role": "user", "content": prompt}]
    )

    fr_sentence = response.content[0].text.strip()

    return {
        "fr_sentence": fr_sentence,
        "status":      "constructed",
        "source":      "Claude (constructed example)",
    }


# ============================================================
# STEP 5: BUILD XML
# ============================================================

def build_xml(entry_id: str, entry_data: dict,
              analysis: dict, match: dict,
              example: dict, fr_example: dict) -> str:
    """Build XML entry from all components."""

    canonical   = entry_data["canonical"]
    variants    = entry_data["variants"]
    grammar     = analysis.get("grammar_bracket", "")
    fr_grammar  = build_fr_grammar_bracket(analysis)
    phrase_type = analysis.get("phrase_type", "")
    ru_paraph   = analysis.get("ru_paraphrase", "")
    register    = analysis.get("register", {})

    # Stylistic labels
    style_labels = [v for v in register.values() if v]
    style_str    = ", ".join(style_labels) if style_labels else ""

    # French content
    match_type  = match.get("match_type", "B") if match else "B"
    fr_idiom    = match.get("fr_idiom", "") if match else ""
    fr_paraph   = match.get("fr_paraphrase", "") if match else ""
    ru_paraph_m = match.get("ru_paraphrase", ru_paraph) if match else ru_paraph
    fr_trans    = match.get("fr_translation", "") if match else ""

    # French definition
    if match_type == "A" and fr_idiom:
        fr_definition = fr_idiom
        fr_def_type   = "equivalent"
    else:
        fr_definition = fr_trans or ru_paraph_m
        fr_def_type   = "paraphrase"

    # Russian example
    ru_sent   = example.get("ru_sentence", "")
    ru_author = example.get("ru_author", "")
    ru_work   = example.get("ru_work", "")
    ru_year   = example.get("ru_year", "")
    en_sent   = example.get("en_sentence", "")

    # French example
    fr_sent        = fr_example.get("fr_sentence", "") if fr_example else ""
    fr_ex_status   = fr_example.get("status", "") if fr_example else ""
    fr_ex_source   = fr_example.get("source", "") if fr_example else ""

    # Build variant elements
    variant_elements = ""
    for v in variants:
        variant_elements += f'\n    <variant>{_escape(v)}</variant>'

    # Citation
    citation = ""
    if ru_author and ru_work:
        citation = f"{ru_author}, {ru_work}"
        if ru_year:
            citation += f" ({ru_year})"

    xml = f'''<?xml version="1.0" encoding="UTF-8"?>
<entry id="{entry_id}" status="draft">

  <headword>
    <canonical>{_escape(canonical)}</canonical>{variant_elements}
  </headword>

  <grammar>
    <bracket>{_escape(fr_grammar)}</bracket>
    <paraphrase lang="ru">{_escape(ru_paraph_m)}</paraphrase>
    <paraphrase lang="fr">{_escape(fr_trans)}</paraphrase>
  </grammar>

  <stylistic_labels>{style_str}</stylistic_labels>

  <french>
    <definition type="{fr_def_type}">{_escape(fr_definition)}</definition>
    <match_type>{match_type}</match_type>
    <fr_paraphrase>{_escape(fr_paraph)}</fr_paraphrase>
  </french>

  <examples>
    <example lang="ru">
      <sentence>{_escape(ru_sent)}</sentence>
      <citation>{_escape(citation)}</citation>
    </example>
    <example lang="fr" status="{fr_ex_status}">
      <sentence>{_escape(fr_sent)}</sentence>
    </example>
  </examples>

  <!-- verification only — not for rendering -->
  <internal>
    <en_example>{_escape(en_sent)}</en_example>
    <phrase_type_en>{phrase_type}</phrase_type_en>
    <ru_bracket>{_escape(grammar)}</ru_bracket>
  </internal>

</entry>
'''
    return xml


def _escape(text: str) -> str:
    """Escape XML special characters."""
    if not text:
        return ""
    return (text
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;"))


# ============================================================
# STEP 6: RENDER PDF (optional)
# ============================================================

def render_docx(xml_path: Path, entry_id: str) -> Path:
    """Render XML entry to Word document via xml_to_docx.py."""
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "xml_to_docx", PIPELINE_DIR / "xml_to_docx.py"
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        docx_path = PDF_DIR / f"entry_{entry_id.replace('-','_')}.docx"
        mod.xml_to_docx(str(xml_path), str(docx_path))
        return docx_path
    except Exception as e:
        print(f"  Word render failed: {e}")
        return None


# ============================================================
# MAIN PIPELINE
# ============================================================

def generate_entry(entry_id: str, conn,
                   entry_to_idioms: dict,
                   render: bool = True,
                   save_json: bool = True) -> dict:
    """Full pipeline for one entry."""

    print(f"\n{'='*55}")
    print(f"Generating entry {entry_id}")
    print('='*55)

    # Step 1: Index
    print(f"  [1] Loading index data...")
    entry_data = get_entry_data(entry_id, entry_to_idioms)
    print(f"      Canonical: {entry_data['canonical']}")
    if entry_data['variants']:
        print(f"      Variants:  {entry_data['variants']}")

    # Steps 2+3: Analyze + Match
    combined = analyze_and_match(entry_id, entry_data["canonical"], conn)
    analysis = combined["analysis"]
    match    = combined["match"]

    print(f"      Type:      {analysis.get('phrase_type','')}")
    print(f"      Grammar:   {analysis.get('grammar_bracket','')}")
    if match:
        mt = match.get('match_type','?')
        fi = match.get('fr_idiom','')
        print(f"      FR match:  Type {mt} — {fi}")

    # Step 4: Example
    print(f"  [4] Getting RNC example...")
    example = get_example(entry_id)
    if example["status"] == "found":
        print(f"      {example['ru_author']} — {example['ru_work']}")
    else:
        print(f"      No RNC example found")

    # Step 4b: French example
    print(f"  [4b] Generating French example...")
    fr_definition = match.get("fr_idiom", "") if match else ""
    if not fr_definition:
        fr_definition = match.get("fr_translation", "") if match else ""
    fr_example = generate_fr_example(
        entry_id,
        entry_data["canonical"],
        fr_definition,
        match.get("match_type", "B") if match else "B",
        example.get("ru_sentence", "")
    )
    print(f"      {fr_example['fr_sentence'][:70]}")
    time.sleep(1)

    # Step 5: Build XML
    print(f"  [5] Building XML...")
    xml_content = build_xml(entry_id, entry_data, analysis,
                            match, example, fr_example)

    # Save XML
    letter = entry_id.split('-')[0]
    xml_subdir = XML_DIR / letter
    xml_subdir.mkdir(parents=True, exist_ok=True)
    xml_path = xml_subdir / f"entry_{entry_id.replace('-','_')}.xml"
    xml_path.write_text(xml_content, encoding='utf-8')
    print(f"      Saved: {xml_path}")

    # Save JSON analysis
    if save_json:
        json_dir = PIPELINE_DIR / "analyses"
        json_dir.mkdir(exist_ok=True)
        json_path = json_dir / f"{entry_id}.json"
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump({
                "entry_id":  entry_id,
                "entry_data": entry_data,
                "analysis":  analysis,
                "match":     match,
                "example":   example,
            }, f, ensure_ascii=False, indent=2)

    # Step 6: Render Word document
    docx_path = None
    if render:
        print(f"  [6] Rendering Word document...")
        docx_path = render_docx(xml_path, entry_id)
        if docx_path:
            print(f"      Saved: {docx_path}")

    return {
        "entry_id": entry_id,
        "xml_path": str(xml_path),
        "docx_path": str(docx_path) if docx_path else None,
        "analysis": analysis,
        "match":    match,
        "example":  example,
    }


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description='Generate RF dictionary entry')
    ap.add_argument('--entry',   help='Entry ID e.g. Б-41')
    ap.add_argument('--range',   nargs=2, metavar=('FROM', 'TO'))
    ap.add_argument('--no-pdf',  action='store_true', help='Skip PDF rendering')
    args = ap.parse_args()

    if not ANTHROPIC_KEY:
        print("ERROR: ANTHROPIC_API_KEY not set")
        sys.exit(1)

    entry_to_idioms, idiom_to_entry = load_index()
    conn = get_db()
    seed_fr_idiom_db(conn)

    if args.entry:
        result = generate_entry(
            args.entry, conn, entry_to_idioms,
            render=not args.no_pdf
        )
        print(f"\nDone: {result['entry_id']}")
        print(f"  XML:  {result['xml_path']}")
        if result.get('docx_path'):
            print(f"  Word: {result['docx_path']}")

    elif args.range:
        from_id, to_id = args.range
        RU_ALPHA = 'АБВГДЕЁЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯ'

        def sort_key(eid):
            p = eid.split('-')
            if len(p) != 2: return (999, 0)
            return (RU_ALPHA.index(p[0]) if p[0] in RU_ALPHA else 99,
                    int(p[1]) if p[1].isdigit() else 0)

        sorted_entries = sorted(entry_to_idioms.keys(), key=sort_key)
        in_range = False
        for entry_id in sorted_entries:
            if entry_id == from_id: in_range = True
            if in_range:
                generate_entry(entry_id, conn, entry_to_idioms,
                               render=not args.no_pdf)
                time.sleep(2)
            if entry_id == to_id: break

    else:
        ap.print_help()
        print("\nExample:")
        print("  python3 pipeline/generate_entry.py --entry Б-41")
        print("  python3 pipeline/generate_entry.py --range Б-36 Б-44 --no-pdf")

    conn.close()
