"""
Mock seed data for SmartVoter Phase 1.
5 parties, 20 policy items, 40 questions, 10 persons, party lineage examples.
"""
import uuid
import datetime

# ─── Fixed UUIDs for reproducible seeding ────────────────────────────────────

# Political Brands
BRAND_LIKUD = uuid.UUID("10000000-0000-0000-0000-000000000001")
BRAND_LABOR = uuid.UUID("10000000-0000-0000-0000-000000000002")
BRAND_UTJ = uuid.UUID("10000000-0000-0000-0000-000000000003")
BRAND_YESH_ATID = uuid.UUID("10000000-0000-0000-0000-000000000004")
BRAND_NEW_HOPE = uuid.UUID("10000000-0000-0000-0000-000000000005")  # new party, limited history

# Party Instances (Knesset 25)
PARTY_LIKUD = uuid.UUID("20000000-0000-0000-0000-000000000001")
PARTY_LABOR = uuid.UUID("20000000-0000-0000-0000-000000000002")
PARTY_UTJ = uuid.UUID("20000000-0000-0000-0000-000000000003")
PARTY_YESH_ATID = uuid.UUID("20000000-0000-0000-0000-000000000004")
PARTY_NEW_HOPE = uuid.UUID("20000000-0000-0000-0000-000000000005")  # new party

# Predecessor party instance for lineage examples
PARTY_KADIMA_OLD = uuid.UUID("20000000-0000-0000-0000-000000000010")  # dissolved

# Topics
TOPIC_JUDICIARY = uuid.UUID("30000000-0000-0000-0000-000000000001")
TOPIC_ECONOMY = uuid.UUID("30000000-0000-0000-0000-000000000002")
TOPIC_RELIGION_STATE = uuid.UUID("30000000-0000-0000-0000-000000000003")
TOPIC_SECURITY = uuid.UUID("30000000-0000-0000-0000-000000000004")
TOPIC_CIVIL_RIGHTS = uuid.UUID("30000000-0000-0000-0000-000000000005")

# Persons
PERSON_IDS = [uuid.UUID(f"40000000-0000-0000-0000-{i:012d}") for i in range(1, 11)]

POLITICAL_BRANDS = [
    {
        "id": BRAND_LIKUD,
        "canonical_name": "Likud",
        "names_json": {"he": "הליכוד", "en": "Likud"},
        "description": "Right-wing nationalist party founded by Menachem Begin.",
    },
    {
        "id": BRAND_LABOR,
        "canonical_name": "Labor",
        "names_json": {"he": "העבודה", "en": "Labor"},
        "description": "Center-left social-democratic party.",
    },
    {
        "id": BRAND_UTJ,
        "canonical_name": "United Torah Judaism",
        "names_json": {"he": "יהדות התורה", "en": "United Torah Judaism"},
        "description": "Ultra-Orthodox Haredi political alliance.",
    },
    {
        "id": BRAND_YESH_ATID,
        "canonical_name": "Yesh Atid",
        "names_json": {"he": "יש עתיד", "en": "Yesh Atid"},
        "description": "Centrist secular party focused on middle class.",
    },
    {
        "id": BRAND_NEW_HOPE,
        "canonical_name": "New Hope",
        "names_json": {"he": "תקווה חדשה", "en": "New Hope"},
        "description": "Recently formed right-wing party with limited parliamentary history.",
    },
]

PARTY_INSTANCES = [
    {
        "id": PARTY_LIKUD,
        "political_brand_id": BRAND_LIKUD,
        "official_name": "Likud",
        "election_cycle": "2022",
        "knesset_number": 25,
        "start_date": datetime.date(2022, 11, 1),
        "end_date": None,
        "status": "active",
    },
    {
        "id": PARTY_LABOR,
        "political_brand_id": BRAND_LABOR,
        "official_name": "HaAvoda",
        "election_cycle": "2022",
        "knesset_number": 25,
        "start_date": datetime.date(2022, 11, 1),
        "end_date": None,
        "status": "active",
    },
    {
        "id": PARTY_UTJ,
        "political_brand_id": BRAND_UTJ,
        "official_name": "Yahadut HaTorah",
        "election_cycle": "2022",
        "knesset_number": 25,
        "start_date": datetime.date(2022, 11, 1),
        "end_date": None,
        "status": "active",
    },
    {
        "id": PARTY_YESH_ATID,
        "political_brand_id": BRAND_YESH_ATID,
        "official_name": "Yesh Atid",
        "election_cycle": "2022",
        "knesset_number": 25,
        "start_date": datetime.date(2022, 11, 1),
        "end_date": None,
        "status": "active",
    },
    {
        "id": PARTY_NEW_HOPE,
        "political_brand_id": BRAND_NEW_HOPE,
        "official_name": "Tikva Hadasha",
        "election_cycle": "2022",
        "knesset_number": 25,
        "start_date": datetime.date(2022, 11, 1),
        "end_date": None,
        "status": "active",
    },
    # Dissolved predecessor for lineage demo
    {
        "id": PARTY_KADIMA_OLD,
        "political_brand_id": BRAND_LIKUD,
        "official_name": "Kadima (19th Knesset)",
        "election_cycle": "2013",
        "knesset_number": 19,
        "start_date": datetime.date(2013, 1, 1),
        "end_date": datetime.date(2015, 3, 17),
        "status": "dissolved",
    },
]

