#!/usr/bin/env python3
"""
XML → LaTeX → PDF converter for the Russian-French Dictionary of Idioms.
Closely mimics the visual style of Lubensky's R-E dictionary.
Uses XeLaTeX for full Unicode / Cyrillic / French support.
"""

import xml.etree.ElementTree as ET
import subprocess
import sys
import os
import tempfile

# ============================================================
# LaTeX DOCUMENT TEMPLATE
# ============================================================

LATEX_PREAMBLE = r"""
\documentclass[10pt,twoside]{article}
\usepackage{fontspec}
\usepackage{polyglossia}

\setmainlanguage{french}
\setotherlanguage{russian}

% Fonts — FreeSerif covers Latin, Cyrillic, French diacritics
\setmainfont{CMU Serif}
\setmonofont{DejaVu Sans Mono}[Scale=0.85]

\usepackage{microtype}
\usepackage{amssymb}
\usepackage{geometry}
\geometry{
    paperwidth=187mm,
    paperheight=254mm,
    top=18mm,
    bottom=18mm,
    inner=18mm,
    outer=15mm,
    columnsep=5mm
}

\usepackage{multicol}
\usepackage{xcolor}
\usepackage{enumitem}
\usepackage{parskip}
\usepackage{ragged2e}

% No paragraph indent — dictionary style
\setlength{\parindent}{0pt}
\setlength{\parskip}{2pt}

% Entry number + headword style
\newcommand{\entrynum}[1]{\textbf{#1}}
\newcommand{\headword}[1]{\textbf{#1}}
\newcommand{\headwordvar}[1]{\textbf{#1}}

% Usage label style — italic, small
\newcommand{\usagelabel}[1]{\textit{#1}}

% Grammar info style — upright, smaller
\newcommand{\graminfo}[1]{[#1]}

% Definition style — upright
\newcommand{\defn}[1]{#1}

% French equivalent — bold
\newcommand{\frequiv}[1]{\textbf{#1}}

% Register label
\newcommand{\reglabel}[1]{\textit{#1}}

% Russian example text — italic
\newcommand{\ruex}[1]{\textit{#1}}

% French example text — upright, indented
\newcommand{\frex}[1]{#1}

% Source citation
\newcommand{\srcite}[1]{(#1)}

% Bullet for examples
\newcommand{\exbullet}{$\diamond$\ }

% Section separator
\newcommand{\sensesep}{\textbf{1.}\ }

% Optional element marker < >
\newcommand{\optelem}[1]{\textlangle #1\textrangle}

% Synonymous variant separator
\newcommand{\variantsep}{;\quad}

% Horizontal rule between entries (thin)
\newcommand{\entrysep}{\vspace{2pt}\noindent\rule{\linewidth}{0.2pt}\vspace{2pt}}

\pagestyle{empty}

\begin{document}
\begin{multicols}{2}
\RaggedRight
\small
"""

LATEX_POSTAMBLE = r"""
\end{multicols}
\end{document}
"""

# ============================================================
# XML → LaTeX CONVERSION
# ============================================================

def escape_latex(text):
    """Escape special LaTeX characters, preserving Cyrillic and French."""
    if not text:
        return ""
    text = text.strip()
    # Combining acute accent (U+0301) used for Russian stress — preserve as-is
    # XeLaTeX with FreeSerif renders it correctly
    # Escape LaTeX specials (but not backslash itself — handle carefully)
    replacements = [
        ('&', r'\&'),
        ('%', r'\%'),
        ('$', r'\$'),
        ('#', r'\#'),
        ('^', r'\^{}'),
        ('_', r'\_'),
        ('~', r'\~{}'),
        ('{', r'\{'),
        ('}', r'\}'),
        ('≈', r'$\approx$'),
        ('◇', r'$\diamond$'),
        ('♦', r'$\blacklozenge$'),
        ('○', r'$\circ$'),
        ('≡', r'$\equiv$'),
        ('→', r'$\rightarrow$'),
        ('←', r'$\leftarrow$'),
        ('⟨', r'\textlangle '),
        ('⟩', r'\textrangle '),
        ('〈', r'\textlangle '),   # CJK left angle bracket U+3008
        ('〉', r'\textrangle '),   # CJK right angle bracket U+3009
        ('<', r'\textless '),
        ('>', r'\textgreater '),
    ]
    for old, new in replacements:
        text = text.replace(old, new)
    return text

def get_text(element, xpath, default=""):
    """Safely get text from XML element."""
    el = element.find(xpath)
    if el is not None and el.text:
        return el.text.strip()
    return default

