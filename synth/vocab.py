"""Vocabulary for the synthetic directory.

Everything in this module is invented except the borough / county / ZIP
geography and ordinary street names, which are public knowledge. No real
person, practice, vendor, or phone number is represented.
"""

# ---------------------------------------------------------------------------
# People
# ---------------------------------------------------------------------------

FIRST_NAMES = [
    "Aaliyah", "Aaron", "Abigail", "Adam", "Adriana", "Ahmed", "Aisha", "Alejandro",
    "Alexander", "Alice", "Amara", "Amir", "Ana", "Andre", "Andrea", "Angela", "Anna",
    "Anthony", "Aria", "Arjun", "Asher", "Ava", "Benjamin", "Bianca", "Brandon", "Brian",
    "Camila", "Carlos", "Carmen", "Caroline", "Catherine", "Charles", "Chen", "Chloe",
    "Christopher", "Claire", "Daniel", "Daniela", "David", "Deborah", "Denise", "Diana",
    "Diego", "Dominic", "Dylan", "Elena", "Elijah", "Elizabeth", "Emily", "Emma", "Eric",
    "Ethan", "Eva", "Evelyn", "Fatima", "Felix", "Fiona", "Gabriel", "Grace", "Hannah",
    "Hassan", "Helen", "Henry", "Ibrahim", "Irene", "Isaac", "Isabella", "Ivan", "Jacob",
    "James", "Jasmine", "Javier", "Jennifer", "Jessica", "John", "Jonathan", "Jordan",
    "Jose", "Joseph", "Julia", "Karen", "Kevin", "Layla", "Leah", "Leon", "Liam", "Lila",
    "Lucas", "Luis", "Maria", "Mariam", "Mark", "Martin", "Maya", "Mei", "Michael",
    "Miguel", "Mohammed", "Nadia", "Naomi", "Natalie", "Nathan", "Nicole", "Nina", "Noah",
    "Olivia", "Omar", "Oscar", "Patricia", "Paul", "Priya", "Rachel", "Rafael", "Ravi",
    "Rebecca", "Richard", "Robert", "Rosa", "Ruth", "Ryan", "Samuel", "Sara", "Sarah",
    "Sean", "Sofia", "Sophia", "Stephen", "Susan", "Tariq", "Thomas", "Victor", "Victoria",
    "Vivian", "Wei", "William", "Xavier", "Yara", "Yusuf", "Zoe",
]

LAST_NAMES = [
    "Abbott", "Acosta", "Adler", "Aguilar", "Ahmed", "Ali", "Alvarez", "Anderson", "Baker",
    "Banerjee", "Barnes", "Bauer", "Becker", "Bell", "Bennett", "Berg", "Bishop", "Blake",
    "Bowen", "Brooks", "Burke", "Byrne", "Cabrera", "Calloway", "Campbell", "Cardenas",
    "Carter", "Castillo", "Chan", "Chen", "Choi", "Clark", "Cohen", "Cole", "Collins",
    "Cooper", "Cortez", "Cruz", "Dawson", "Delgado", "Diaz", "Dixon", "Doyle", "Duarte",
    "Duncan", "Edwards", "Ellis", "Espinoza", "Evans", "Farrell", "Fischer", "Fleming",
    "Flores", "Foster", "Fox", "Franklin", "Freeman", "Fuentes", "Garcia", "Gill", "Gomez",
    "Gonzalez", "Graham", "Grant", "Green", "Griffin", "Gupta", "Hall", "Hamilton", "Harper",
    "Harris", "Hayes", "Henderson", "Hernandez", "Holland", "Howard", "Huang", "Hughes",
    "Hunt", "Ibrahim", "Iyer", "Jackson", "James", "Jensen", "Johnson", "Jones", "Jordan",
    "Kaur", "Keller", "Kelly", "Khan", "Kim", "King", "Klein", "Kowalski", "Kumar", "Lam",
    "Lambert", "Lee", "Levine", "Lewis", "Li", "Lin", "Lopez", "Lynch", "Malik", "Marsh",
    "Martin", "Martinez", "Mason", "Mehta", "Mendez", "Miller", "Mitchell", "Moore",
    "Morales", "Moreno", "Morgan", "Murphy", "Nakamura", "Nash", "Nelson", "Nguyen", "Novak",
    "O'Brien", "Okafor", "Ortiz", "Osei", "Owens", "Park", "Patel", "Perez", "Peterson",
    "Pham", "Phillips", "Porter", "Powell", "Quinn", "Ramirez", "Ramos", "Reed", "Reyes",
    "Rivera", "Roberts", "Robinson", "Rodriguez", "Rossi", "Russo", "Ryan", "Sanchez",
    "Sanders", "Santos", "Schmidt", "Scott", "Shah", "Sharma", "Silva", "Singh", "Smith",
    "Sullivan", "Tanaka", "Taylor", "Torres", "Tran", "Turner", "Vargas", "Vasquez", "Walker",
    "Wallace", "Wang", "Ward", "Watson", "Weber", "White", "Williams", "Wilson", "Wong",
    "Wright", "Wu", "Yang", "Young", "Zhang",
]

