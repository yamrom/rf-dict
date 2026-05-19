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
