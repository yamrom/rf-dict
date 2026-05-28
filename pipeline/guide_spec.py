#!/usr/bin/env python3
"""
guide_spec.py — Structured specification derived from SL Guide to the Dictionary

This is the machine-readable form of the Guide, used as a prompt specification
for Claude to generate grammatical analyses of Russian idioms.

Each section corresponds to a section of the Guide, converted from natural
language prose into structured Python data that can be injected into prompts.
"""

# ============================================================
# SECTION 1: CHARACTERISTICS OF IDIOMS
# Defective paradigm properties that must be checked for every idiom
# ============================================================

DEFECTIVE_PARADIGM = {
    "description": (
        "Many idioms have a defective paradigm — they are restricted "
        "to a subset of the grammatical forms normally available to their phrase type."
    ),
    "dimensions": {
        "case": {
            "description": "Idiom restricted to specific grammatical case(s)",
            "check": "Can the idiom appear in all cases, or only some?",
            "flag": "case_only",
            "example": {
                "idiom": "САМАЯ МАЛОСТЬ",
                "restriction": "accusative only (самую малость) in sense 2",
                "notation": "accus only"
            }
        },
        "number": {
            "description": "Idiom restricted to singular or plural only",
            "check": "Can the idiom appear in both singular and plural?",
            "flags": ["sing_only", "pl_only"],
            "examples": [
                {"idiom": "ВЫСОКИЕ МАТЕРИИ", "restriction": "pl only"},
                {"idiom": "ДУРНОЙ ГЛАЗ",     "restriction": "sing only"},
            ]
        },
        "person": {
            "description": "Idiom restricted to specific grammatical person",
            "check": "Is the idiom restricted to 1st, 2nd, or 3rd person?",
            "flag": "person_restriction",
            "examples": [
                {"idiom": "БОЮСЬ СКАЗАТЬ",       "restriction": "1st pers sing only"},
                {"idiom": "НЕДОРОГО ВОЗЬМЁТ",    "restriction": "not used in 1st pers"},
            ]
        },
        "tense_aspect": {
            "description": "Idiom restricted to specific tense or aspect",
            "check": "Is the idiom restricted to imperfective, perfective, present, past?",
            "flags": ["impfv_only", "pfv_only", "pres_only", "past_only",
                      "fut_only", "pfv_past_only"],
            "examples": [
                {"idiom": "В МУТНОЙ ВОДЕ РЫБУ ЛОВИТЬ", "restriction": "impfv only"},
                {"idiom": "МАЛО НЕ ПОКАЖЕТСЯ",          "restriction": "pfv only"},
                {"idiom": "В ЧЁМ ДУША ДЕРЖИТСЯ",        "restriction": "pres only"},
                {"idiom": "ПОШЛА ПИСАТЬ ГУБЕРНИЯ",       "restriction": "pfv past only"},
            ]
        },
        "finite_nonfinite": {
            "description": "Idiom lacks infinitive, participle, or verbal adverb forms",
            "check": "Does the idiom have corresponding nonfinite forms?",
            "flag": "finite_only",
            "example": {
                "idiom": "НЕ ПРОПАДЁТ",
                "restriction": "no infinitive, participle, or verbal adverb"
            }
        },
    }
}

# ============================================================
# NEGATION BEHAVIOR
# The role of НЕ is often unpredictable and must be analyzed per idiom
# ============================================================