LINEAGE_EDGES = [
    # Rename: Kadima → absorbed (split → successor to Likud)
    {
        "from_party_instance_id": PARTY_KADIMA_OLD,
        "to_party_instance_id": PARTY_LIKUD,
        "relation_type": "successor",
        "continuity_weight": 0.35,
        "llm_explanation": "Some Kadima MKs joined Likud following dissolution.",
        "human_review_status": "approved",
    },
    # Alliance: Labor ↔ Yesh Atid (historical cooperation)
    {
        "from_party_instance_id": PARTY_LABOR,
        "to_party_instance_id": PARTY_YESH_ATID,
        "relation_type": "alliance",
        "continuity_weight": 0.20,
        "llm_explanation": "Both parties formed opposition bloc in 25th Knesset.",
        "human_review_status": "approved",
    },
    # Split example: New Hope split from mainstream right
    {
        "from_party_instance_id": PARTY_LIKUD,
        "to_party_instance_id": PARTY_NEW_HOPE,
        "relation_type": "split",
        "continuity_weight": 0.30,
        "llm_explanation": "New Hope was founded by former Likud members who left over leadership disputes.",
        "human_review_status": "approved",
    },
]

TOPICS = [
    {"id": TOPIC_JUDICIARY, "slug": "judiciary", "name_he": "מערכת המשפט", "name_en": "Judiciary", "name_ru": "Судебная власть", "description": "Judicial review, Supreme Court, legal reform."},
    {"id": TOPIC_ECONOMY, "slug": "economy_taxes", "name_he": "כלכלה ומיסים", "name_en": "Economy & Taxes", "name_ru": "Экономика и налоги", "description": "Tax policy, social spending, economic regulation."},
    {"id": TOPIC_RELIGION_STATE, "slug": "religion_state", "name_he": "דת ומדינה", "name_en": "Religion & State", "name_ru": "Религия и государство", "description": "Separation of religion and state, religious law, civil marriage."},
    {"id": TOPIC_SECURITY, "slug": "security", "name_he": "ביטחון", "name_en": "Security", "name_ru": "Безопасность", "description": "Defense policy, military, settlements, peace negotiations."},
    {"id": TOPIC_CIVIL_RIGHTS, "slug": "civil_rights", "name_he": "זכויות אזרח", "name_en": "Civil Rights", "name_ru": "Гражданские права", "description": "Individual freedoms, minority rights, LGBTQ+, discrimination law."},
]