# The one practitioner the advisory checklist says must not appear. The surname is
# deliberately absent from LAST_NAMES so the record is unique in the data.
NAMED_EXCLUSION = {"FirstName": "Theodora", "LastName": "Vance", "Specialty": "Internal Medicine"}

# ---------------------------------------------------------------------------
# Geography (public knowledge: NYC boroughs, their counties, real ZIP codes)
# ---------------------------------------------------------------------------

BOROUGHS = {
    "Manhattan": {
        "county": "New York",
        "zips": ["10001", "10002", "10003", "10009", "10010", "10011", "10012", "10013",
                 "10014", "10016", "10017", "10018", "10019", "10021", "10022", "10023",
                 "10024", "10025", "10026", "10027", "10028", "10029", "10030", "10031",
                 "10032", "10033", "10034", "10035", "10036", "10037", "10038", "10039",
                 "10040", "10044", "10065", "10075", "10128", "10280"],
        "area_codes": ["212", "646", "917"],
    },
    "Bronx": {
        "county": "Bronx",
        "zips": ["10451", "10452", "10453", "10454", "10455", "10456", "10457", "10458",
                 "10459", "10460", "10461", "10462", "10463", "10464", "10465", "10466",
                 "10467", "10468", "10469", "10470", "10471", "10472", "10473", "10474",
                 "10475"],
        "area_codes": ["718", "347", "929"],
    },
    "Brooklyn": {
        "county": "Kings",
        "zips": ["11201", "11203", "11204", "11205", "11206", "11207", "11208", "11209",
                 "11210", "11211", "11212", "11213", "11214", "11215", "11216", "11217",
                 "11218", "11219", "11220", "11221", "11222", "11223", "11224", "11225",
                 "11226", "11228", "11229", "11230", "11231", "11232", "11233", "11234",
                 "11235", "11236", "11237", "11238", "11239"],
        "area_codes": ["718", "347", "929"],
    },
    "Queens": {
        "county": "Queens",
        "zips": ["11004", "11101", "11102", "11103", "11104", "11105", "11106", "11354",
                 "11355", "11356", "11357", "11358", "11360", "11361", "11362", "11363",
                 "11364", "11365", "11366", "11367", "11368", "11369", "11370", "11372",
                 "11373", "11374", "11375", "11377", "11378", "11379", "11385", "11411",
                 "11412", "11413", "11414", "11415", "11416", "11417", "11418", "11419",
                 "11420", "11421", "11422", "11423", "11426", "11427", "11428", "11429",
                 "11432", "11433", "11434", "11435", "11436", "11691", "11692", "11693",
                 "11694"],
        "area_codes": ["718", "347", "929"],
    },
    "Staten Island": {
        "county": "Richmond",
        "zips": ["10301", "10302", "10303", "10304", "10305", "10306", "10307", "10308",
                 "10309", "10310", "10312", "10314"],
        "area_codes": ["718", "347"],
    },
}