NEGATION_RULES = {
    "description": (
        "The role of the negative particle НЕ in idioms is often unpredictable. "
        "Four patterns exist:"
    ),
    "patterns": {
        "negation_impossible": {
            "description": "Affirmative idiom cannot be used with negation at all",
            "flag": "no_negation",
            "examples": [
                "БАБУШКА НАДВОЕ СКАЗАЛА",
                "КАМЕНЬ С ДУШИ СВАЛИЛСЯ",
            ]
        },
        "negation_loses_meaning": {
            "description": (
                "Idiom used only with НЕ, but the particle loses its negating meaning"
            ),
            "flag": "he_non_negative",
            "example": "КОМАР НОСА НЕ ПОДТОЧИТ — means 'done to a T', not a negation"
        },
        "negation_produces_antonym": {
            "description": "Adding НЕ produces the antonym — separate entries",
            "flag": "negation_antonym",
            "example": "ПО ВКУСУ / НЕ ПО ВКУСУ — '(not) to s.o.'s taste'"
        },
        "negation_changes_senses": {
            "description": (
                "Affirmative and negative forms have different numbers of senses "
                "— treated as separate entries"
            ),
            "flag": "negation_separate_entry",
            "example": "В ЛАДУ (1 sense) vs НЕ В ЛАДУ (3 senses)"
        },
        "negation_same_meaning": {
            "description": "Idiom has same meaning with or without negation",
            "flag": "negation_optional",
            "example": "(НЕ) ПРИШЕЙ КОБЫЛЕ ХВОСТ — 'excess baggage' either way"
        },
    }
}

# ============================================================
# ASPECT BEHAVIOR (for VP idioms)
# Imperfective and perfective may have different meanings
# ============================================================

ASPECT_RULES = {
    "description": (
        "Idioms differing only in verbal aspect may have different meanings "
        "and a different number of senses. Both aspects are given in the headword "
        "separated by a slash: ВАЛЯТЬ/СВАЛЯТЬ ДУРАКА."
    ),
    "checks": [
        "Does the imperfective form have the same meaning as the perfective?",
        "If meanings differ, each aspect gets its own sense or entry.",
        "If only one aspect is used, only that form appears in the headword.",
    ],
    "flags": ["impfv_only", "pfv_only", "both_aspects"],
    "example": {
        "impfv": {
            "idiom": "ВАЛЯТЬ ДУРАКА",
            "senses": 4,
            "meanings": [
                "feign stupidity",
                "act mischievously",
                "act irresponsibly / make a blunder",
                "be idle"
            ]
        },
        "pfv": {
            "idiom": "СВАЛЯТЬ ДУРАКА",
            "senses": 1,
            "meanings": ["make a blunder"],
            "note": "Included at sense 3 of the imperfective"
        }
    }
}

# ============================================================
# SYNTACTIC FUNCTION RESTRICTIONS
# Some idioms cannot perform all syntactic functions of their phrase type
# ============================================================

SYNTACTIC_RESTRICTIONS = {
    "description": (
        "Many idioms lack some syntactic functions of the phrase type to which they belong."
    ),
    "patterns": {
        "predic_only": {
            "description": "NP used only as predicate (subject complement), not as subject/object",
            "example": "НЕ ИГОЛКА — only predicative"
        },
        "subj_obj_only": {
            "description": "NP used only as subject or object, not predicatively",
            "example": "ЦЕЛЫЙ КОРОБ новостей — only subj or obj"
        },
        "premodif_only": {
            "description": "AdjP used only before the noun it modifies",
            "flag": "premodif"
        },
        "postmodif_only": {
            "description": "AdjP used only after the noun it modifies",
            "flag": "postmodif"
        },
    }
}

# ============================================================
# METAPHORICAL EXTENSION
# Some idioms are extensions of literal word combinations
# ============================================================

METAPHORICAL_EXTENSION = {
    "description": (
        "Some idioms are metaphorical extensions of nonidiomatic word combinations. "
        "The literal meaning is noted separately from idiomatic meanings."
    ),
    "check": "Does this idiom also have a literal non-idiomatic reading?",
    "flag": "has_literal_meaning",
    "example": {
        "idiom": "ПОДНИМАТЬ/ПОДНЯТЬ РУКУ",
        "literal": "to raise one's hand/arm",
        "idiomatic_senses": [
            "~ на кого: to (try to) harm s.o. physically",
            "~ на кого-что: to criticize and express disapproval"
        ]
    }
}

