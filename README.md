# Russian-French Dictionary of Idioms

A Russian-French dictionary of idioms modeled on S. Lubensky's
*Russian-English Dictionary of Idioms* (2nd edition, Yale University Press).

## Project Status
Early development — pilot page in progress.

## Structure

```
rf_dict/
├── README.md
├── .gitignore
├── bibliography/
│   └── sl_bibliography.csv     # SL source → FR translation mapping table
├── xml/
│   ├── schema/
│   │   └── rf_dictionary.xsd   # XML schema for all entries
│   └── entries/
│       └── B/
│           └── entry_B41.xml   # Sample entry Б-41
├── latex/
│   └── entry_B41.tex           # Generated LaTeX (do not edit manually)
├── pdf/
│   └── entry_B41.pdf           # Rendered output
├── pipeline/
│   ├── xml_to_latex.py         # XML → LaTeX → PDF converter
│   ├── sl_parser.py            # SL PDF entry parser (TODO)
│   ├── passage_locator.py      # Russian/French passage finder (TODO)
│   └── claude_api_wrapper.py   # Claude API entry generator (TODO)
├── docs/
│   ├── entry_structure.md      # Notes on SL entry apparatus
│   └── lawyer_letter.md        # IP consultation letter (TODO)
└── samples/
    └── page_10_pilot/          # Pilot page (entries Б-36 to Б-44)
```

## Pipeline Overview

```
SL PDF (2nd ed.)
    ↓ sl_parser.py
Structured entry (XML)
    ↓ passage_locator.py + bibliography lookup
French example located
    ↓ claude_api_wrapper.py
Complete RF entry (XML)
    ↓ xml_to_latex.py
LaTeX source
    ↓ xelatex
PDF
```

## Base Dictionary

- **Source:** Lubensky, S. *Russian-English Dictionary of Idioms*, 2nd ed.
- **Edition used:** 2nd (Yale University Press)
- **Total entries:** ~7,500
- **Pilot scope:** Page 10 (entries Б-36 to Б-44)

## Technical Requirements

- Python 3.8+
- XeLaTeX (TeX Live 2023+)
- FreeSerif font (freefont package)
- Python packages: see requirements.txt

## Notes on French Apparatus

Unlike the English edition, French equivalents are organized by register:
- `prov.` — proverbial
- `sout.` — soutenu / literary
- `cour.` — courant / standard
- `fam.` — familier
- `pop.` — populaire
- `arg.` — argotique
- `vieilli` — dated

## License

To be determined pending IP legal consultation.

## RNC Corpus Workflow

The `rnc` Python library is currently broken against ruscorpora.ru (May 2026).
Use the manual export workflow instead:

### Searching for idiom examples

1. Go to [ruscorpora.ru](https://ruscorpora.ru) → main corpus
2. Search using lemma forms from `pipeline/rnc_search.py` PILOT_QUERIES
3. Export results: click **Скачать** → CSV
4. Save to `pipeline/rnc_exports/` as `B41_беда_не_приходит_одна.csv`
5. Import: `python3 pipeline/rnc_db.py import pipeline/rnc_exports/FILE.csv Б-41`
6. Review best examples: `python3 pipeline/rnc_db.py best Б-41`

### Pilot page query reference

| Entry | Idiom | RNC query | Search type | Notes |
|-------|-------|-----------|-------------|-------|
| Б-36 | В БЕГАХ | `в бегах` | lexform | preposition essential |
| Б-37 | КАК БЕГЕМОТ | `бегемот` | lexgramm | key noun sufficient |
| Б-38 | СПАСАТЬСЯ БЕГСТВОМ | `спасаться бегство` | lexgramm | two content words |
| Б-39 | НА БЕГУ | `на бегу` | lexform | preposition essential |
| Б-40 | СЕМЬ БЕД ОДИН ОТВЕТ | `семь беда ответ` | lexgramm | distinctive combination |
| Б-41 | БЕДА НЕ ПРИХОДИТ ОДНА | `беда приходить один` | lexgramm | ✅ tested, 29 results |
| Б-42 | ЛИХА БЕДА | `лихой беда` | lexgramm | obsoles, may be rare |
| Б-43 | ЛИХА БЕДА НАЧАЛО | `лихой беда начало` | lexgramm | saying |
| Б-44 | НЕ БЕДА | `не беда` | lexform | negation integral |

**Search type guidance:**
- `lexgramm` — lemma search, finds all inflected forms. Use for content words.
- `lexform` — exact form search. Use for frozen prepositional phrases and negated idioms.