# 20 policy items: 4 per topic
POLICY_ITEMS = [
    # Judiciary (4)
    {"slug": "jud_01", "topic_id": TOPIC_JUDICIARY, "title": "Judicial Review Scope", "description": "Extent of Supreme Court authority to strike down Knesset laws.", "directional_axis": "judicial_review_scope: -1=broad court power, +1=parliamentary supremacy", "source_type": "vote"},
    {"slug": "jud_02", "topic_id": TOPIC_JUDICIARY, "title": "Judicial Appointments", "description": "Who controls appointment of Supreme Court justices.", "directional_axis": "appointment_control: -1=judicial committee control, +1=political appointment", "source_type": "bill"},
    {"slug": "jud_03", "topic_id": TOPIC_JUDICIARY, "title": "Override Clause", "description": "Ability of Knesset to override Supreme Court rulings.", "directional_axis": "override: -1=no override, +1=simple majority override", "source_type": "vote"},
    {"slug": "jud_04", "topic_id": TOPIC_JUDICIARY, "title": "Attorney General Independence", "description": "Independence of the Attorney General from government.", "directional_axis": "ag_independence: -1=full independence, +1=politically subordinate", "source_type": "platform"},
    # Economy (4)
    {"slug": "eco_01", "topic_id": TOPIC_ECONOMY, "title": "Income Tax Progressivity", "description": "Whether top income tax brackets should be raised.", "directional_axis": "tax_progressivity: -1=higher top rates, +1=flat/lower rates", "source_type": "vote"},
    {"slug": "eco_02", "topic_id": TOPIC_ECONOMY, "title": "State Welfare Spending", "description": "Level of state social safety net and welfare benefits.", "directional_axis": "welfare_spending: -1=expand welfare, +1=reduce welfare/privatize", "source_type": "bill"},
    {"slug": "eco_03", "topic_id": TOPIC_ECONOMY, "title": "Housing Market Regulation", "description": "Government intervention in housing prices and rental market.", "directional_axis": "housing_regulation: -1=strong state regulation, +1=free market", "source_type": "vote"},
    {"slug": "eco_04", "topic_id": TOPIC_ECONOMY, "title": "Religious Institution Funding", "description": "State budget allocation to religious institutions.", "directional_axis": "religious_funding: -1=cut funding, +1=increase funding", "source_type": "vote"},
    # Religion & State (4)
    {"slug": "rel_01", "topic_id": TOPIC_RELIGION_STATE, "title": "Civil Marriage", "description": "Whether civil (non-religious) marriage should be legalized.", "directional_axis": "civil_marriage: -1=legalize civil marriage, +1=maintain religious monopoly", "source_type": "bill"},
    {"slug": "rel_02", "topic_id": TOPIC_RELIGION_STATE, "title": "Shabbat Commerce", "description": "Whether businesses may operate on Shabbat.", "directional_axis": "shabbat_commerce: -1=allow commerce, +1=restrict commerce", "source_type": "vote"},
    {"slug": "rel_03", "topic_id": TOPIC_RELIGION_STATE, "title": "Haredi Military Service", "description": "Whether Haredi men should serve in the military.", "directional_axis": "haredi_service: -1=mandatory service, +1=exempt status", "source_type": "vote"},
    {"slug": "rel_04", "topic_id": TOPIC_RELIGION_STATE, "title": "Kashrut Law", "description": "State enforcement of kashrut (kosher) rules.", "directional_axis": "kashrut_enforcement: -1=privatize kashrut, +1=state monopoly enforcement", "source_type": "platform"},
    # Security (4)
    {"slug": "sec_01", "topic_id": TOPIC_SECURITY, "title": "Two-State Solution", "description": "Support for Palestinian statehood alongside Israel.", "directional_axis": "two_state: -1=support two states, +1=oppose Palestinian statehood", "source_type": "platform"},
    {"slug": "sec_02", "topic_id": TOPIC_SECURITY, "title": "Settlement Expansion", "description": "Policy on West Bank settlement building.", "directional_axis": "settlements: -1=freeze/remove settlements, +1=expand settlements", "source_type": "vote"},
    {"slug": "sec_03", "topic_id": TOPIC_SECURITY, "title": "Defense Budget", "description": "Level of military and defense spending.", "directional_axis": "defense_spending: -1=reduce, +1=increase significantly", "source_type": "bill"},
    {"slug": "sec_04", "topic_id": TOPIC_SECURITY, "title": "Gaza Ceasefire Terms", "description": "Conditions acceptable for Gaza ceasefire agreement.", "directional_axis": "ceasefire_terms: -1=flexible humanitarian terms, +1=military victory first", "source_type": "statement"},
    # Civil Rights (4)
    {"slug": "civ_01", "topic_id": TOPIC_CIVIL_RIGHTS, "title": "LGBTQ+ Rights", "description": "Legal equality and recognition of LGBTQ+ persons.", "directional_axis": "lgbtq_rights: -1=full equality, +1=restrict recognition", "source_type": "vote"},
    {"slug": "civ_02", "topic_id": TOPIC_CIVIL_RIGHTS, "title": "Arab Minority Rights", "description": "Language rights, political participation, budget parity for Arab citizens.", "directional_axis": "arab_rights: -1=full equality and recognition, +1=restrict political participation", "source_type": "bill"},
    {"slug": "civ_03", "topic_id": TOPIC_CIVIL_RIGHTS, "title": "Freedom of Press", "description": "Independence of public broadcasting and press freedom.", "directional_axis": "press_freedom: -1=strong independent media, +1=government control/influence", "source_type": "vote"},
    {"slug": "civ_04", "topic_id": TOPIC_CIVIL_RIGHTS, "title": "Anti-Discrimination Law", "description": "Scope of anti-discrimination protections in employment and services.", "directional_axis": "anti_discrimination: -1=broad protections, +1=narrow/religious exemptions", "source_type": "platform"},
]

# Party positions: position_mean values per (party × policy_item)
# Format: (party_id, policy_slug) → {position_mean, position_uncertainty, evidence_strength, evidence_type}
# -1 = left/liberal pole, +1 = right/conservative pole per axis direction above