# ============================================================
# ARCHAIC / UNIQUE COMPONENTS
# ============================================================

LEXICAL_PROPERTIES = {
    "unique_component": {
        "description": "Idiom contains a lexical component not found elsewhere in modern Russian",
        "flag": "unique_lexical_component",
        "examples": ["ВО ВСЕОРУЖИИ", "ДО СКОНЧАНИЯ ВЕКА", "БЕЗ УМОЛКУ"]
    },
    "archaic_form": {
        "description": "Idiom contains an archaic grammatical form",
        "flag": "archaic_component",
        "examples": [
            {"idiom": "ТЕМНА ВОДА ВО ОБЛАЦЕХ",
             "note": "архаичная форма локатива мн.ч. от 'облако'"},
            {"idiom": "СКРЕПЯ СЕРДЦЕ",
             "note": "архаичная форма краткого действительного причастия от 'скрепить'"}
        ]
    }
}

# ============================================================
# MASTER CHECKLIST
# Questions Claude must answer for every idiom
# ============================================================

IDIOM_ANALYSIS_CHECKLIST = [
    # Phase 1: Classification
    ("phrase_type",      "What is the phrase type? [NP/VP/AdjP/AdvP/PrepP/saying/formula/Interj]"),
    ("subtype",          "Any subtype? [как+NP / sent adv / quantif / etc.]"),

    # Phase 2: Paradigm restrictions
    ("case_restriction",    "Is the idiom restricted to specific case(s)?"),
    ("number_restriction",  "Is it restricted to singular or plural only?"),
    ("person_restriction",  "Is it restricted to specific grammatical person?"),
    ("tense_restriction",   "Is it restricted to specific tense or aspect?"),
    ("finite_only",         "Does it lack nonfinite forms (infinitive/participle/verbal adverb)?"),

    # Phase 3: Syntactic function
    ("syntactic_functions", "What syntactic functions can it perform? [subj/obj/predic/adv/modif]"),
    ("fixed_WO",            "Is word order fixed?"),

    # Phase 4: Negation
    ("negation_behavior",   "How does НЕ interact with this idiom? [impossible/non-negative/antonym/separate_entry/optional/normal]"),

    # Phase 5: Aspect (VP only)
    ("aspect",              "For VP: impfv only / pfv only / both? Do aspects have different meanings?"),

    # Phase 6: Stylistic register
    ("register",            "Stylistic label(s): [neutral/coll/highly coll/lit/obs/obsoles/old-fash/rare/disapprov/iron/humor/elev/offic/vulg/rhet/substand/euph/derog/folk poet/approv]"),

    # Phase 7: Subject/object restrictions
    ("subj_type",           "Subject type restriction: [human/collect/animal/abstr/any]"),
    ("obj_type",            "Object type restriction if applicable: [human/abstr/concr/any]"),

    # Phase 8: Special properties
    ("literal_meaning",     "Does it have a parallel literal non-idiomatic meaning?"),
    ("unique_component",    "Does it contain a unique lexical component?"),
    ("archaic_component",   "Does it contain an archaic grammatical form?"),
    ("etym_note",           "Any etymology? [biblical/literary/historical/calque/folk]"),
]

# ============================================================
# SECTION 2: TYPES OF IDIOMS
# Classification of all idiom types included in the dictionary
# ============================================================