# Share of addresses per borough, roughly proportional to population.
BOROUGH_WEIGHTS = [("Manhattan", 28), ("Brooklyn", 26), ("Queens", 24), ("Bronx", 15),
                   ("Staten Island", 7)]

# Queens mailing addresses use neighborhood names; everywhere else uses the borough.
_QUEENS_CITY_BY_PREFIX = {
    "110": "Floral Park", "111": "Long Island City", "1135": "Flushing", "1136": "Bayside",
    "1137": "Jackson Heights", "1138": "Ridgewood", "114": "Jamaica", "116": "Far Rockaway",
}


def city_for(borough: str, zip_code: str) -> str:
    if borough == "Manhattan":
        return "New York"
    if borough != "Queens":
        return borough
    for prefix, city in _QUEENS_CITY_BY_PREFIX.items():
        if zip_code.startswith(prefix):
            return city
    return "Queens"


STREETS = {
    "Manhattan": ["Broadway", "Amsterdam Ave", "Lexington Ave", "1st Ave", "2nd Ave",
                  "3rd Ave", "Park Ave", "W 57th St", "E 86th St", "W 125th St", "Canal St",
                  "Columbus Ave", "St Nicholas Ave", "E 14th St", "Madison Ave"],
    "Bronx": ["Grand Concourse", "E Fordham Rd", "Jerome Ave", "Westchester Ave",
              "White Plains Rd", "E Tremont Ave", "Southern Blvd", "Bruckner Blvd",
              "Morris Park Ave", "E 149th St", "Boston Rd", "Pelham Pkwy"],
    "Brooklyn": ["Flatbush Ave", "Atlantic Ave", "Court St", "Ocean Pkwy", "Nostrand Ave",
                 "Kings Hwy", "Bay Pkwy", "Myrtle Ave", "Fulton St", "Bedford Ave",
                 "Church Ave", "Utica Ave", "Coney Island Ave", "Bay Ridge Ave"],
    "Queens": ["Queens Blvd", "Northern Blvd", "Hillside Ave", "Steinway St", "Main St",
               "Roosevelt Ave", "Jamaica Ave", "Union Tpke", "Astoria Blvd", "Kissena Blvd",
               "Bell Blvd", "Myrtle Ave", "Beach 20th St", "Liberty Ave"],
    "Staten Island": ["Victory Blvd", "Hylan Blvd", "Bay St", "Richmond Ave", "Forest Ave",
                      "Amboy Rd", "Richmond Rd", "New Dorp Ln", "Castleton Ave",
                      "Arthur Kill Rd", "Clove Rd", "Targee St"],
}

ADDRESS2_OPTIONS = ["", "", "", "", "", "Suite 100", "Suite 201", "Suite 3B", "2nd Floor",
                    "3rd Floor", "Ground Floor", "Lower Level"]

# ---------------------------------------------------------------------------
# Professional providers
# ---------------------------------------------------------------------------

# (specialty, provider type, relative frequency)
SPECIALTIES = [
    ("Internal Medicine", "Physician", 10), ("Family Medicine", "Physician", 8),
    ("Pediatrics", "Physician", 7), ("Cardiology", "Physician", 4),
    ("Pediatric Cardiology", "Physician", 1), ("Dermatology", "Physician", 3),
    ("Endocrinology", "Physician", 2), ("Gastroenterology", "Physician", 3),
    ("Neurology", "Physician", 3), ("Obstetrics & Gynecology", "Physician", 5),
    ("Ophthalmology", "Physician", 3), ("Orthopedic Surgery", "Physician", 3),
    ("Otolaryngology", "Physician", 2), ("Nephrology", "Physician", 2),
    ("Oncology", "Physician", 2), ("Pulmonology", "Physician", 2),
    ("Rheumatology", "Physician", 1), ("Urology", "Physician", 2),
    ("Neonatology", "Physician", 1), ("Allergy & Immunology", "Physician", 1),
    ("Podiatry", "Other", 3), ("Chiropractic", "Other", 2), ("Optometry", "Other", 3),
    ("Midwifery", "Other", 1), ("Psychiatry", "Behavioral Health", 4),
    ("Psychology", "Behavioral Health", 4), ("Clinical Social Work", "Behavioral Health", 6),
    ("Substance Use Counseling", "Behavioral Health", 2),
    ("Physical Therapy", "Therapist", 5), ("Occupational Therapy", "Therapist", 3),
    ("Speech-Language Pathology", "Therapist", 2),
    ("Nurse Practitioner", "Nurse Practitioner", 8),
    ("Physician Assistant", "Physician Assistant", 5),
    ("Care Management", "Other", 3), ("School-Based Health", "Other", 2),
]

