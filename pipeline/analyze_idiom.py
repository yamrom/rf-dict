#!/usr/bin/env python3
"""
analyze_idiom.py — Generate grammatical analysis of a Russian idiom
using the Guide spec as the rule specification for Claude.

Usage:
  python3 analyze_idiom.py --idiom "беда не приходит одна"
  python3 analyze_idiom.py --entry Б-41
  python3 analyze_idiom.py --range Б-36 Б-44
"""

import os
import sys
import json
import argparse
import anthropic
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from guide_spec import (
    DEFECTIVE_PARADIGM,
    NEGATION_RULES,
    IDIOM_TYPES,
    GRAMMAR_RULES,
    STYLISTIC_LABELS,
    IDIOM_ANALYSIS_CHECKLIST,
    TYPE_DETECTION,
)

CLAUDE_MODEL    = "claude-sonnet-4-5"
PIPELINE_DIR    = Path(__file__).parent
INDEX_JSON      = PIPELINE_DIR / "sl_index.json"
ANTHROPIC_KEY   = os.environ.get("ANTHROPIC_API_KEY", "")


# ============================================================
# PROMPT BUILDER
# ============================================================

def build_system_prompt() -> str:
    """
    Build the system prompt containing the Guide spec rules.
    This is passed once and stays in context for all idiom analyses.
    """
    return """You are an expert Russian linguist and lexicographer working on a 
Russian-French dictionary of idioms. Your task is to perform a precise 
grammatical and stylistic analysis of Russian idiomatic expressions, 
following the rules of the Guide to the Dictionary specified below.

Your analysis must be rigorous, based on linguistic knowledge of the idiom, 
NOT on any existing dictionary entry. You are generating original analysis.

Return ONLY valid JSON matching the schema provided. No prose, no explanation 
outside the JSON structure.

═══════════════════════════════════════════════════════════
PHRASE TYPES
═══════════════════════════════════════════════════════════
{phrase_types}

TYPE DETECTION PRIORITY:
{type_detection}

═══════════════════════════════════════════════════════════
GRAMMATICAL BRACKET RULES
═══════════════════════════════════════════════════════════
Bracket contents appear in this order:
  [phrase_type; form_restriction; syntactic_function; copula_spec; 
   subj_spec; obj_spec; foll_by; WO_spec]

Examples:
  В БЕГАХ → [PrepP; Invar; subj-compl with бытьø (subj: human)]
  СПАСАТЬСЯ БЕГСТВОМ → [VP; subj: human, collect, or animal; usu. this WO]
  БЕДА НЕ ПРИХОДИТ ОДНА → [saying]
  НЕ БЕДА → [NP; Invar; subj-compl with бытьø (subj: usu. это or a clause), pres only, or indep. sent]

Subject types: human / collect / animal / abstr / concr / infin / clause
Copula notation: бытьø (zero-present only) / copula (any copula verb)

═══════════════════════════════════════════════════════════
DEFECTIVE PARADIGM — check all 5 dimensions
═══════════════════════════════════════════════════════════
1. CASE: restricted to specific case(s)?
   → accus only / nom only / gen only / dat only / instrum only / prep only
2. NUMBER: sing only / pl only / both
3. PERSON: 1st pers only / not 1st pers / 2nd pers only / 3rd pers only / any
4. TENSE/ASPECT: impfv only / pfv only / pres only / past only / fut only / any
5. FINITE: finite only (no infinitive/participle/verbal adverb) / all forms

═══════════════════════════════════════════════════════════
NEGATION BEHAVIOR
═══════════════════════════════════════════════════════════
Patterns:
  no_negation        — cannot be used with НЕ at all
  he_non_negative    — used only with НЕ but НЕ loses negating meaning
  negation_antonym   — НЕ produces antonym (separate entry)
  negation_changes_senses — НЕ form has different number of senses (separate entry)
  negation_optional  — same meaning with or without НЕ
  normal             — НЕ behaves predictably

═══════════════════════════════════════════════════════════
STYLISTIC LABELS
═══════════════════════════════════════════════════════════
Temporal:   obs / obsoles / old-fash / rare / recent
Register:   [none=neutral] / coll / highly coll / substand / slang / euph /
            lit / rhet / elev / offic / special / folk poet / vulg / taboo
Expressive: approv / humor / iron / disapprov / derog / condes / impol / rude

═══════════════════════════════════════════════════════════
WORD ORDER
═══════════════════════════════════════════════════════════
  fixed WO       — word order cannot change
  usu. this WO   — rarely changed
  free           — free word order (default, not noted)

═══════════════════════════════════════════════════════════
OUTPUT SCHEMA
═══════════════════════════════════════════════════════════
Return this exact JSON structure:
{{
  "idiom": "the idiom as given",
  "canonical_form": "canonical dictionary form with stress marks if known",
  "phrase_type": "NP|VP|AdjP|AdvP|PrepP|saying|formula|Interj|simile|intensifier|quantif|prep_idiom|conj_idiom|particle_idiom",
  "subtype": "как+NP|sent adv|quantit|etc. or null",
  "grammar_bracket": "full bracket string as it would appear in dictionary e.g. [VP; subj: human]",
  "form_restriction": "Invar|these forms only|null",
  "syntactic_functions": ["subj", "obj", "predic", "adv", "modif", "subj-compl", "indep. sent"],
  "copula": "бытьø|copula|null",
  "subject_type": "human|collect|animal|abstr|concr|infin|clause|any|null",
  "object_type": "human|collect|animal|abstr|concr|any|null",
  "foll_by": "infin|clause|null",
  "word_order": "fixed WO|usu. this WO|free",
  "defective_paradigm": {{
    "case": "accus only|nom only|gen only|any",
    "number": "sing only|pl only|both",
    "person": "1st pers only|not 1st pers|any",
    "tense_aspect": "impfv only|pfv only|pres only|past only|fut only|any",
    "finite": "finite only|all forms"
  }},
  "negation": "no_negation|he_non_negative|negation_antonym|negation_changes_senses|negation_optional|normal",
  "aspect": "impfv only|pfv only|both|null",
  "aspect_note": "brief note if impfv and pfv have different meanings, else null",
  "register": {{
    "temporal": "obs|obsoles|old-fash|rare|recent|null",
    "stylistic": "coll|highly coll|substand|slang|euph|lit|rhet|elev|offic|special|folk poet|vulg|taboo|null",
    "expressive": "approv|humor|iron|disapprov|derog|condes|impol|rude|null"
  }},
  "has_literal_meaning": true|false,
  "literal_meaning_note": "brief description if has_literal_meaning is true, else null",
  "unique_lexical_component": true|false,
  "archaic_component": true|false,
  "archaic_note": "description of archaic form if present, else null",
  "etymology": "biblical|literary|historical|calque|folk|null",
  "etymology_note": "brief etymology if relevant, else null",
  "ru_paraphrase": "plain Russian paraphrase of the idiom meaning (no idioms used)",
  "confidence": "high|medium|low",
  "confidence_note": "brief note if confidence is not high"
}}
""".format(
    phrase_types=_format_phrase_types(),
    type_detection=_format_type_detection(),
)