def render_head_matter(entry):
    """Render entry number + headword + variants."""
    entry_id = entry.get('id', '')
    lines = []

    # Entry number bullet + canonical headword
    canonical_text = get_text(entry, './/canonical/text')
    if not canonical_text:
        canonical_text = get_text(entry, './/canonical')
    optional_els = [e.text.strip() for e in 
                    entry.findall('.//canonical/optional_element') 
                    if e.text]

    # Build headword with optional elements shown
    headword_display = escape_latex(canonical_text)

    line = f"\\entrynum{{{escape_latex(entry_id)}}} $\\bullet$ \\headword{{{headword_display}}}"
    lines.append(line)

    # Variants
    variants_old = entry.findall('.//variant/text')
    variants_new = [e for e in entry.findall('.//variant') if not len(e)]
    variants = variants_old if variants_old else variants_new
    if variants:
        var_texts = [escape_latex(v.text.strip()) for v in variants if v.text]
        var_line = "; ".join([f"\\headwordvar{{{v}}}" for v in var_texts])
        lines.append("; " + var_line)

    return " ".join(lines)

# Phrase type → French abbreviation mapping
PHRASE_TYPE_FR = {
    "saying":   "prov.",
    "NP":       "SN",
    "VP":       "SV",
    "AdjP":     "SAdj",
    "AdvP":     "SAdv",
    "PrepP":    "SP",
    "Interj":   "Interj",
    "formula":  "formule",
    "sent":     "prop",
    "quantif":  "quantif",
    "particle": "particule",
}

def render_grammar(entry):
    """Render grammatical information in brackets."""
    raw = get_text(entry, './/grammar/raw_grammar')
    if not raw:
        raw = get_text(entry, './/grammar/bracket')
    phrase_type = get_text(entry, './/grammar/phrase_type')
    form_restrictions = [e.text.strip() for e in 
                        entry.findall('.//grammar/form_restriction') 
                        if e.text]

    if raw:
        # Translate phrase type in raw grammar string
        for en, fr in PHRASE_TYPE_FR.items():
            raw = raw.replace(f"[{en}]", f"[{fr}]").replace(en, fr)
        return f"\\graminfo{{{escape_latex(raw)}}}"
    elif phrase_type:
        pt_fr = PHRASE_TYPE_FR.get(phrase_type, phrase_type)
        parts = [pt_fr] + form_restrictions
        return f"\\graminfo{{{escape_latex('; '.join(parts))}}}"
    return ""

def render_usage_labels(sense):
    """Render usage labels before definition."""
    labels = [e.text.strip() for e in 
              sense.findall('.//usage_labels/label') if e.text]
    if not labels:
        return ""
    return f"\\usagelabel{{{escape_latex(', '.join(labels))}}}"

def render_definition(sense):
    """Render the French definition."""
    defn_el = sense.find('definition')
    if defn_el is not None and defn_el.text:
        return f"\\defn{{{escape_latex(defn_el.text.strip())}}}"
    return ""

def render_french_equivalents(sense):
    """Render French equivalents grouped by register."""
    equivs = sense.findall('.//french_equivalents/equiv')
    if not equivs:
        return ""

    # Group by register
    by_register = {}
    for eq in equivs:
        reg = eq.get('register', 'neutre')
        text_el = eq.find('text')
        if text_el is not None and text_el.text:
            by_register.setdefault(reg, []).append(text_el.text.strip())

    # Register display order and labels
    register_order = ['prov', 'neutre', 'sout', 'litt', 'cour', 'fam', 'pop', 'arg', 'vieilli', 'iron', 'humor']
    register_labels = {
        'prov':    'prov.',
        'neutre':  '',
        'sout':    'sout.',
        'litt':    'litt.',
        'cour':    'cour.',
        'fam':     'fam.',
        'pop':     'pop.',
        'arg':     'arg.',
        'vieilli': 'vieilli',
        'iron':    'iron.',
        'humor':   'humor.',
    }

    parts = []
    for reg in register_order:
        if reg in by_register:
            label = register_labels.get(reg, reg)
            equiv_texts = "; ".join([
                f"\\frequiv{{{escape_latex(t)}}}" 
                for t in by_register[reg]
            ])
            if label:
                parts.append(f"\\reglabel{{{label}}} {equiv_texts}")
            else:
                parts.append(equiv_texts)

    # Any registers not in our order
    for reg, texts in by_register.items():
        if reg not in register_order:
            equiv_texts = "; ".join([
                f"\\frequiv{{{escape_latex(t)}}}" for t in texts
            ])
            parts.append(f"\\reglabel{{{escape_latex(reg)}}} {equiv_texts}")

    return " $|$ ".join(parts)

