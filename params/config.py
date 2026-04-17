ZENODO_API = "https://zenodo.org/api/records"
DRYAD_API = "https://datadryad.org/api/v2"
FIGSHARE_API = "https://api.figshare.com/v2"

# Open licenses accepted by QDArchive.
# Match uses startswith() so "cc-by-4.0" matches the "cc-by" prefix.
OPEN_LICENSE_PREFIXES = {
    "cc-by",
    "cc0",
    "cc-zero",
    "odc-by",
    "pddl",
    "cc-pddc",
}

# ── Zenodo query notes ────────────────────────────────────────────────────────
# Unauthenticated requests are capped at 25 results/page.
# To use size > 25, create a free Zenodo account, generate a personal token at
# https://zenodo.org/account/settings/applications/ and pass it to ZenodoClient:
#   ZenodoClient(access_token="your_token_here")
#
# Queries use Lucene syntax. Quoted strings = exact phrase. Single tokens don't
# need quotes. Words with dots/hyphens (ATLAS.ti, REFI-QDA) are quoted so the
# tokeniser doesn't split them.
# ─────────────────────────────────────────────────────────────────────────────

# First pass: QDA software / file-format names — high precision, low volume.
QUERIES_QDA = [
    "qdpx",
    "nvpx",
    "atlproj",
    "mx22",
    '"REFI-QDA"',
    "NVivo",
    '"ATLAS.ti"',
    "MaxQDA",
    "Dedoose",
    "QDAcity",
    '"QDA Miner"',
    "Transana",
    "f4analyse",
    "CAQDAS",
    '"qualitative data analysis"',
    '"coded transcript"',
]

# Second pass: qualitative methodology keywords — broader, higher volume.
QUERIES_QUAL_EN = [
    '"interview transcript"',
    '"qualitative research"',
    '"qualitative data"',
    '"focus group"',
    "ethnography",
    '"grounded theory"',
    '"semi-structured interview"',
    '"thematic analysis"',
    '"narrative analysis"',
    '"case study research"',
    '"participant observation"',
    '"qualitative coding"',
    '"open-ended responses"',
    '"open-ended questions"',
    '"biographical interview"',
    '"life history interview"',
    '"action research" qualitative',
    '"interpretive research"',
    '"interpretative phenomenological"',
    "QualCoder",
    '"mixed methods" qualitative',
    '"codebook" qualitative',
]

# Non-English queries — useful for Zenodo (international deposits) and
# language-specific repositories (DANS, DataverseNO, QualidataNet).
QUERIES_MULTILINGUAL = {
    "de": [                          # German
        '"qualitative Forschung"',
        '"qualitatives Interview"',
        "Leitfadeninterview",
        "Gruppendiskussion",
        "Biografieforschung",
        '"qualitative Inhaltsanalyse"',
        '"Transkript Interview"',
    ],
    "nl": [                          # Dutch  (DANS)
        '"kwalitatief onderzoek"',
        '"kwalitatief interview"',
        "focusgroep",
        '"diepte-interview"',
        '"transcriptie interview"',
    ],
    "no": [                          # Norwegian  (DataverseNO)
        '"kvalitativ forskning"',
        '"kvalitativt intervju"',
        "fokusgruppe",
        "dybdeintervju",
    ],
    "es": [                          # Spanish
        '"investigación cualitativa"',
        '"entrevista cualitativa"',
        '"grupo focal"',
        '"análisis temático"',
        '"transcripción entrevista"',
    ],
    "fr": [                          # French
        '"recherche qualitative"',
        '"entretien qualitatif"',
        '"groupe de discussion"',
        '"analyse thématique"',
    ],
    "pt": [                          # Portuguese
        '"pesquisa qualitativa"',
        '"entrevista qualitativa"',
        '"grupo focal"',
        '"análise temática"',
    ],
}

# Flat list of all multilingual queries (for passing directly to the collector).
QUERIES_MULTILINGUAL_ALL = [q for qs in QUERIES_MULTILINGUAL.values() for q in qs]

# Convenience bundles ─────────────────────────────────────────────────────────

# Full English run (QDA-first, then broader qualitative).
ALL_QUERIES_EN = QUERIES_QDA + QUERIES_QUAL_EN

# Complete run including all languages.
ALL_QUERIES = QUERIES_QDA + QUERIES_QUAL_EN + QUERIES_MULTILINGUAL_ALL