IDIOM_TYPES = {

    # ── TRADITIONAL IDIOMS (function as a part of speech) ────────
    "NP": {
        "label": "noun phrase",
        "description": "Functions as a noun phrase — subject, object, or predicate",
        "example": "ТЕЛЯЧЬИ НЕЖНОСТИ 'sloppy sentimentality'",
        "grammatical_notation": "NP",
        "subj_compl_possible": True,
    },
    "VP": {
        "label": "verb phrase",
        "description": "Functions as a verb phrase",
        "example": "БЕЖАТЬ ВПЕРЕДИ ПАРОВОЗА 'jump the gun'",
        "grammatical_notation": "VP",
        "requires_aspect_check": True,
    },
    "AdjP": {
        "label": "adjective phrase",
        "description": "Functions as an adjective phrase — modifier or predicate",
        "example": "ИЗ РЯДА ВОН ВЫХОДЯЩИЙ 'extraordinary'",
        "grammatical_notation": "AdjP",
    },
    "AdvP": {
        "label": "adverb phrase",
        "description": "Functions as an adverb phrase",
        "example": "ВКРИВЬ И ВКОСЬ 'every which way'",
        "grammatical_notation": "AdvP",
        "subtypes": ["adv", "sent adv"],
    },
    "PrepP": {
        "label": "prepositional phrase",
        "description": "Functions as a prepositional phrase",
        "example": "В БЕГАХ",
        "grammatical_notation": "PrepP",
    },

    # ── SENTENCE-FUNCTIONING IDIOMS ───────────────────────────────
    "saying": {
        "label": "saying / proverb",
        "description": (
            "Functions as a complete sentence. Includes proverbs, sayings, "
            "and commonly used quotations (крылатые слова). "
            "Approximately 350 entries. Fixed word order."
        ),
        "grammatical_notation": "saying",
        "example": "БАБУШКА НАДВОЕ СКАЗАЛА 'that remains to be seen'",
        "fixed_WO": True,
        "negation_usually_impossible": True,
    },

    # ── INTENSIFIERS AND SIMILES ──────────────────────────────────
    "intensifier": {
        "label": "pure intensifier",
        "description": "Phrase serving as intensifier for collocating words",
        "grammatical_notation": "AdvP (intensif) or quantit",
        "example": "ДО ПОЛУСМЕРТИ 'intensely, to a very high degree'",
        "subtype": "pure_intensif",
    },
    "neg_intensifier": {
        "label": "negative intensifier",
        "description": "Phrase serving as negative intensifier",
        "example": "нужен КАК РЫБКЕ ЗОНТИК '(as useful) as an umbrella to a duck'",
        "grammatical_notation": "neg intensif",
    },
    "simile": {
        "label": "frozen simile",
        "description": "Fixed comparative phrase (как + NP)",
        "grammatical_notation": "как + NP",
        "example": "красный КАК РАК '(as) red as a beet'",
        "pattern": "как + NP",
        "nom_only": True,  # adjective/noun always in nominative
    },
    "word_intensifier": {
        "label": "word + intensifier phrase",
        "description": "Phrase consisting of a word and its intensifier",
        "example": "ВОЛЧИЙ АППЕТИТ 'a ravenous appetite'",
        "grammatical_notation": "NP",
    },

    # ── INTERJECTIONS ─────────────────────────────────────────────
    "Interj": {
        "label": "interjection",
        "description": (
            "Fixed phrase used to express emotions and reactions. "
            "Syntactically independent. Can express different or even "
            "opposite emotions depending on context and intonation."
        ),
        "grammatical_notation": "Interj",
        "example": "НУ И НУ! 'well, I'll be (damned)!'",
        "fixed_WO": True,
        "intonation_dependent": True,
    },

    # ── FORMULA PHRASES ───────────────────────────────────────────
    "formula": {
        "label": "formula phrase",
        "description": (
            "Fixed phrase used in standard communication situations: "
            "greeting, parting, apology, thanks, response to thanks, etc."
        ),
        "grammatical_notation": "formula phrase",
        "example": "ВСЕГО ХОРОШЕГО 'all the best!'",
        "fixed_WO": True,
        "situational": True,
        "situations": [
            "greeting", "parting", "apology", "response_to_apology",
            "thanks", "response_to_thanks", "wish", "request"
        ],
    },

    # ── GRAMMATICAL / FUNCTION IDIOMS ────────────────────────────
    "prep_idiom": {
        "label": "prepositional idiom",
        "description": "Fixed phrase functioning as a preposition",
        "grammatical_notation": "Prep",
        "example": "ПО НАПРАВЛЕНИЮ к кому-чему 'toward'",
        "fixed_WO": True,
    },
    "conj_idiom": {
        "label": "conjunctional idiom",
        "description": "Fixed phrase functioning as a conjunction",
        "grammatical_notation": "Conj",
        "example": "ПЕРЕД ТЕМ КАК 'before'",
        "fixed_WO": True,
    },
    "particle_idiom": {
        "label": "particle idiom",
        "description": "Fixed phrase functioning as a particle",
        "grammatical_notation": "Particle",
        "example": "ТОГО И ГЛЯДИ 'any minute now'",
        "fixed_WO": True,
    },

    # ── QUANTIFIERS ───────────────────────────────────────────────
    "quantif": {
        "label": "quantifier",
        "description": (
            "Phrase functioning as a quantifier — either as predicate "
            "(quantit subj-compl) or as adverbial (adv quantif)"
        ),
        "grammatical_notation": "quantit subj-compl or adv (quantif)",
        "examples": [
            "КОТ НАПЛАКАЛ 'practically no... at all'",
            "КАК НА МАЛАНЬИНУ СВАДЬБУ '(cook) enough for an army'",
        ],
    },
}

