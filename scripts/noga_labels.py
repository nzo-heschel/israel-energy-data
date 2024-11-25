NS_SMP = "noga2.smp"
NS_CO2 = "noga2.co2emission"
NS_FORECAST2 = "noga2.forecast2"
NS_SYSTEM_DEMAND = "noga2.system_demand"
NS_ENERGY = "noga2.energy"
NS_PRODUCER = "noga2.producer"
NS_RESERVE = "noga2.reserve"
NS_MARKET = "noga2.market"
NS_COST = "noga2.cost"

UNKNOWN = "unknown"

LABELS_UNIQUE_KEY = {
    "מחיר שולי": NS_SMP,
    "חסכון בפליטות": NS_CO2,
    "יחס פליטות": NS_CO2,
    "(MW) מתחדשות": NS_FORECAST2,
    "תחזית ביקוש": NS_SYSTEM_DEMAND,
    "ניהול הביקוש": NS_ENERGY,
    "יצרנים פרטיים": NS_PRODUCER,
    "פוטו וולטאי משולב אגירה": NS_ENERGY,
    "חיובית": NS_RESERVE,
    "אגירה שאובה": NS_MARKET,
    "עלות ₪/MW": NS_COST,
}

NS_LABEL_MAP_HEB2ENG = {
    NS_SMP: (
        "Date", "Time",
        "Pre Booking Price Constrained SMP",
        "Pre Booking Price Unconstrained SMP",
        "Real Time Pricing Constrained SMP",
        "Real Time Pricing Unconstrained SMP",
    ),
    NS_CO2: {
        "פחם": "Coal", "סולר": "Gasoil",  "גז": "Gas", "מזוט": "Fueloil",
        "מתנול": "Methanol",
        "חסכון בפליטות על ידי ייצור באנרגיות מתחדשות": "Renewables",
        'סה"כ פליטות לא כולל מתחדשות': "Co2 From All Sites Without Renewables",
        'יחס פליטות (mTCO2\MWh) CO2': "Co2 Ratio"
    },
    NS_FORECAST2: {
        "(MW) מתחדשות": "Renewable"
    },
    NS_SYSTEM_DEMAND: {
        "תחזית ביקוש יום מראש": "Demand Ahead",
        "תחזית ביקוש עדכנית": "Demand Updated",
        "ביקוש בפועל": "Demand Current"
    },
    NS_ENERGY: {
        "פחם": "Coal", "גז": "Gas", "סולר": "Solar", "מזוט": "Mazut", "אגירה שאובה": "PSP",
        "אחר": "Other", "פוטו-וולטאי": "PV", "תרמו סולארי": "Thermo", "רוח": "Wind",
        "ביוגז": "Bio Gas", "ניהול הביקוש": "Demand Management",
        'סה"כ מתחדשות': "Renewables", "ייצור משקי בפועל": "Actualdemand",
        "פוטו וולטאי משולב אגירה": "PV With Storage"
    },
    NS_PRODUCER: {
        "חברת החשמל": "IEC Production",
        "יצרנים פרטיים": "Private Production"
    },
    NS_RESERVE: {
        "חיובית": "Spinning Reserve",
        "שלילית": "Drop Reserve"
    },
    NS_MARKET: {
        "פחם": "Coal", "גז": "Gas", "סולר": "Soler", "מזוט": "Mazut", "אחר": "Mazut Rotem",
        "מתנול": "Methanol", "אגירה שאובה": "MAGP", "פוטו-וולטאי": "PV", "תרמו סולארי": "Plot",
        "רוח": "Wind", "ביוגז": "Biogas", "סך הכל": "Sum"
    },
    NS_COST: {
        "עלות ₪/MW": "Cost"
    }
}

for namespace, d in NS_LABEL_MAP_HEB2ENG.items():
    if isinstance(d, dict):
        d["תאריך"] = "Date"
        d["שעה"] = "Time"


def new_labels(labels):
    labels_str = ",".join(labels)
    if "ו" not in labels_str:
        raise ValueError("File must be with Hebrew headings")
    namespace = UNKNOWN
    for heb_label, namespace in LABELS_UNIQUE_KEY.items():
        if heb_label in labels_str:
            break
    if namespace == UNKNOWN:
        return UNKNOWN, labels
    labels_map = NS_LABEL_MAP_HEB2ENG[namespace]
    if isinstance(labels_map, tuple):
        return namespace, labels_map
    new_labels = [labels_map.get(label) or "Unnamed" for label in labels]
    return namespace, new_labels