PARTY_POSITIONS_RAW = {
    # LIKUD — right-wing, nationalist
    (PARTY_LIKUD, "jud_01"): (0.75, 0.15, 0.90, "vote"),
    (PARTY_LIKUD, "jud_02"): (0.65, 0.18, 0.85, "bill"),
    (PARTY_LIKUD, "jud_03"): (0.80, 0.12, 0.92, "vote"),
    (PARTY_LIKUD, "jud_04"): (0.60, 0.20, 0.80, "platform"),
    (PARTY_LIKUD, "eco_01"): (0.50, 0.15, 0.82, "vote"),
    (PARTY_LIKUD, "eco_02"): (0.45, 0.18, 0.78, "bill"),
    (PARTY_LIKUD, "eco_03"): (0.40, 0.20, 0.75, "vote"),
    (PARTY_LIKUD, "eco_04"): (0.55, 0.15, 0.80, "vote"),
    (PARTY_LIKUD, "rel_01"): (0.40, 0.20, 0.70, "vote"),
    (PARTY_LIKUD, "rel_02"): (0.30, 0.25, 0.68, "vote"),
    (PARTY_LIKUD, "rel_03"): (0.20, 0.22, 0.72, "vote"),
    (PARTY_LIKUD, "rel_04"): (0.35, 0.20, 0.65, "platform"),
    (PARTY_LIKUD, "sec_01"): (0.70, 0.15, 0.88, "platform"),
    (PARTY_LIKUD, "sec_02"): (0.75, 0.12, 0.90, "vote"),
    (PARTY_LIKUD, "sec_03"): (0.70, 0.15, 0.85, "bill"),
    (PARTY_LIKUD, "sec_04"): (0.65, 0.18, 0.82, "statement"),
    (PARTY_LIKUD, "civ_01"): (0.30, 0.25, 0.70, "vote"),
    (PARTY_LIKUD, "civ_02"): (0.45, 0.20, 0.75, "bill"),
    (PARTY_LIKUD, "civ_03"): (0.40, 0.25, 0.72, "vote"),
    (PARTY_LIKUD, "civ_04"): (0.35, 0.22, 0.68, "platform"),

    # LABOR — center-left
    (PARTY_LABOR, "jud_01"): (-0.75, 0.12, 0.88, "vote"),
    (PARTY_LABOR, "jud_02"): (-0.70, 0.15, 0.85, "bill"),
    (PARTY_LABOR, "jud_03"): (-0.80, 0.10, 0.90, "vote"),
    (PARTY_LABOR, "jud_04"): (-0.65, 0.18, 0.80, "platform"),
    (PARTY_LABOR, "eco_01"): (-0.60, 0.15, 0.85, "vote"),
    (PARTY_LABOR, "eco_02"): (-0.65, 0.12, 0.88, "bill"),
    (PARTY_LABOR, "eco_03"): (-0.55, 0.18, 0.80, "vote"),
    (PARTY_LABOR, "eco_04"): (-0.70, 0.15, 0.82, "vote"),
    (PARTY_LABOR, "rel_01"): (-0.80, 0.10, 0.85, "vote"),
    (PARTY_LABOR, "rel_02"): (-0.70, 0.15, 0.82, "vote"),
    (PARTY_LABOR, "rel_03"): (-0.75, 0.12, 0.85, "vote"),
    (PARTY_LABOR, "rel_04"): (-0.65, 0.18, 0.78, "platform"),
    (PARTY_LABOR, "sec_01"): (-0.60, 0.15, 0.85, "platform"),
    (PARTY_LABOR, "sec_02"): (-0.65, 0.12, 0.88, "vote"),
    (PARTY_LABOR, "sec_03"): (-0.20, 0.25, 0.75, "bill"),
    (PARTY_LABOR, "sec_04"): (-0.55, 0.18, 0.80, "statement"),
    (PARTY_LABOR, "civ_01"): (-0.85, 0.08, 0.92, "vote"),
    (PARTY_LABOR, "civ_02"): (-0.80, 0.10, 0.90, "bill"),
    (PARTY_LABOR, "civ_03"): (-0.75, 0.12, 0.88, "vote"),
    (PARTY_LABOR, "civ_04"): (-0.80, 0.10, 0.88, "platform"),

    # UTJ — ultra-Orthodox, socially conservative, economically populist
    (PARTY_UTJ, "jud_01"): (0.60, 0.18, 0.82, "vote"),
    (PARTY_UTJ, "jud_02"): (0.70, 0.15, 0.85, "bill"),
    (PARTY_UTJ, "jud_03"): (0.75, 0.12, 0.88, "vote"),
    (PARTY_UTJ, "jud_04"): (0.55, 0.20, 0.78, "platform"),
    (PARTY_UTJ, "eco_01"): (-0.10, 0.30, 0.65, "vote"),   # less consistent on economics
    (PARTY_UTJ, "eco_02"): (-0.20, 0.28, 0.68, "bill"),
    (PARTY_UTJ, "eco_03"): (0.10, 0.30, 0.60, "vote"),
    (PARTY_UTJ, "eco_04"): (0.90, 0.08, 0.95, "vote"),   # strongly supports religious funding
    (PARTY_UTJ, "rel_01"): (0.95, 0.05, 0.98, "vote"),   # strongly opposes civil marriage
    (PARTY_UTJ, "rel_02"): (0.90, 0.08, 0.95, "vote"),
    (PARTY_UTJ, "rel_03"): (0.95, 0.05, 0.98, "vote"),   # strongly opposes Haredi service
    (PARTY_UTJ, "rel_04"): (0.90, 0.08, 0.95, "platform"),
    (PARTY_UTJ, "sec_01"): (0.65, 0.18, 0.80, "platform"),
    (PARTY_UTJ, "sec_02"): (0.70, 0.15, 0.82, "vote"),
    (PARTY_UTJ, "sec_03"): (0.40, 0.25, 0.70, "bill"),
    (PARTY_UTJ, "sec_04"): (0.55, 0.22, 0.75, "statement"),
    (PARTY_UTJ, "civ_01"): (0.85, 0.10, 0.90, "vote"),   # strongly opposes LGBTQ+ rights
    (PARTY_UTJ, "civ_02"): (0.50, 0.22, 0.72, "bill"),
    (PARTY_UTJ, "civ_03"): (0.60, 0.20, 0.75, "vote"),
    (PARTY_UTJ, "civ_04"): (0.70, 0.15, 0.80, "platform"),

    # YESH ATID — centrist, secular, pro-reform
    (PARTY_YESH_ATID, "jud_01"): (-0.70, 0.12, 0.88, "vote"),
    (PARTY_YESH_ATID, "jud_02"): (-0.65, 0.15, 0.85, "bill"),
    (PARTY_YESH_ATID, "jud_03"): (-0.75, 0.10, 0.90, "vote"),
    (PARTY_YESH_ATID, "jud_04"): (-0.60, 0.18, 0.82, "platform"),
    (PARTY_YESH_ATID, "eco_01"): (-0.20, 0.20, 0.80, "vote"),   # moderate on economy
    (PARTY_YESH_ATID, "eco_02"): (-0.15, 0.22, 0.78, "bill"),
    (PARTY_YESH_ATID, "eco_03"): (-0.30, 0.20, 0.82, "vote"),
    (PARTY_YESH_ATID, "eco_04"): (-0.60, 0.15, 0.85, "vote"),
    (PARTY_YESH_ATID, "rel_01"): (-0.75, 0.12, 0.88, "vote"),
    (PARTY_YESH_ATID, "rel_02"): (-0.65, 0.15, 0.85, "vote"),
    (PARTY_YESH_ATID, "rel_03"): (-0.70, 0.12, 0.88, "vote"),
    (PARTY_YESH_ATID, "rel_04"): (-0.70, 0.15, 0.85, "platform"),
    (PARTY_YESH_ATID, "sec_01"): (-0.30, 0.20, 0.78, "platform"),
    (PARTY_YESH_ATID, "sec_02"): (-0.40, 0.18, 0.80, "vote"),
    (PARTY_YESH_ATID, "sec_03"): (0.10, 0.25, 0.72, "bill"),
    (PARTY_YESH_ATID, "sec_04"): (-0.25, 0.22, 0.75, "statement"),
    (PARTY_YESH_ATID, "civ_01"): (-0.70, 0.12, 0.88, "vote"),
    (PARTY_YESH_ATID, "civ_02"): (-0.65, 0.15, 0.85, "bill"),
    (PARTY_YESH_ATID, "civ_03"): (-0.70, 0.12, 0.88, "vote"),
    (PARTY_YESH_ATID, "civ_04"): (-0.65, 0.15, 0.85, "platform"),

    # NEW HOPE — new party, LOW evidence strength (demonstrates new-party scoring, AGENTS.MD Section 9)
    (PARTY_NEW_HOPE, "jud_01"): (0.50, 0.35, 0.30, "candidate_past_vote"),
    (PARTY_NEW_HOPE, "jud_02"): (0.45, 0.38, 0.28, "platform"),
    (PARTY_NEW_HOPE, "jud_03"): (0.55, 0.32, 0.32, "candidate_past_vote"),
    (PARTY_NEW_HOPE, "jud_04"): (0.40, 0.40, 0.25, "platform"),
    (PARTY_NEW_HOPE, "eco_01"): (0.30, 0.40, 0.25, "public_statement"),
    (PARTY_NEW_HOPE, "eco_02"): (0.25, 0.42, 0.22, "platform"),
    (PARTY_NEW_HOPE, "eco_03"): (0.20, 0.40, 0.25, "public_statement"),
    (PARTY_NEW_HOPE, "eco_04"): (0.30, 0.38, 0.28, "platform"),
    (PARTY_NEW_HOPE, "rel_01"): (0.10, 0.40, 0.22, "public_statement"),
    (PARTY_NEW_HOPE, "rel_02"): (0.05, 0.42, 0.20, "platform"),
    (PARTY_NEW_HOPE, "rel_03"): (-0.10, 0.40, 0.25, "candidate_past_vote"),
    (PARTY_NEW_HOPE, "rel_04"): (0.15, 0.40, 0.22, "platform"),
    (PARTY_NEW_HOPE, "sec_01"): (0.55, 0.35, 0.30, "platform"),
    (PARTY_NEW_HOPE, "sec_02"): (0.50, 0.38, 0.28, "public_statement"),
    (PARTY_NEW_HOPE, "sec_03"): (0.50, 0.35, 0.30, "candidate_past_vote"),
    (PARTY_NEW_HOPE, "sec_04"): (0.40, 0.40, 0.25, "public_statement"),
    (PARTY_NEW_HOPE, "civ_01"): (0.10, 0.42, 0.22, "public_statement"),
    (PARTY_NEW_HOPE, "civ_02"): (0.20, 0.40, 0.25, "platform"),
    (PARTY_NEW_HOPE, "civ_03"): (0.25, 0.40, 0.25, "public_statement"),
    (PARTY_NEW_HOPE, "civ_04"): (0.15, 0.42, 0.22, "platform"),
}