# ============================================================
# TYPE DETECTION RULES
# How to classify an idiom into a type from its form
# ============================================================

TYPE_DETECTION = {
    "priority_order": [
        "saying",       # Full sentence form, fixed WO
        "formula",      # Situational fixed phrase
        "Interj",       # Exclamatory, intonation-dependent
        "simile",       # как + NP pattern
        "prep_idiom",   # Functions as preposition
        "conj_idiom",   # Functions as conjunction
        "particle_idiom",
        "quantif",      # Quantity expression
        "intensifier",  # Pure intensifier
        "VP",           # Contains conjugated verb
        "NP",           # Noun-headed
        "AdjP",         # Adjective-headed
        "PrepP",        # Preposition-headed
        "AdvP",         # Adverb-functioning
    ],
    "signals": {
        "saying": [
            "Full sentence structure (subject + predicate)",
            "Often imperative or 3rd person",
            "No free argument slots",
            "Proverbial/gnomic meaning",
        ],
        "simile": [
            "Contains как + noun in nominative",
            "Modifies or intensifies another word",
            "Pattern: [adjective] как [noun]",
        ],
        "formula": [
            "Used in standard social interaction situations",
            "Often imperative or exclamatory",
            "Situationally bound",
        ],
        "VP": [
            "Contains a verb as head component",
            "Has subject argument slot (X)",
            "May have object argument slot (Y)",
        ],
        "NP": [
            "Noun-headed",
            "Can function as subject, object, or predicate",
            "No verb head",
        ],
    }
}

# ============================================================
# SECTION 3: GRAMMAR
# Rules for grammatical descriptions in square brackets
# ============================================================

