"""Curated Indian pools for the demo dataset. Plain data, no logic.

Company names are invented from common Indian trade-name words; they are not real businesses.
Cities are industrial clusters, each with its GST state code.
"""

CITIES: tuple[tuple[str, str, str], ...] = (
    ("Coimbatore", "Tamil Nadu", "33"),
    ("Chennai", "Tamil Nadu", "33"),
    ("Hosur", "Tamil Nadu", "33"),
    ("Pune", "Maharashtra", "27"),
    ("Nashik", "Maharashtra", "27"),
    ("Aurangabad", "Maharashtra", "27"),
    ("Ludhiana", "Punjab", "03"),
    ("Rajkot", "Gujarat", "24"),
    ("Ahmedabad", "Gujarat", "24"),
    ("Vadodara", "Gujarat", "24"),
    ("Bengaluru", "Karnataka", "29"),
    ("Howrah", "West Bengal", "19"),
    ("Faridabad", "Haryana", "06"),
    ("Indore", "Madhya Pradesh", "23"),
    ("Hyderabad", "Telangana", "36"),
)

COMPANY_PREFIXES: tuple[str, ...] = (
    "Sri Murugan",
    "Kalyan",
    "Nova",
    "Bharat",
    "Shree Ganesh",
    "Premier",
    "Sahyadri",
    "Coastal",
    "Rajdhani",
    "Om Sai",
    "Vishwakarma",
    "Lakshmi",
    "Trident",
    "Mahalaxmi",
    "Konark",
    "Sathya",
    "Jai Bajrang",
    "Eastern",
    "Deccan",
    "Pioneer",
)

COMPANY_SUFFIXES: tuple[str, ...] = (
    "Fasteners Pvt Ltd",
    "Engineering Works",
    "Bearings Pvt Ltd",
    "Forgings LLP",
    "Pumps Pvt Ltd",
    "Auto Components Pvt Ltd",
    "Castings Pvt Ltd",
    "Industries Pvt Ltd",
    "Tools Pvt Ltd",
    "Precision Components LLP",
)

FIRST_NAMES: tuple[str, ...] = (
    "Karthik",
    "Meghana",
    "Suresh",
    "Anand",
    "Rajesh",
    "Priyanka",
    "Vikram",
    "Deepa",
    "Farhan",
    "Ravi",
    "Lakshmi",
    "Arun",
    "Sunita",
    "Harpreet",
    "Gurpreet",
    "Nilesh",
    "Kiran",
    "Abhishek",
    "Pooja",
    "Venkatesh",
    "Ashwin",
    "Manoj",
    "Shalini",
    "Faisal",
    "Divya",
    "Sandeep",
    "Neha",
    "Prakash",
    "Ramesh",
)

LAST_NAMES: tuple[str, ...] = (
    "Subramanian",
    "Joshi",
    "Iyer",
    "Patil",
    "Reddy",
    "Singh",
    "Kulkarni",
    "Naidu",
    "Mehta",
    "Shah",
    "Nair",
    "Pillai",
    "Gupta",
    "Chauhan",
    "Desai",
    "Bhatt",
    "Khan",
    "Rao",
    "Menon",
    "Kaur",
    "Verma",
    "Sharma",
)

JOB_TITLES: tuple[str, ...] = (
    "Purchasing Manager",
    "Plant Head",
    "Procurement Officer",
    "Maintenance Engineer",
    "Owner",
    "Stores In-charge",
)

LEAD_SOURCES: tuple[str, ...] = (
    "website",
    "referral",
    "trade fair",
    "cold call",
    "IndiaMART enquiry",
)

# Colloquial phrasings a sales rep would actually type; the catalog name is never used verbatim.
ACTIVITY_TEMPLATES: tuple[str, ...] = (
    "Call: {contact} ko {product} ka rate bheja, kal tak confirm karenge bola.",
    "Plant visit. {product} ki delivery time pe complaint thi, 15 din ka lead time bata diya.",
    "WhatsApp: bhai {product} stock mein hai kya? {qty} chahiye.",
    "Email: quotation for {product} sent, valid 15 days. 3% discount offer kiya.",
    "Note: procurement ne bola local vendor se bhi comparison chal raha hai.",
    "Meeting: {contact} ne {product} ka sample maanga, courier kar diya.",
    "Call: payment ka follow-up, invoice clear hone ka wait hai.",
    "Note: decision maker ke saath demo fix hua, agle hafte call.",
)

FOLLOW_UP_TEMPLATES: tuple[str, ...] = (
    "Pehli baat hui, {product} ki requirement samjhi.",
    "Quotation bhej diya, {contact} review kar rahe hain.",
    "Price negotiation: bola {qty} pe better rate chahiye.",
    "Confirmation mil gaya, PO ka wait hai.",
)

# Colloquial names by catalog family; the product is referred to this way in activity text.
FASTENER_COLLOQUIAL = {"SS304": "stainless", "SS316": "316 stainless", "MS": "mild steel"}