def render_examples(sense):
    """Render literary examples with citations.
    Supports both old schema (<ru>, <fr> children) and
    new schema (<example lang="ru">, <example lang="fr">).
    """
    examples = sense.findall('.//examples/example')
    if not examples:
        return ""

    # New schema: collect by lang attribute
    ru_ex = None
    fr_ex = None
    for ex in examples:
        lang = ex.get('lang', '')
        if lang == 'ru':
            ru_ex = ex
        elif lang == 'fr':
            fr_ex = ex

    # If new schema detected, build unified example block
    if ru_ex is not None or fr_ex is not None:
        ru_text   = get_text(ru_ex, 'sentence') if ru_ex is not None else ""
        citation  = get_text(ru_ex, 'citation') if ru_ex is not None else ""
        fr_text   = get_text(fr_ex, 'sentence') if fr_ex is not None else ""
        fr_status = fr_ex.get('status', 'pending') if fr_ex is not None else 'pending'

        status_marker = ""
        if fr_status == 'pending':
            status_marker = r" \textcolor{red}{[FR\,?]}"
        elif fr_status == 'constructed':
            status_marker = r" \textcolor{blue}{[forgé]}"

        block = ""
        if ru_text:
            block += f"\n\\exbullet \\ruex{{{escape_latex(ru_text)}}}"
            if citation:
                block += f" \\srcite{{{escape_latex(citation)}}}"
        if fr_text:
            block += f"\n\\quad \\frex{{{escape_latex(fr_text)}}}{status_marker}"
        return block

    lines = []
    for ex in examples:
        ru_el = ex.find('ru')
        fr_el = ex.find('fr')
        bibref = ex.find('bibref')

        ru_text = ru_el.text.strip() if ru_el is not None and ru_el.text else ""
        fr_text = fr_el.text.strip() if fr_el is not None and fr_el.text else ""
        fr_status = fr_el.get('status', 'pending') if fr_el is not None else 'pending'

        # Build citation
        citation = ""
        if bibref is not None:
            sl_code = get_text(bibref, 'sl_code')
            sl_suffix = get_text(bibref, 'sl_suffix')
            if sl_code:
                # Convert Шолохов-2 → author short name
                author_short = sl_code.split('-')[0] if '-' in sl_code else sl_code
                suffix_str = sl_suffix if sl_suffix else ""
                citation = f"{escape_latex(author_short)} {escape_latex(suffix_str)}"

        # French translation status marker
        status_marker = ""
        if fr_status == 'pending':
            status_marker = r" \textcolor{red}{[FR\,?]}"
        elif fr_status == 'constructed':
            status_marker = r" \textcolor{blue}{[forgé]}"

        # Build SL-style abbreviated citation: (Шолохов 2a)
        # For Russian example: full code e.g. (Шолохов 2a)
        # For French example: just the letter suffix e.g. (2a) matching SL convention
        sl_citation = ""
        fr_citation_short = ""
        if bibref is not None:
            sl_code = get_text(bibref, 'sl_code')
            sl_suffix = get_text(bibref, 'sl_suffix')
            if sl_code:
                author_short = sl_code.split('-')[0] if '-' in sl_code else sl_code
                work_num = sl_code.split('-')[1] if '-' in sl_code else ""
                # SL convention:
                # Russian citation: (Шолохов 2) — author + work number, no suffix
                # FR/EN citation:   (2a) — work number + suffix only, author implied
                suffix_str = sl_suffix if sl_suffix else ""
                sl_citation = f"{escape_latex(author_short)} {escape_latex(work_num)}"
                fr_citation_short = f"{escape_latex(work_num)}{escape_latex(suffix_str)}"

        # Format the example block
        example_block = ""
        if ru_text:
            example_block += f"\n\\exbullet \\ruex{{{escape_latex(ru_text)}}}"
            if sl_citation:
                example_block += f" \\srcite{{{sl_citation}}}"
        if fr_text:
            example_block += f"\n\\quad \\frex{{{escape_latex(fr_text)}}}"
            if fr_citation_short:
                example_block += f" \\srcite{{{fr_citation_short}}}"
            example_block += status_marker

        lines.append(example_block)

    return "\n".join(lines)