GRAMMAR_RULES = {

    # ── COPULA ────────────────────────────────────────────────────
    "copula": {
        "description": (
            "The term 'copula' embraces a broad group of copula-like verbs: "
            "оказываться/оказаться, казаться/показаться, становиться/стать, "
            "делаться/сделаться, считаться, представляться, оставаться/остаться, "
            "бывать, являться (in copular use), and occasionally сидеть, стоять."
        ),
        "bytyo_notation": (
            "бытьø means: idiom used as subject-complement only with copular быть "
            "which has zero form in present tense. "
            "Notation in brackets: 'subj-compl with бытьø'"
        ),
        "est_pattern": (
            "When idiom can be used with both бытьø AND existential/possessive быть "
            "(present form: есть), two patterns are given — with and without есть."
        ),
    },

    # ── SUBJECT ───────────────────────────────────────────────────
    "subject": {
        "description": (
            "The grammatical subject may be in nominative OR genitive case. "
            "A genitive NP functions as subject when a quantifier is the predicate: "
            "e.g. 'Денег у меня кот наплакал' — денег (gen) is the subject."
        ),
        "subject_types": {
            "human":   "noun denoting a person",
            "collect": "collective noun (group, organization, etc.)",
            "animal":  "noun denoting an animal",
            "abstr":   "abstract noun",
            "concr":   "concrete (physical) noun",
            "infin":   "infinitive clause",
            "clause":  "subordinate clause",
        },
        "notation": "subj: human / collect / animal / abstr / concr / infin / clause",
    },

    # ── PRONOUNS IN DEFINITIONS ───────────────────────────────────
    "pronoun_conventions": {
        "one / one's / o.s.": "corresponds to the SUBJECT of the Russian clause",
        "s.o. / s.o.'s":      "corresponds to the OBJECT of the Russian clause",
        "person X/Y/Z":       "animate subject or object",
        "thing X/Y/Z":        "inanimate subject or object",
        "another":            "second object when both slots are filled",
        "note": (
            "Abbreviated forms s.o. and sth. are used in all cases EXCEPT "
            "when 'someone else' or 'something else' are irreplaceable "
            "(e.g. С ЧУЖОГО ПЛЕЧА 'someone else's castoff')."
        ),
    },

    # ── TENSE-ASPECT CORRESPONDENCE ──────────────────────────────
    "tense_aspect": {
        "description": "Russian and English tense-aspect forms do not fully correspond.",
        "mappings": {
            "Russian present (impfv only)": [
                "English simple present",
                "English present progressive",
            ],
            "Russian perfective past": [
                "English simple past",
                "English present perfect",
                "English past perfect",
            ],
        },
        "note": (
            "Patterns use simple present and simple past as models. "
            "They should be modified as context requires."
        ),
    },

    # ── WORD ORDER ────────────────────────────────────────────────
    "word_order": {
        "free_WO": "Not commented upon — free word order is the default",
        "fixed_WO": "Noted as 'fixed WO' in grammatical brackets",
        "usu_this_WO": "Noted as 'usu. this WO' when rarely changed",
        "movable_component": (
            "When only one component can change position, this is specified: "
            "e.g. 'the verb may take the final position, otherwise fixed WO'"
        ),
        "note": (
            "Even fixed-WO idioms may occasionally have different word order "
            "in poetry or for stylistic effect."
        ),
    },

    # ── VARIABLES IN PATTERNS ────────────────────────────────────
    "variables": {
        "X": "subject (human, both genders unless specified)",
        "Y": "primary object",
        "Z": "secondary object or location",
        "X-а / X-у / X-ов": "X declined in appropriate case",
        "Y-а / Y-у / Y-ов": "Y declined in appropriate case",
        "X's / Y's":         "possessive form in English equivalents",
        "кого-чего / кому-чему etc.": "case-specific argument slots in headword",
    },

    # ── GRAMMATICAL BRACKET CONTENTS ─────────────────────────────
    "bracket_contents": {
        "description": "The square brackets [ ] contain grammatical description of the idiom",
        "components_in_order": [
            "phrase_type",          # NP / VP / AdjP / AdvP / PrepP / saying / Interj / formula phrase
            "form_restriction",     # Invar / these forms only / sing only / pl only / etc.
            "syntactic_function",   # subj / obj / adv / modif / subj-compl / predic
            "copula_spec",          # with бытьø / with copula / nom or instrum
            "subject_spec",         # subj: human / abstr / etc.
            "object_spec",          # obj: human / abstr / etc.
            "foll_by",              # foll. by infin / foll. by clause
            "WO_spec",              # fixed WO / usu. this WO
        ],
        "example": {
            "idiom": "В БЕГАХ",
            "bracket": "PrepP; Invar; subj-compl with бытьø (subj: human)",
            "parsed": {
                "phrase_type": "PrepP",
                "form": "Invar",
                "syntactic_function": "subj-compl",
                "copula": "бытьø",
                "subject_type": "human",
            }
        },
        "example2": {
            "idiom": "СПАСАТЬСЯ/СПАСТИСЬ БЕГСТВОМ",
            "bracket": "VP; subj: human, collect, or animal; usu. this WO",
            "parsed": {
                "phrase_type": "VP",
                "subject_type": ["human", "collect", "animal"],
                "WO": "usu. this WO",
            }
        },
    },
}