PROVIDER_TYPE_FOR_SPECIALTY = {s: t for s, t, _ in SPECIALTIES}

# Specialties that have no listings in a county. Invented placeholder rule — see
# ASSUMPTIONS.md. Any row carrying one of these pairs is invalid.
SPECIALTY_COUNTY_EXCLUSIONS = [
    ("Care Management", "Richmond"),
    ("Neonatology", "Richmond"),
    ("Pediatric Cardiology", "Bronx"),
]

SCHOOL_BASED_SPECIALTY = "School-Based Health"
SCHOOL_LIMITATION_TEXT = "Serves enrolled students of the host school only"

# How many practice locations a practitioner has.
LOCATION_COUNT_WEIGHTS = [(1, 35), (2, 30), (3, 18), (4, 10), (5, 7)]

NETWORKS = [("Harbor Network", 55), ("Summit Network", 30), ("Crossroads Network", 15)]

PROFESSIONAL_SOURCES = [("CredentialingFeed", 60), ("PracticeRosterFeed", 30),
                        ("DelegatedGroupFeed", 10)]

OFFICE_NAME_PATTERNS = [
    "{last} Medical Group", "{prefix} Medical Associates", "{prefix} Family Health",
    "{prefix} Health Partners", "{last} & Associates", "{prefix} Physicians PC",
    "{prefix} Community Health", "{last} Medical PC",
]

# ---------------------------------------------------------------------------
# Organizations (service directory)
# ---------------------------------------------------------------------------

NAME_PREFIXES = [
    "Harborview", "Riverside", "Parkside", "Summit", "Meadowbrook", "Bayview", "Crossroads",
    "Lighthouse", "Beacon", "Northgate", "Eastbridge", "Westfield", "Cedar Hill",
    "Maple Grove", "Stonebridge", "Willowbrook", "Silver Lake", "Bluepoint", "Kingsway",
    "Metro", "Empire", "Liberty", "Unity", "Horizon", "Atlas", "Pinnacle", "Evergreen",
    "Sunrise", "Clearview", "Fairmont", "Oakridge", "Brightwater", "Greenfield",
    "Highbridge", "Seaside", "Hillcrest", "Ironwood", "Lakeshore", "Redwood", "Tidewater",
]

# (facility type, service types offered, relative frequency, name suffixes, source feed)
FACILITY_TYPES = [
    ("Hospital", ["Inpatient", "Outpatient", "Emergency"], 3,
     ["Hospital", "Medical Center"], "HospitalContractFeed"),
    ("Clinic", ["Outpatient", "Urgent Care", "CORE"], 12,
     ["Clinic", "Health Center", "Family Health"], "FacilityContractFeed"),
    ("Vision Provider", ["Vision"], 10,
     ["Vision Center", "Eye Care", "Optical"], "VisionVendorFeed"),
    ("Pharmacy", ["Pharmacy"], 8,
     ["Pharmacy", "Drugs", "Rx"], "PharmacyNetworkFeed"),
    ("Transportation", ["Ambulette", "Ambulance", "Livery"], 6,
     ["Transport Co", "Ambulette Service", "Medical Transportation"], "TransportVendorFeed"),
    ("Home Care Agency", ["Home Health Aide", "Skilled Nursing", "Care Coordination",
                          "Physical Therapy"], 15,
     ["Home Care", "Home Health Services", "Community Care"], "HomeCareFeed"),
    ("Equipment Supplier", ["Durable Equipment", "Respiratory Equipment", "Orthotics"], 7,
     ["Med Supply", "Medical Equipment", "Surgical Supply"], "EquipmentSupplierFeed"),
    ("Laboratory", ["Laboratory"], 5, ["Laboratories", "Diagnostics"], "FacilityContractFeed"),
    ("Imaging Center", ["Radiology"], 5, ["Imaging", "Radiology Associates"], "FacilityContractFeed"),
    ("Dialysis Center", ["Dialysis"], 4, ["Dialysis Center", "Kidney Care"], "FacilityContractFeed"),
    ("Behavioral Health Center", ["Outpatient", "CORE", "Substance Use"], 6,
     ["Counseling Center", "Behavioral Health", "Recovery Center"], "FacilityContractFeed"),
]