def entry_to_latex(entry):
    """Convert a single XML entry to LaTeX code."""
    parts = []

    # Head matter
    head = render_head_matter(entry)
    parts.append(head)

    # Grammar
    grammar = render_grammar(entry)
    if grammar:
        parts.append(grammar)

    # Senses — support both old schema (<sense>) and new schema (direct children)
    senses = entry.findall('sense')
    if not senses:
        # New schema: build a synthetic sense from french/examples
        import xml.etree.ElementTree as ET2
        sense = ET2.Element('sense')
        # Copy french definition
        french = entry.find('french')
        if french is not None:
            defn_el = french.find('definition')
            if defn_el is not None and defn_el.text:
                d = ET2.SubElement(sense, 'definition')
                d.text = defn_el.text
            # Add as french_equivalent
            fe = ET2.SubElement(sense, 'french_equivalents')
            eq = ET2.SubElement(fe, 'equiv')
            eq.set('register', 'neutre')
            t = ET2.SubElement(eq, 'text')
            if defn_el is not None and defn_el.text:
                t.text = defn_el.text
        # Copy examples
        examples_el = entry.find('examples')
        if examples_el is not None:
            exs = ET2.SubElement(sense, 'examples')
            for ex in examples_el.findall('example'):
                exs.append(ex)
        senses = [sense]
    multi_sense = len(senses) > 1

    for i, sense in enumerate(senses, 1):
        sense_parts = []

        # Sense number if multiple senses
        if multi_sense:
            sense_parts.append(f"\\textbf{{{i}.}}")

        # Usage labels
        labels = render_usage_labels(sense)
        if labels:
            sense_parts.append(labels)

        # Definition
        defn = render_definition(sense)
        if defn:
            sense_parts.append(defn)

        # French equivalents
        equivs = render_french_equivalents(sense)
        if equivs:
            sense_parts.append(f"\\\\\n{equivs}")

        # Examples
        examples = render_examples(sense)
        if examples:
            sense_parts.append(examples)

        parts.append(" ".join(sense_parts))

    # Etymological note
    etym = entry.find('etym_note')
    if etym is not None and etym.text:
        parts.append(f"$<$ \\textit{{{escape_latex(etym.text.strip())}}}")

    return "\n\n".join(parts)

# ============================================================
# MAIN PIPELINE
# ============================================================

def xml_to_pdf(xml_file, output_pdf, keep_tex=False):
    """Full pipeline: XML file → LaTeX → PDF."""

    # Parse XML
    tree = ET.parse(xml_file)
    root = tree.getroot()

    # Handle both single <entry> and <dictionary> root
    if root.tag == 'entry':
        entries = [root]
    else:
        entries = root.findall('entry')

    print(f"Processing {len(entries)} entry/entries...")

    # Build LaTeX body
    body_parts = []
    for entry in entries:
        entry_id = entry.get('id', '?')
        print(f"  Rendering {entry_id}...")
        latex_entry = entry_to_latex(entry)
        body_parts.append(latex_entry)
        body_parts.append("")  # blank line between entries

    latex_body = "\n\n".join(body_parts)
    full_latex = LATEX_PREAMBLE + latex_body + LATEX_POSTAMBLE

    # Write .tex file
    tex_file = output_pdf.replace('.pdf', '.tex')
    with open(tex_file, 'w', encoding='utf-8') as f:
        f.write(full_latex)
    print(f"LaTeX written to {tex_file}")

    # Compile with XeLaTeX (twice for stable layout)
    tex_dir = os.path.dirname(os.path.abspath(tex_file))
    tex_base = os.path.basename(tex_file)

    # Find xelatex — MacTeX installs to /Library/TeX/texbin/
    import shutil
    xelatex = shutil.which('xelatex') or '/Library/TeX/texbin/xelatex'

    for pass_num in range(1, 3):
        print(f"XeLaTeX pass {pass_num}...")
        result = subprocess.run(
            [xelatex, '-interaction=nonstopmode', tex_base],
            cwd=tex_dir,
            capture_output=True,
            text=True
        )
        if result.returncode != 0:
            print("XeLaTeX output:")
            # Show last 30 lines of log for diagnosis
            lines = result.stdout.split('\n')
            print('\n'.join(lines[-30:]))
            if pass_num == 1:
                print("Warning: XeLaTeX errors on pass 1, trying pass 2...")

    # Check PDF was produced
    produced_pdf = tex_file.replace('.tex', '.pdf')
    if os.path.exists(produced_pdf):
        if produced_pdf != output_pdf:
            import shutil
            shutil.copy(produced_pdf, output_pdf)
        print(f"PDF produced: {output_pdf}")
        return True
    else:
        print("ERROR: PDF was not produced. Check the .tex file for errors.")
        return False


if __name__ == '__main__':
    xml_in  = sys.argv[1] if len(sys.argv) > 1 else '/mnt/user-data/outputs/entry_B41.xml'
    pdf_out = sys.argv[2] if len(sys.argv) > 2 else '/mnt/user-data/outputs/entry_B41.pdf'
    xml_to_pdf(xml_in, pdf_out)