# Volatility scores
PARTY_VOLATILITY = {
    PARTY_LIKUD: 0.15,
    PARTY_LABOR: 0.10,
    PARTY_UTJ: 0.08,
    PARTY_YESH_ATID: 0.12,
    PARTY_NEW_HOPE: 0.55,  # high volatility — new party
}

PERSONS = [
    {"id": PERSON_IDS[0], "name_he": "בנימין נתניהו", "name_en": "Benjamin Netanyahu", "birth_year": 1949},
    {"id": PERSON_IDS[1], "name_he": "יצחק הרצוג", "name_en": "Itzhak Herzog", "birth_year": 1960},
    {"id": PERSON_IDS[2], "name_he": "יאיר לפיד", "name_en": "Yair Lapid", "birth_year": 1963},
    {"id": PERSON_IDS[3], "name_he": "משה גפני", "name_en": "Moshe Gafni", "birth_year": 1952},
    {"id": PERSON_IDS[4], "name_he": "גדעון סער", "name_en": "Gideon Sa'ar", "birth_year": 1966},
    {"id": PERSON_IDS[5], "name_he": "מרב מיכאלי", "name_en": "Merav Michaeli", "birth_year": 1975},
    {"id": PERSON_IDS[6], "name_he": "אילת שקד", "name_en": "Ayelet Shaked", "birth_year": 1976},
    {"id": PERSON_IDS[7], "name_he": "אמיר אוחנה", "name_en": "Amir Ohana", "birth_year": 1972},
    # Cross-party movers (demonstrate volatility)
    {"id": PERSON_IDS[8], "name_he": "ח''כ שינוי א", "name_en": "MK Changer A", "birth_year": 1970},
    {"id": PERSON_IDS[9], "name_he": "ח''כ שינוי ב", "name_en": "MK Changer B", "birth_year": 1968},
]