def _format_phrase_types() -> str:
    lines = []
    for key, val in IDIOM_TYPES.items():
        lines.append(f"  {key:15s} — {val['label']}: {val['description'][:80]}")
        if 'example' in val:
            lines.append(f"                    e.g. {val['example']}")
    return '\n'.join(lines)


def _format_type_detection() -> str:
    lines = ["Priority order (check in this sequence):"]
    for i, t in enumerate(TYPE_DETECTION['priority_order'], 1):
        signals = TYPE_DETECTION['signals'].get(t, [])
        sig_str = '; '.join(signals[:2]) if signals else ''
        lines.append(f"  {i:2d}. {t:15s} {sig_str}")
    return '\n'.join(lines)


def build_user_prompt(idiom: str, context: str = None) -> str:
    """Build the user prompt for a specific idiom."""
    prompt = f"""Analyze this Russian idiom: «{idiom}»
"""
    if context:
        prompt += f"\nAdditional context: {context}\n"

    prompt += """
Apply the Guide rules from the system prompt to generate a complete 
grammatical and stylistic analysis. 

Key steps:
1. Determine phrase type using the priority detection order
2. Construct the grammar bracket string
3. Check all 5 defective paradigm dimensions
4. Determine negation behavior
5. Assign stylistic labels (temporal, register, expressive)
6. Write a plain Russian paraphrase (no idioms, 1-2 sentences)

Return ONLY the JSON object. No other text.
"""
    return prompt


# ============================================================
# CLAUDE API CALL
# ============================================================

def analyze_idiom(idiom: str, context: str = None) -> dict:
    """Call Claude to analyze a Russian idiom."""
    if not ANTHROPIC_KEY:
        raise ValueError("ANTHROPIC_API_KEY not set")

    client = anthropic.Anthropic(api_key=ANTHROPIC_KEY)

    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=1500,
        system=build_system_prompt(),
        messages=[{
            "role": "user",
            "content": build_user_prompt(idiom, context)
        }]
    )

    text = response.content[0].text.strip()

    # Strip markdown if present
    import re
    text = re.sub(r'^```(?:json)?\s*', '', text, flags=re.MULTILINE)
    text = re.sub(r'\s*```$', '', text, flags=re.MULTILINE)

    try:
        return json.loads(text.strip())
    except json.JSONDecodeError as e:
        print(f"JSON parse error: {e}")
        print(f"Response: {text[:300]}")
        return {"error": str(e), "raw": text}


def load_index():
    with open(INDEX_JSON, encoding='utf-8') as f:
        data = json.load(f)
    return data['entry_to_idioms'], data['idiom_to_entry']