# ============================================================
# SECTION 4: STYLISTIC LABELS
# Three groups: temporal, register, emotional-expressive
# ============================================================

STYLISTIC_LABELS = {
    "temporal": {
        "obs":      "obsolete — not used in modern Russian literary or colloquial language",
        "obsoles":  "obsolescent — rarely used, perceived as archaic",
        "old-fash": "old-fashioned — used mainly by older speakers",
        "rare":     "used rarely, may seem slightly unusual",
        "recent":   "entered usage relatively recently",
    },
    "register": {
        "neutral":      "no label — stylistically neutral, used in any situation",
        "coll":         "colloquial — informal speech (oral or written)",
        "highly coll":  "highly colloquial — very informal, often emotional; inappropriate in formal/semi-formal contexts",
        "substand":     "substandard — deviates from grammatical/syntactic norm; speech of less educated",
        "slang":        "came into colloquial speech from a specific social group",
        "euph":         "euphemism — inoffensive substitute for crude/shocking expression",
        "lit":          "literary — typical of educated speakers; mainly formal/academic contexts",
        "rhet":         "rhetorical — intended to produce an effect; mainly oratory",
        "elev":         "elevated — used in lofty or solemn written texts or speech",
        "offic":        "official — used in official situations and/or bureaucratic jargon",
        "special":      "used only or mainly in specialized contexts",
        "folk poet":    "folkloric-poetic — from oral folk tradition, retains folkloric coloring",
        "vulg":         "vulgar — socially or aesthetically unacceptable; indecent",
        "taboo":        "directly related to sex or bodily functions; unacceptable in normative texts",
    },
    "emotional_expressive": {
        "approv":   "approving",
        "humor":    "humorous",
        "iron":     "ironic — used in meaning opposite to its literal meaning",
        "humor or iron": "humorous or ironic (predominant element listed first)",
        "disapprov": "disapproving",
        "derog":    "derogatory",
        "condes":   "condescending",
        "impol":    "impolite",
        "rude":     "rude",
    },
    "note": (
        "Labels apply to the Russian idiom only. "
        "Neutral idioms (no label) can be used in any situation with any interlocutor. "
        "English equivalents are chosen to match the Russian register as closely as possible."
    ),
}

# ============================================================
# FRENCH GRAMMATICAL LABEL MAPPING
# SL English notation → French lexicographic equivalents
# ============================================================