MEMBERSHIPS = [
    {"person_id": PERSON_IDS[0], "party_instance_id": PARTY_LIKUD, "role": "leader", "start_date": datetime.date(2022, 11, 1)},
    {"person_id": PERSON_IDS[1], "party_instance_id": PARTY_LABOR, "role": "mk", "start_date": datetime.date(2022, 11, 1)},
    {"person_id": PERSON_IDS[2], "party_instance_id": PARTY_YESH_ATID, "role": "leader", "start_date": datetime.date(2022, 11, 1)},
    {"person_id": PERSON_IDS[3], "party_instance_id": PARTY_UTJ, "role": "leader", "start_date": datetime.date(2022, 11, 1)},
    {"person_id": PERSON_IDS[4], "party_instance_id": PARTY_NEW_HOPE, "role": "leader", "start_date": datetime.date(2022, 11, 1)},
    {"person_id": PERSON_IDS[5], "party_instance_id": PARTY_LABOR, "role": "mk", "start_date": datetime.date(2022, 11, 1)},
    {"person_id": PERSON_IDS[6], "party_instance_id": PARTY_NEW_HOPE, "role": "mk", "start_date": datetime.date(2022, 11, 1)},
    {"person_id": PERSON_IDS[7], "party_instance_id": PARTY_LIKUD, "role": "mk", "start_date": datetime.date(2022, 11, 1)},
    # Cross-party mover: was in Likud, now in New Hope (demonstrates volatility)
    {"person_id": PERSON_IDS[8], "party_instance_id": PARTY_LIKUD, "role": "mk", "start_date": datetime.date(2019, 4, 9), "end_date": datetime.date(2022, 1, 1)},
    {"person_id": PERSON_IDS[8], "party_instance_id": PARTY_NEW_HOPE, "role": "candidate", "start_date": datetime.date(2022, 11, 1)},
    # Cross-party mover B: was in Yesh Atid, now in New Hope
    {"person_id": PERSON_IDS[9], "party_instance_id": PARTY_YESH_ATID, "role": "mk", "start_date": datetime.date(2021, 3, 23), "end_date": datetime.date(2022, 6, 1)},
    {"person_id": PERSON_IDS[9], "party_instance_id": PARTY_NEW_HOPE, "role": "candidate", "start_date": datetime.date(2022, 11, 1)},
]

