# ISIC Rev. 5 taxonomy — verbatim from the notebook cell 404f4653
# 22 sections (A-V), 87 divisions

ISIC_REV5: dict[str, dict] = {
    'A': {'title': 'Agriculture, forestry and fishing',
          'divisions': {
              '01': 'Crop and animal production, hunting and related service activities',
              '02': 'Forestry and logging',
              '03': 'Fishing and aquaculture',
          }},
    'B': {'title': 'Mining and quarrying',
          'divisions': {
              '05': 'Mining of coal and lignite',
              '06': 'Extraction of crude petroleum and natural gas',
              '07': 'Mining of metal ores',
              '08': 'Other mining and quarrying',
              '09': 'Mining support service activities',
          }},
    'C': {'title': 'Manufacturing',
          'divisions': {
              '10': 'Manufacture of food products',
              '11': 'Manufacture of beverages',
              '12': 'Manufacture of tobacco products',
              '13': 'Manufacture of textiles',
              '14': 'Manufacture of wearing apparel',
              '15': 'Manufacture of leather and related products',
              '16': 'Manufacture of wood and of products of wood and cork, except furniture; manufacture of articles of straw and plaiting materials',
              '17': 'Manufacture of paper and paper products',
              '18': 'Printing and reproduction of recorded media',
              '19': 'Manufacture of coke and refined petroleum products',
              '20': 'Manufacture of chemicals and chemical products',
              '21': 'Manufacture of basic pharmaceutical products and pharmaceutical preparations',
              '22': 'Manufacture of rubber and plastic products',
              '23': 'Manufacture of other non-metallic mineral products',
              '24': 'Manufacture of basic metals',
              '25': 'Manufacture of fabricated metal products, except machinery and equipment',
              '26': 'Manufacture of computer, electronic and optical products',
              '27': 'Manufacture of electrical equipment',
              '28': 'Manufacture of machinery and equipment n.e.c.',
              '29': 'Manufacture of motor vehicles, trailers and semi-trailers',
              '30': 'Manufacture of other transport equipment',
              '31': 'Manufacture of furniture',
              '32': 'Other manufacturing',
              '33': 'Repair, maintenance and installation of machinery and equipment',
          }},
    'D': {'title': 'Electricity, gas, steam and air conditioning supply',
          'divisions': {
              '35': 'Electricity, gas, steam and air conditioning supply',
          }},
    'E': {'title': 'Water supply; sewerage, waste management and remediation activities',
          'divisions': {
              '36': 'Water collection, treatment and supply',
              '37': 'Sewerage',
              '38': 'Waste collection, treatment and disposal, and recovery activities',
              '39': 'Remediation and other waste management service activities',
          }},
    'F': {'title': 'Construction',
          'divisions': {
              '41': 'Construction of residential and non-residential buildings',
              '42': 'Civil engineering',
              '43': 'Specialized construction activities',
          }},
    'G': {'title': 'Wholesale and retail trade',
          'divisions': {
              '46': 'Wholesale trade',
              '47': 'Retail trade',
          }},
    'H': {'title': 'Transportation and storage',
          'divisions': {
              '49': 'Land transport and transport via pipelines',
              '50': 'Water transport',
              '51': 'Air transport',
              '52': 'Warehousing and support activities for transportation',
              '53': 'Postal and courier activities',
          }},
    'I': {'title': 'Accommodation and food service activities',
          'divisions': {
              '55': 'Accommodation',
              '56': 'Food and beverage service activities',
          }},
    'J': {'title': 'Publishing, broadcasting, and content production and distribution activities',
          'divisions': {
              '58': 'Publishing activities',
              '59': 'Motion picture, video and television programme production, sound recording and music publishing activities',
              '60': 'Programming, broadcasting, news agency and other content distribution activities',
          }},
    'K': {'title': 'Telecommunications, computer programming, consultancy, computing infrastructure, and other information service activities',
          'divisions': {
              '61': 'Telecommunications',
              '62': 'Computer programming, consultancy and related activities',
              '63': 'Computing infrastructure, data processing, hosting, and other information service activities',
          }},
    'L': {'title': 'Financial and insurance activities',
          'divisions': {
              '64': 'Financial service activities, except insurance and pension funding',
              '65': 'Insurance, reinsurance and pension funding, except compulsory social security',
              '66': 'Activities auxiliary to financial service and insurance activities',
          }},
    'M': {'title': 'Real estate activities',
          'divisions': {
              '68': 'Real estate activities',
          }},
    'N': {'title': 'Professional, scientific and technical activities',
          'divisions': {
              '69': 'Legal and accounting activities',
              '70': 'Activities of head offices; management consultancy activities',
              '71': 'Architectural and engineering activities; technical testing and analysis',
              '72': 'Scientific research and development',
              '73': 'Activities of advertising, market research and public relations',
              '74': 'Other professional, scientific and technical activities',
              '75': 'Veterinary activities',
          }},
    'O': {'title': 'Administrative and support service activities',
          'divisions': {
              '77': 'Rental and leasing activities',
              '78': 'Employment activities',
              '79': 'Travel agency, tour operator, and other travel related activities',
              '80': 'Investigation and security activities',
              '81': 'Services to buildings and landscape activities',
              '82': 'Office administrative, office support and other business support activities',
          }},
    'P': {'title': 'Public administration and defence; compulsory social security',
          'divisions': {
              '84': 'Public administration and defence; compulsory social security',
          }},
    'Q': {'title': 'Education',
          'divisions': {
              '85': 'Education',
          }},
    'R': {'title': 'Human health and social work activities',
          'divisions': {
              '86': 'Human health activities',
              '87': 'Residential care activities',
              '88': 'Social work activities without accommodation',
          }},
    'S': {'title': 'Arts, sports and recreation',
          'divisions': {
              '90': 'Arts creation and performing arts activities',
              '91': 'Library, archives, museum and other cultural activities',
              '92': 'Gambling and betting activities',
              '93': 'Sports activities and amusement and recreation activities',
          }},
    'T': {'title': 'Other service activities',
          'divisions': {
              '94': 'Activities of membership organizations',
              '95': 'Repair and maintenance of computers, personal and household goods, and motor vehicles and motorcycles',
              '96': 'Personal service activities',
          }},
    'U': {'title': 'Activities of households as employers; undifferentiated goods- and services-producing activities of households for own use',
          'divisions': {
              '97': 'Activities of households as employers of domestic personnel',
              '98': 'Undifferentiated goods- and services-producing activities of private households for own use',
          }},
    'V': {'title': 'Activities of extraterritorial organizations and bodies',
          'divisions': {
              '99': 'Activities of extraterritorial organizations and bodies',
          }},
}