VISION_FACILITY_TYPE = "Vision Provider"
VISION_SERVICE_TYPE = "Vision"

# A home-care feed that, in the current month, started sending one row per service
# line instead of one row per location. Its growth is real rows, not new locations.
EXPANDING_SOURCE = "CommunityCareFeed"
EXPANDING_SOURCE_PRIOR_SERVICE = "Care Coordination"
EXPANDING_SOURCE_CURRENT_SERVICES = ["Care Coordination", "Home Health Aide",
                                     "Skilled Nursing", "Physical Therapy"]

# A feed retired before this cycle. Nothing from it belongs in the service directory.
RETIRED_SOURCE = "LegacyVendorFeed"

# An organization the checklist says must carry only the first coverage line.
NAMED_ORG = {"DisplayName": "Meadowbrook Transport Co", "FacilityType": "Transportation",
             "ServiceType": "Ambulette"}

ORG_LOCATION_COUNT_WEIGHTS = [(1, 55), (2, 22), (3, 12), (4, 6), (5, 3), (6, 2)]
ORG_SERVICE_COUNT_WEIGHTS = [(1, 70), (2, 20), (3, 10)]

# ---------------------------------------------------------------------------
# Pharmacies
# ---------------------------------------------------------------------------

LANGUAGES = ["Spanish", "Chinese", "Russian", "Hindi", "Bengali", "Korean", "Haitian Creole",
             "French", "Italian", "Polish", "Arabic", "Urdu", "Vietnamese", "Tagalog",
             "Greek", "Yiddish", "Hebrew", "Portuguese", "Punjabi", "Albanian"]

PHARMACY_SUFFIXES = ["Pharmacy", "Drugs", "Rx", "Apothecary", "Chemists"]

PHARMACY_HOURS = ["Mon-Fri 9-7, Sat 9-5", "Mon-Sat 8-8", "Daily 8-10", "Mon-Fri 8-6",
                  "24 hours", "Mon-Sun 9-9"]

# ---------------------------------------------------------------------------
# Advisory checklist (the informal spreadsheet, as natural-language notes)
# ---------------------------------------------------------------------------

ADVISORY_CHECKLIST = [
    ("Dr. Theodora Vance should no longer appear in the directory.", "2026-07-18", "Directory owner"),
    ("Make sure every vision provider has LineA set to 1.", "2026-05-02", "Directory owner"),
    ("Confirm vision services are included for Staten Island.", "2026-06-11", "Print coordinator"),
    ("Meadowbrook Transport Co is LineA only - LineB, LineC and LineD must be 0.", "2026-08-05",
     "Contracting"),
    ("Some vision listings have double spaces in the display name - check before print.", "2026-08-20",
     "Print coordinator"),
    ("October: the flu-clinic listings go in next cycle, not this one.", "2026-08-28", "Directory owner"),
    ("Care Management is not offered in Staten Island.", "2026-03-14", "Network management"),
    ("School-based providers must show the enrolled-students limitation text.", "2026-01-09", "Compliance"),
    ("LegacyVendorFeed was retired in July - nothing from it should be in the service directory.",
     "2026-07-30", "Directory owner"),
]