def print_analysis(result: dict):
    """Pretty-print the analysis result."""
    print(f"\n{'='*60}")
    print(f"Idiom:         {result.get('idiom', '')}")
    print(f"Canonical:     {result.get('canonical_form', '')}")
    print(f"Phrase type:   {result.get('phrase_type', '')}")
    if result.get('subtype'):
        print(f"Subtype:       {result['subtype']}")
    print(f"Grammar:       {result.get('grammar_bracket', '')}")
    print(f"Syn. functions:{result.get('syntactic_functions', [])}")
    print(f"Word order:    {result.get('word_order', '')}")

    dp = result.get('defective_paradigm', {})
    non_default = {k: v for k, v in dp.items()
                   if v not in ('any', 'both', 'all forms', 'free', None)}
    if non_default:
        print(f"Defective paradigm: {non_default}")

    print(f"Negation:      {result.get('negation', '')}")

    reg = result.get('register', {})
    labels = [v for v in reg.values() if v]
    if labels:
        print(f"Register:      {', '.join(labels)}")

    if result.get('has_literal_meaning'):
        print(f"Literal:       {result.get('literal_meaning_note', '')}")
    if result.get('archaic_component'):
        print(f"Archaic:       {result.get('archaic_note', '')}")
    if result.get('etymology'):
        print(f"Etymology:     {result.get('etymology')} — {result.get('etymology_note', '')}")

    print(f"\nRU paraphrase: {result.get('ru_paraphrase', '')}")
    print(f"Confidence:    {result.get('confidence', '')} {result.get('confidence_note') or ''}")


# ============================================================
# MAIN
# ============================================================

if __name__ == '__main__':
    ap = argparse.ArgumentParser(description='Analyze Russian idiom grammatically')
    ap.add_argument('--idiom',  help='Idiom string to analyze')
    ap.add_argument('--entry',  help='Entry ID — analyze canonical idiom for this entry')
    ap.add_argument('--range',  nargs=2, metavar=('FROM', 'TO'),
                    help='Analyze all entries in range')
    ap.add_argument('--save',   action='store_true',
                    help='Save results to pipeline/analyses/')
    args = ap.parse_args()

    if not ANTHROPIC_KEY:
        print("ERROR: ANTHROPIC_API_KEY not set")
        sys.exit(1)

    entry_to_idioms, idiom_to_entry = load_index()

    if args.idiom:
        result = analyze_idiom(args.idiom)
        print_analysis(result)
        if args.save:
            out = PIPELINE_DIR / 'analyses' / f"{args.idiom[:30].replace(' ','_')}.json"
            out.parent.mkdir(exist_ok=True)
            with open(out, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            print(f"\nSaved to {out}")

    elif args.entry:
        idioms = entry_to_idioms.get(args.entry, [])
        if not idioms:
            print(f"Entry {args.entry} not found in index")
            sys.exit(1)
        # Analyze the canonical (first) idiom for this entry
        canonical = idioms[0]
        print(f"Analyzing canonical idiom for {args.entry}: «{canonical}»")
        result = analyze_idiom(canonical)
        result['entry_id']  = args.entry
        result['all_forms'] = idioms
        print_analysis(result)
        if args.save:
            out = PIPELINE_DIR / 'analyses' / f"{args.entry}.json"
            out.parent.mkdir(exist_ok=True)
            with open(out, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            print(f"\nSaved to {out}")

    elif args.range:
        from_id, to_id = args.range
        import time

        RU_ALPHA = 'АБВГДЕЁЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯ'

        def entry_sort_key(eid):
            parts = eid.split('-')
            if len(parts) != 2:
                return (999, 0)
            letter = parts[0]
            try:
                number = int(parts[1])
            except ValueError:
                return (999, 0)
            return (RU_ALPHA.index(letter) if letter in RU_ALPHA else 99, number)

        sorted_entries = sorted(entry_to_idioms.keys(), key=entry_sort_key)

        # Get entries in range
        in_range = False
        results = {}
        for entry_id in sorted_entries:
            if entry_id == from_id:
                in_range = True
            if in_range and entry_to_idioms.get(entry_id):
                canonical = entry_to_idioms[entry_id][0]
                print(f"\nAnalyzing {entry_id}: «{canonical}»...")
                result = analyze_idiom(canonical)
                result['entry_id']  = entry_id
                result['all_forms'] = entry_to_idioms[entry_id]
                print_analysis(result)
                results[entry_id] = result
                time.sleep(1)
            if entry_id == to_id:
                break

        if args.save:
            out = PIPELINE_DIR / 'analyses' / f"range_{from_id}_{to_id}.json"
            out.parent.mkdir(exist_ok=True)
            with open(out, 'w', encoding='utf-8') as f:
                json.dump(results, f, ensure_ascii=False, indent=2)
            print(f"\nSaved {len(results)} analyses to {out}")

    else:
        ap.print_help()
        print("\nExamples:")
        print('  python3 analyze_idiom.py --idiom "беда не приходит одна"')
        print('  python3 analyze_idiom.py --entry Б-41 --save')
        print('  python3 analyze_idiom.py --range Б-36 Б-44 --save')