# Extra vocabulary appended to section embeddings at classify time ONLY.
# These phrases never appear in reports or DB — they only steer the cosine scorer.
# Populated based on observed misclassification patterns across 110 test projects.
ISIC_EMBED_EXTRAS: dict[str, str] = {
    # POLICY — domain-first. The label must answer "what is this research ABOUT",
    # not "what activity produced it". Under a literal reading of ISIC every
    # academic dataset is N/72 (R&D), which makes the label worthless, so:
    #
    #   * Section N carries ONLY R&D-as-an-economic-activity and meta-research
    #     vocabulary (research about research: data management, CAQDAS tooling).
    #   * Subject vocabulary lives in the section that owns the SUBJECT — crop
    #     genomics in A, pharmacology in R, and so on.
    #   * Research METHOD vocabulary ("thematic analysis", "cohort study",
    #     "semi-structured interviews") belongs nowhere. Every study has a
    #     method; method terms in any section make it a magnet.
    #
    # Do NOT re-add domain nouns to N to "fix" a single project — that is how N
    # became a dumping ground for 52% of the corpus. If a project has no honest
    # domain section, it SHOULD fall back to N with low confidence and be
    # flagged for review. See is_meta_research() and ISICEmbedder.classify(demote=).
    "N": (
        "research and experimental development services; contract research organisation; "
        "research institute; commissioned R&D; scientific research services; "
        "laboratory testing services; technical testing and analysis; "
        # Meta-research: projects genuinely ABOUT the practice of research. These
        # are the legitimate N/72 cases and must keep winning the section.
        "research data management; research data infrastructure; FAIR data principles; "
        "open science practice; data sharing and reuse; research reproducibility; "
        "qualitative coding tool; qualitative analysis software; "
        "computer-assisted qualitative data analysis; CAQDAS; "
        "codebook development; research software tooling"
    ),
    # H keeps matching pharmacological 'transporters' and virological 'airborne
    # transmission'. Anchor it firmly to the physical transport industry.
    "H": (
        "airline; aviation; freight; cargo logistics; shipping; maritime; "
        "railway; road transport; trucking; fleet management; courier; "
        "delivery service; air traffic control; port operations; warehouse; "
        "supply chain logistics; vehicle routing; transport network"
    ),
    # A owns living-organism subjects: crops, livestock, forests, fisheries —
    # INCLUDING the molecular/genomic research done on them (plant genomics is
    # about plants). Production vocabulary keeps it anchored to the sector.
    "A": (
        "farming; crop production; soil management; irrigation system; harvesting; "
        "livestock breeding; cattle ranching; poultry farming; aquaculture farm; "
        "fish farming; deforestation; timber production; agricultural yield; "
        "pesticide application; fertilizer use; land cultivation; agroforestry; "
        "food production; rural agriculture; field crop; grain production; "
        "animal husbandry; farm management; agricultural land; orchard; "
        "nursery production; crop rotation; seed variety; planting season; "
        "tractor; irrigation canal; smallholder farmer; pasture; grazing land; "
        # Subjects: plant/animal/fisheries science belongs to the sector it studies.
        "plant genomics; plant science; crop science; plant breeding; "
        "genomic selection; genomic prediction; quantitative trait loci; "
        "GWAS in crops; transgenic plant; plant biotechnology; plant physiology; "
        "seed genetics; crop yield trait; agronomy; horticulture; "
        "animal genomics; livestock genetics; fish stock; fisheries; "
        "forest ecology; tree species; wildlife population; soil microbiome"
    ),
    # V/99 fires on any qualitative research with international/humanitarian/
    # multicountry framing. Anchor hard to the actual institutions and their
    # operational activities — not research ABOUT international topics.
    "V": (
        "United Nations secretariat; UNICEF operations; UNESCO programmes; "
        "UNHCR refugee agency; ILO labour standards; WHO Geneva headquarters; "
        "World Bank lending; IMF structural adjustment; OECD secretariat; "
        "NATO alliance operations; G7 summit communiqué; G20 declaration; "
        "embassy visa section; consulate services; ambassador posting; "
        "foreign service officer; diplomatic staff; consular fees; "
        "diplomatic immunity; extraterritorial jurisdiction; "
        "peacekeeping troops; Security Council resolution; "
        "General Assembly vote; treaty body; bilateral agreement; "
        "foreign ministry; state department; intergovernmental secretariat; "
        "multilateral fund; international civil servant; UN mandate"
    ),
    # K: the IT/telecoms industry, plus AI/ML as a subject in its own right.
    # No QDA tool names — those are meta-research and belong to N.
    "K": (
        "software development; app development; programming language; source code; "
        "IT infrastructure; cloud computing; cybersecurity; broadband network; "
        "wireless telecommunications; mobile operator; data centre; "
        "internet service provider; SaaS; DevOps; API development; "
        "computer systems; network protocol; software engineering; "
        "system architecture; database management; IT service; "
        "machine learning deployment; MLOps; federated learning system; "
        "machine learning model; deep learning; neural network; "
        "large language model; generative AI; computer vision; algorithm design"
    ),
    # R owns human health and social care as SUBJECTS — which is where biomedical,
    # clinical and pharmacological research belongs (a study of drug transporters
    # is about health, not about "doing research"). The transporter vocabulary
    # lives here, not in N and not in H (which reads it as freight).
    "R": (
        "patient care; hospital; clinic; nursing; physician; medical treatment; "
        "public health; mental health; psychiatric care; wellbeing; "
        "social work; social care; caregiving; residential care home; "
        "disability support; child welfare; elderly care; "
        # Biomedical / clinical subjects
        "clinical medicine; disease; diagnosis; therapy; drug treatment; "
        "epidemiology; immunology; neuroscience; pharmacology; toxicology; "
        "molecular biology; gene expression; cell biology; biochemistry; "
        "genomics; transcriptomics; proteomics; metabolomics; bioinformatics; "
        "DNA sequencing; CRISPR; molecular cloning; synthetic biology; "
        "microbiome; pathogen; infection; vaccine; "
        "pharmacokinetics; drug transport; drug disposition; transporter protein; "
        "membrane transport; organic anion transporter; solute carrier; "
        "ion channel; efflux pump; endogenous metabolite"
    ),
    # E owns water, waste and the environment as SUBJECTS: ecology, climate,
    # marine and pollution research describe the environment being studied.
    "E": (
        "water supply; water treatment; drinking water quality; sewerage; "
        "wastewater; sanitation; waste collection; recycling; landfill; "
        "pollution control; site remediation; contaminated land; "
        # Environmental subjects
        "ecology; ecosystem; biodiversity; species abundance; food web; "
        "marine ecosystem; ocean; oceanography; freshwater; lake; river basin; "
        "climate change; climate data; atmospheric science; "
        "environmental monitoring; environmental contamination; "
        "microplastics; nanoplastics; pollutant; emissions; "
        "sustainability; conservation; habitat"
    ),
    # Q owns education as a subject: teaching, learners, curriculum, pedagogy.
    "Q": (
        "school; classroom; teaching; teacher; pupil; student; learner; "
        "curriculum; pedagogy; lesson; instruction; learning outcome; "
        "higher education; university; undergraduate; academic staff; "
        "vocational training; educational attainment; literacy; "
        "preservice teacher; teacher education; educational assessment"
    ),
    # P owns government, policy and public administration as subjects.
    "P": (
        "public administration; government policy; public sector; regulation; "
        "policy implementation; legislation; ministry; civil service; "
        "governance; public service delivery; state institution; "
        "defence; national security; border control; migration policy; "
        "asylum policy; public consultation"
    ),
    # L is often missed for genuine financial datasets (KGP pawnshop collateral
    # was going to G/47). Enrich with financial services vocabulary.
    "L": (
        "banking; investment fund; insurance policy; pension fund; "
        "securities trading; financial markets; credit; loans; assets; "
        "equity; bond; fintech; collateral; liquidity; risk management; "
        "asset management; pawn; lending; mortgage; hedge fund"
    ),
    # G keeps attracting non-commercial datasets. Anchor to actual commerce.
    "G": (
        "retail store; consumer goods; merchandise; wholesale distribution; "
        "e-commerce; sales volume; buyer; seller; market price; "
        "trade transaction; inventory; point of sale; supermarket; "
        "product catalogue; supply chain commerce"
    ),
    # O false-positived on emergency obstetric referrals. Anchor to office/admin.
    "O": (
        "office administration; business support services; payroll processing; "
        "scheduling; travel booking agency; document management; "
        "security guard; facility cleaning; call centre; outsourcing; "
        "administrative staffing; secretarial services"
    ),
}

