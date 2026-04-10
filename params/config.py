ZENODO_API = "https://zenodo.org/api/records"
DRYAD_API = "https://datadryad.org/api/v2"

# Open licenses that QDArchive accepts.
# Match is done with startswith() so "cc-by-4.0" matches the "cc-by" prefix.
OPEN_LICENSE_PREFIXES = {
    "cc-by",
    "cc0",
    "cc-zero",
    "odc-by",
    "pddl",
    "cc-pddc",
}

# Zenodo Lucene queries targeted at qualitative datasets.
# resource_type.type:dataset filters out papers/software.
ZENODO_QUERIES = [
    '"interview transcript" AND resource_type.type:dataset',
    '"focus group" AND resource_type.type:dataset',
    '"qualitative data" AND resource_type.type:dataset',
    '"thematic analysis" AND resource_type.type:dataset',
    '"grounded theory" AND resource_type.type:dataset',
    '"oral history" AND resource_type.type:dataset',
    '"ethnographic" AND resource_type.type:dataset',
    '"field notes" AND resource_type.type:dataset',
    'qdpx OR nvpx OR atlproj OR mx22',
    'NVivo AND resource_type.type:dataset',
    '"ATLAS.ti" AND resource_type.type:dataset',
    'MAXQDA AND resource_type.type:dataset',
]

# Simpler keyword queries for repositories without Lucene support (e.g. Dryad).
GENERIC_QUERIES = [
    "interview transcript",
    "focus group qualitative",
    "qualitative data",
    "oral history",
    "ethnographic",
    "NVivo",
    "ATLAS.ti",
    "MAXQDA",
    "qdpx",
]