FR_GRAMMAR_LABELS = {
    # Phrase types
    "saying":        "loc. prov.",   # locution proverbiale
    "NP":            "loc. nom.",    # locution nominale
    "VP":            "loc. verb.",   # locution verbale
    "AdjP":          "loc. adj.",    # locution adjectivale
    "AdvP":          "loc. adv.",    # locution adverbiale
    "PrepP":         "loc. prép.",   # locution prépositive
    "Interj":        "interj.",      # interjection
    "formula":       "formule",      # formule de politesse
    "simile":        "compar. fig.", # comparaison figée
    "intensifier":   "intensif.",    # intensificateur
    "quantif":       "quantif.",     # quantificateur
    "prep_idiom":    "prép.",        # préposition
    "conj_idiom":    "conj.",        # conjonction
    "particle_idiom": "part.",       # particule

    # Stylistic labels
    "coll":          "fam.",         # familier
    "highly coll":   "très fam.",    # très familier
    "substand":      "pop.",         # populaire
    "slang":         "arg.",         # argotique
    "obs":           "vx.",          # vieux
    "obsoles":       "vieilli.",     # vieilli
    "old-fash":      "vieilli.",     # vieilli
    "lit":           "litt.",        # littéraire
    "elev":          "sout.",        # soutenu
    "offic":         "admin.",       # administratif
    "rhet":          "rhét.",        # rhétorique
    "iron":          "iron.",        # ironique
    "humor":         "plaisant.",    # plaisant
    "disapprov":     "péj.",         # péjoratif
    "derog":         "péj.",         # péjoratif
    "vulg":          "vulg.",        # vulgaire
    "euph":          "euphem.",      # euphémique
    "folk poet":     "folkl.",       # folklorique
    "rare":          "rare.",        # rare
    "special":       "spéc.",        # spécialisé

    # Syntactic functions
    "subj-compl":    "attrib.",      # attribut du sujet
    "adv":           "adv.",         # adverbe / adverbial
    "modif":         "épith.",       # épithète
    "Invar":         "inv.",         # invariable
    "fixed WO":      "ordre fixe",   # ordre des mots fixe
    "indep. sent":   "phrase indép.", # phrase indépendante
}


def to_fr_label(en_label: str) -> str:
    """Convert an English SL label to its French equivalent."""
    return FR_GRAMMAR_LABELS.get(en_label, en_label)


def build_fr_grammar_bracket(analysis: dict) -> str:
    """
    Build a French-style grammar bracket from the analysis dict.
    For sayings: [loc. prov.] — no further annotation needed.
    For others: [phrase_type; form; function; WO; register]
    """
    phrase_type = analysis.get("phrase_type", "")
    form        = analysis.get("form_restriction", "")
    functions   = analysis.get("syntactic_functions", [])
    wo          = analysis.get("word_order", "")
    register    = analysis.get("register", {})

    parts = []

    # Phrase type
    if phrase_type:
        parts.append(to_fr_label(phrase_type))

    # Sayings need no further annotation
    if phrase_type in ("saying", "formula", "Interj"):
        return "[" + parts[0] + "]"

    # Form restriction
    if form and form not in ("null", None, "free"):
        parts.append(to_fr_label(form))

    # Primary syntactic function — skip redundant ones
    skip_functions = {"indep. sent"}
    if functions:
        primary = functions[0]
        if primary not in skip_functions:
            fr_func = to_fr_label(primary)
            if fr_func not in parts:
                parts.append(fr_func)

    # Word order — only note if fixed
    if wo == "fixed WO":
        parts.append("ordre fixe")

    # Stylistic labels — only if non-neutral
    temporal   = register.get("temporal", "")
    stylistic  = register.get("stylistic", "")
    expressive = register.get("expressive", "")
    for label in [temporal, stylistic, expressive]:
        if label and label not in ("null", None, "neutral"):
            fr = to_fr_label(label)
            if fr not in parts:
                parts.append(fr)

    return "[" + "; ".join(parts) + "]" if parts else ""


if __name__ == '__main__':
    print("Guide Spec loaded.")
    # Test French label mapping
    test_analysis = {
        "phrase_type": "saying",
        "form_restriction": "Invar",
        "syntactic_functions": ["indep. sent"],
        "word_order": "fixed WO",
        "register": {"temporal": None, "stylistic": None, "expressive": None}
    }
    print(f"Test: {build_fr_grammar_bracket(test_analysis)}")
    # Expected: [loc. prov.; inv.; phrase indép.; ordre fixe]
    print(f"Defective paradigm dimensions: {len(DEFECTIVE_PARADIGM['dimensions'])}")
    print(f"Negation patterns: {len(NEGATION_RULES['patterns'])}")
    print(f"Analysis checklist items: {len(IDIOM_ANALYSIS_CHECKLIST)}")
    print()
    print("Master checklist:")
    for field, question in IDIOM_ANALYSIS_CHECKLIST:
        print(f"  {field:25s} {question[:60]}")