# Division-level vocabulary extras — appended to division title embeddings only.
# Fixes division-level misses WITHIN a correctly-identified section.
# Key problem: N/72 (R&D) was losing to N/70 (management consultancy) for
# toxicology/synthesis/clinical datasets because plain ISIC titles are too generic.
ISIC_DIV_EXTRAS: dict[str, str] = {
    # N/72 — Scientific research and development
    "72": (
        "laboratory experiment; biochemical analysis; toxicological study; "
        "drug synthesis; genomic study; clinical research; epidemiological study; "
        "field experiment; computational modelling; basic research; applied research; "
        "research protocol; experimental design; scientific methodology; "
        "data collection instrument; study cohort; sample analysis"
    ),
    # N/70 — Management consultancy (anchor away from research)
    "70": (
        "corporate strategy; management advice; business consulting; "
        "organisational restructuring; executive leadership; "
        "holding company; headquarters operations; strategic planning"
    ),
    # N/75 — Veterinary (anchor away from virology/biology research on animals)
    "75": (
        "animal clinic; veterinary practice; livestock treatment; "
        "pet healthcare; animal surgery; veterinary diagnosis; "
        "companion animal; farm animal medicine"
    ),
}

# Build a flat set of all valid division codes for fast lookup
_ALL_DIVISIONS: dict[str, str] = {}  # division_code -> section_letter
for _sec, _data in ISIC_REV5.items():
    for _div in _data['divisions']:
        _ALL_DIVISIONS[_div] = _sec


