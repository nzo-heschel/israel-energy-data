SMP = "smp"
CO2_EMISSION = "co2emission"
SYSTEM_DEMAND = "system_demand"
ENERGY = "energy"

NOGA2 = "noga2."

NS_SMP = NOGA2 + SMP
NS_CO2 = NOGA2 + CO2_EMISSION
NS_FORECAST2 = "noga2.forecast2"
NS_SYSTEM_DEMAND = NOGA2 + SYSTEM_DEMAND
NS_ENERGY = NOGA2 + ENERGY
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

# TODO: These labels now appear in two places. Make them constants.
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
        'סה"כ מתחדשות': "Renewables", "ייצור משקי בפועל": "Actual Demand",
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

# Mapping of noga POST response labels to tags

NS_LABEL_POST_MAP = {
    "smp": {
        "real_Time_Constrained_Smp": "Real Time Pricing Constrained SMP",
        "real_Time_Unconstrained_Smp": "Real Time Pricing Unconstrained SMP",
        "day_Ahead_Constrained_Smp": "Pre Booking Price Constrained SMP",
        "day_Ahead_Unconstrained_Smp": "Pre Booking Price Unconstrained SMP"
    },
    "energy": {  # production mix
        "coal": "Coal",
        "natural_Gas": "Gas",
        "soler": "Solar",
        "mazut": "Mazut",
        "pumped_Storage": "PSP",
        "other": "Other",
        "photoVoltaic": "PV",
        "termo_Soler": "Thermo",
        "wind": "Wind",
        "bio_Gas": "Bio Gas",
        "actual_Demand": "Actual Demand"
    },
    "system_demand": {
        "demandHead": "Demand Ahead",
        "demandUpdated": "Demand Updated",
        "demandCurrent": "Demand Current"

    },
    "co2emission": {
        "co2_coal": "Coal",
        "co2_gas": "Gas",
        "co2_diesel": "Gasoil",
        "co2_mazut": "Fueloil",
        "co2_methanol": "Methanol",
        "co2_from_all_sites": "Co2 From All Sites Without Renewables",
        "co2_renewables": "Renewables",
        "co2_current_demand": "Co2 Current Demand",
        "co2_ratio": "Co2 Ratio"
    },
}

for namespace, d in NS_LABEL_POST_MAP.items():
    d["date"] = "Date"
    d["time"] = "Time"


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