# 40 questions: 2 per policy item
QUESTIONS_DATA = [
    # jud_01
    ("jud_01", "Should the Supreme Court have the authority to strike down Basic Laws passed by the Knesset?", "האם בית המשפט העליון צריך להיות מוסמך לפסול חוקי יסוד שהתקבלו בכנסת?"),
    ("jud_01", "Should a simple majority of Knesset members be able to override any Supreme Court ruling?", "האם רוב פשוט של חברי הכנסת צריך להיות מסוגל לבטל כל פסיקה של בית המשפט העליון?"),
    # jud_02
    ("jud_02", "Should the Judicial Appointments Committee include more elected politicians and fewer sitting judges?", "האם ועדת מינויים לשפיטה צריכה לכלול יותר פוליטיקאים נבחרים ופחות שופטים?"),
    ("jud_02", "Should the government coalition have veto power over Supreme Court justice appointments?", "האם לקואליציה הממשלתית צריך להיות כוח וטו על מינויי שופטי בית המשפט העליון?"),
    # jud_03
    ("jud_03", "Should the Knesset be able to reinstate a law that the Supreme Court declared unconstitutional?", "האם הכנסת צריכה להיות מסוגלת לאשרר חוק שבית המשפט העליון פסל כלא חוקתי?"),
    ("jud_03", "Should an override clause require a special supermajority (e.g. 80 MKs) or is a simple majority sufficient?", "האם סעיף התגברות צריך לדרוש רוב מיוחד (למשל 80 ח\"כים) או שדי ברוב רגיל?"),
    # jud_04
    ("jud_04", "Should the Attorney General be directly accountable to the elected government?", "האם היועץ המשפטי לממשלה צריך להיות כפוף ישירות לממשלה הנבחרת?"),
    ("jud_04", "Should the government be able to appoint and dismiss the Attorney General without external review?", "האם הממשלה צריכה להיות מסוגלת למנות ולפטר את היועמ''ש ללא בקרה חיצונית?"),
    # eco_01
    ("eco_01", "Should the top income tax bracket be raised to fund public services?", "האם יש להעלות את שיעור מס ההכנסה הגבוה ביותר למימון שירותים ציבוריים?"),
    ("eco_01", "Should capital gains taxes be reduced to encourage investment?", "האם יש להפחית את מס רווחי הון כדי לעודד השקעות?"),
    # eco_02
    ("eco_02", "Should the state expand child benefits and social assistance programs?", "האם המדינה צריכה להרחיב גמלאות ילדים ותוכניות סיוע סוציאלי?"),
    ("eco_02", "Should essential utilities (electricity, water) remain fully state-owned?", "האם שירותים חיוניים (חשמל, מים) צריכים להישאר בבעלות מדינה מלאה?"),
    # eco_03
    ("eco_03", "Should the government intervene to cap residential rental prices?", "האם הממשלה צריכה להתערב לצורך הגבלת שכר דירה למגורים?"),
    ("eco_03", "Should the state build and rent public ('social') housing at subsidized rates?", "האם המדינה צריכה לבנות ולהשכיר דיור ציבורי במחירים מסובסדים?"),
    # eco_04
    ("eco_04", "Should state funding for yeshivas (religious seminaries) be reduced?", "האם יש להפחית את מימון המדינה לישיבות?"),
    ("eco_04", "Should religious councils receive the same per-capita state funding as secular municipalities?", "האם מועצות דתיות צריכות לקבל מימון מדינה שווה לנפש כמו רשויות חילוניות?"),
    # rel_01
    ("rel_01", "Should civil marriage (without a rabbi or religious authority) be legally recognized in Israel?", "האם נישואים אזרחיים (ללא רב או סמכות דתית) צריכים להיות מוכרים חוקית בישראל?"),
    ("rel_01", "Should Jewish Israelis who marry abroad in civil ceremonies be recognized as married by the state upon their return?", "האם יהודים ישראלים שנישאו בחו''ל בנישואים אזרחיים צריכים להיות מוכרים כנשואים על ידי המדינה עם שובם?"),
    # rel_02
    ("rel_02", "Should supermarkets and shopping centers be permitted to open on Shabbat?", "האם יש לאפשר לסופרמרקטים ולמרכזי קניות לפתוח בשבת?"),
    ("rel_02", "Should local city councils have the authority to decide independently whether businesses may operate on Shabbat?", "האם מועצות עיריות מקומיות צריכות להיות מוסמכות להחליט באופן עצמאי האם עסקים רשאים לפעול בשבת?"),
    # rel_03
    ("rel_03", "Should ultra-Orthodox (Haredi) men be required to serve in the Israeli military?", "האם גברים חרדים צריכים להתגייס לצבא הישראלי?"),
    ("rel_03", "Should Haredi men who study full-time in yeshivas receive a formal exemption from military service?", "האם גברים חרדים הלומדים במשרה מלאה בישיבות צריכים לקבל פטור רשמי משירות צבאי?"),
    # rel_04
    ("rel_04", "Should the state's exclusive kashrut (kosher certification) monopoly be abolished and opened to private supervision?", "האם המונופול הממלכתי על כשרות צריך להתבטל ולהיפתח לפיקוח פרטי?"),
    ("rel_04", "Should restaurants be required to display only state-approved kashrut certification?", "האם מסעדות צריכות להידרש להציג רק תעודת כשרות שאושרה על ידי המדינה?"),
    # sec_01
    ("sec_01", "Do you support the establishment of an independent Palestinian state alongside Israel?", "האם אתה תומך בהקמת מדינה פלסטינית עצמאית לצד ישראל?"),
    ("sec_01", "Should Israel negotiate a final-status peace agreement with Palestinian leadership?", "האם ישראל צריכה לנהל משא ומתן על הסכם מעמד סופי עם ההנהגה הפלסטינית?"),
    # sec_02
    ("sec_02", "Should Israel continue to expand Jewish settlements in the West Bank?", "האם ישראל צריכה להמשיך להרחיב את ההתנחלויות היהודיות בגדה המערבית?"),
    ("sec_02", "Should Israel remove any existing settlements as part of a peace agreement?", "האם ישראל צריכה לפנות התנחלויות קיימות כחלק מהסכם שלום?"),
    # sec_03
    ("sec_03", "Should Israel increase its defense budget as a share of GDP?", "האם ישראל צריכה להגדיל את תקציב הביטחון כחלק מהתמ''ג?"),
    ("sec_03", "Should defense spending be reduced in order to fund social programs?", "האם יש להפחית הוצאות ביטחון כדי לממן תוכניות חברתיות?"),
    # sec_04
    ("sec_04", "Should Israel accept a temporary ceasefire in Gaza without achieving all military objectives first?", "האם ישראל צריכה לקבל הפסקת אש זמנית בעזה מבלי להשיג תחילה את כל המטרות הצבאיות?"),
    ("sec_04", "Should hostage return be prioritized over military objectives in Gaza negotiations?", "האם יש לתעדף החזרת החטופים על פני מטרות צבאיות במשא ומתן עזה?"),
    # civ_01
    ("civ_01", "Should same-sex couples have the same legal rights as different-sex married couples in Israel?", "האם לזוגות חד-מיניים צריכות להיות אותן זכויות חוקיות כמו לזוגות נשואים מסוגים שונים בישראל?"),
    ("civ_01", "Should same-sex couples have the right to adopt children in Israel?", "האם לזוגות חד-מיניים צריכה להיות הזכות לאמץ ילדים בישראל?"),
    # civ_02
    ("civ_02", "Should Arabic be maintained as an official state language with full government services available in Arabic?", "האם יש לשמור על ערבית כשפת מדינה רשמית עם שירותי ממשל מלאים בערבית?"),
    ("civ_02", "Should Arab citizens of Israel receive equal per-capita budget allocations from the state?", "האם לאזרחים ערבים של ישראל צריכה להיות הקצאת תקציב שווה לנפש מהמדינה?"),
    # civ_03
    ("civ_03", "Should public broadcasting be fully independent from government influence?", "האם השידור הציבורי צריך להיות בלתי תלוי לחלוטין מהשפעת הממשלה?"),
    ("civ_03", "Should the government have the power to appoint the majority of public broadcaster board members?", "האם לממשלה צריכה להיות הסמכות למנות את רוב חברי דירקטוריון השידור הציבורי?"),
    # civ_04
    ("civ_04", "Should anti-discrimination laws protect LGBTQ+ individuals in employment and services?", "האם חוקי אי-אפליה צריכים להגן על אנשים להט''בים בתעסוקה ובשירותים?"),
    ("civ_04", "Should religious institutions be exempt from anti-discrimination requirements when hiring staff?", "האם למוסדות דתיים צריך להיות פטור מדרישות אי-אפליה בעת גיוס עובדים?"),
]