# Section N may not win the primary label merely because the data came from a
# study: under a literal reading of ISIC every academic dataset is N/72
# "Scientific research and development", which says nothing about the subject.
# The embedder demotes it in favour of the domain the research is ABOUT, but
# lets it stand when the text has no domain subject at all (a methodology or
# research-data paper) — see ISICEmbedder.classify and N_KEEP_MARGIN.
#
# A keyword test for "meta-research" was tried here and removed: it fired on any
# summary that merely mentioned its method ("design-based research methodology")
# while missing real meta-research ("Qualitative Research Using Open Tools").
# The cosine margin separates the two cleanly; keywords do not.
DEMOTED_SECTION = "N"


def get_section_titles() -> list[tuple[str, str]]:
    return [(sec, data['title']) for sec, data in ISIC_REV5.items()]


def get_division_titles(section: str) -> list[tuple[str, str]]:
    if section not in ISIC_REV5:
        return []
    return list(ISIC_REV5[section]['divisions'].items())


def get_all_division_titles() -> list[tuple[str, str, str]]:
    result = []
    for sec, data in ISIC_REV5.items():
        for div, title in data['divisions'].items():
            result.append((sec, div, title))
    return result


def dim_isic_rows() -> list[tuple[str, str, str, str, str]]:
    """Rows for the dim_isic dimension table:
    (class, section, division, section_title, division_title) for all divisions.
    ``class`` is the "N/72" join key used by projects/files/classifications."""
    rows = []
    for sec, data in ISIC_REV5.items():
        sec_title = data['title']
        for div, div_title in data['divisions'].items():
            rows.append((f"{sec}/{div}", sec, div, sec_title, div_title))
    return rows


def canonical_division_title(section: str, division: str) -> str | None:
    if section not in ISIC_REV5:
        return None
    return ISIC_REV5[section]['divisions'].get(division)


def is_valid_code(section: str, division: str) -> bool:
    return section in ISIC_REV5 and division in ISIC_REV5[section]['divisions']


def division_to_section(division: str) -> str | None:
    return _ALL_DIVISIONS.get(division)
