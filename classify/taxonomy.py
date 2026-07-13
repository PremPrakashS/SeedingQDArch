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
    # N/72 is the most under-predicted section. Almost all pure research datasets
    # (biomedical, genomics, social science, environmental) belong here but lose to
    # domain-specific vocabulary in A, H, C, K, V.
    "N": (
        "laboratory experiment; in vivo study; in vitro study; clinical trial; "
        "randomized controlled trial; cohort study; longitudinal study; "
        "cross-sectional study; observational study; mixed-methods study; "
        "systematic review; meta-analysis; field study; experimental data; "
        "genomics; transcriptomics; proteomics; metabolomics; metatranscriptomics; "
        "bioinformatics; DNA sequencing; gene expression; molecular biology; "
        "biochemistry; cell biology; immunology; neuroscience; pharmacology; "
        "toxicology; epidemiology; ecology; palaeontology; oceanography; "
        "atmospheric science; materials science; nanotechnology; nanoplastics; "
        "thematic analysis; grounded theory; qualitative research; "
        "qualitative data analysis; semi-structured interviews; focus groups; "
        "ethnographic study; discourse analysis; content analysis; "
        "survey research; interview study; phenomenological analysis; "
        "research dataset; scientific study; empirical research; "
        "research findings; study participants; data collection; "
        "remote sensing; satellite imagery; earth observation; "
        "machine learning model; deep learning; neural network; "
        "climate data; environmental monitoring; geospatial analysis; "
        "plant genomics; plant science research; genomic prediction; "
        "GWAS study; quantitative trait loci; gene regulatory network; "
        "multi-omics integration; omics data; metagenome; microbiome analysis; "
        "plant breeding research; genomic selection; crop science research; "
        "synthetic biology; plant biotechnology; rapamycin; CRISPR; "
        "molecular cloning; transgenic plant; gene expression regulation; "
        "ecological economics; environmental economics; sustainability research; "
        "national accounting; ecological GDP; green economy research; "
        "diaspora study; humanitarian research; migration study; "
        "refugee research; indigenous peoples study; postcolonial analysis; "
        "reconciliation research; truth commission analysis; "
        "political discourse analysis; governance research; "
        "multi-country study; cross-national survey; global health research; "
        "international comparative research; post-conflict research; "
        "immigrant community research; multicultural community study; "
        "export promotion research; labour relations research; "
        "psychometric validation; questionnaire validation; scale reliability; "
        "measurement invariance; participant survey; validity evidence; "
        "urban soundscape; acoustic ecology; perceptual study; "
        "sensory environment research; sound environment; "
        # Fix 1: Generic qualitative research tool vocabulary (no product names)
        # anchors datasets that use coding/analysis software toward N, not K.
        "qualitative coding tool; qualitative analysis software; "
        "computer-assisted qualitative analysis; research data management; "
        "coding scheme; codebook; interview transcript coding; "
        # Fix 2: Transporter protein vocab moved here from H so pharmacology
        # datasets score N/72, not H/51 Air transport.
        "transporter protein; membrane transport; drug transport; "
        "pharmacokinetics; organic anion transporter; solute carrier; "
        "ion channel; efflux pump; uptake transporter; drug disposition; "
        "OAT; OATP; SLC22; SLCO; endogenous metabolite"
    ),
    # H keeps matching pharmacological 'transporters' and virological 'airborne
    # transmission'. Anchor it firmly to the physical transport industry.
    "H": (
        "airline; aviation; freight; cargo logistics; shipping; maritime; "
        "railway; road transport; trucking; fleet management; courier; "
        "delivery service; air traffic control; port operations; warehouse; "
        "supply chain logistics; vehicle routing; transport network"
    ),
    # A wins for plant molecular biology and animal genomics because 'plant',
    # 'animal', 'fish' appear in research summaries. Anchor firmly to
    # agricultural/forestry production activities, not scientific research on them.
    "A": (
        "farming; crop production; soil management; irrigation system; harvesting; "
        "livestock breeding; cattle ranching; poultry farming; aquaculture farm; "
        "fish farming; deforestation; timber production; agricultural yield; "
        "pesticide application; fertilizer use; land cultivation; agroforestry; "
        "food production; rural agriculture; field crop; grain production; "
        "animal husbandry; farm management; agricultural land; orchard; "
        "nursery production; crop rotation; seed variety; planting season; "
        "tractor; irrigation canal; smallholder farmer; pasture; grazing land"
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
    # K: anchor to actual IT/telecoms industry only. No QDA tool names.
    "K": (
        "software development; app development; programming language; source code; "
        "IT infrastructure; cloud computing; cybersecurity; broadband network; "
        "wireless telecommunications; mobile operator; data centre; "
        "internet service provider; SaaS; DevOps; API development; "
        "computer systems; network protocol; software engineering; "
        "system architecture; database management; IT service; "
        "machine learning deployment; MLOps; federated learning system"
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
