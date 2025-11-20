import spacy
import dateparser
from dateparser.search import search_dates
import re
from datetime import datetime

nlp = spacy.load("en_core_web_sm")


def detect_tables_n_dates(nlp,text):
    # keywords : Data,Time,Filter
    Keywords_Table = {
        "stress": [
            "stress",
            "stress level",
            "stress score",
            "tension",
            "anxiety",
            "strain",
            "mental load",
            "stress pattern",
            "stress zones",
            "stress chart",
        ],
        "hr": [
            "heart rate",
            "hr",
            "bpm",
            "resting heart rate",
            "max heart rate",
            "pulse",
            "cardio",
            "hr zone",
            "heart beat",
            "heart-rate",
            "heart",
        ],
        "spo2": [
            "spo2",
            "oxygen",
            "blood oxygen",
            "oxygen saturation",
            "o2 level",
            "breathing",
            "respiration",
            "air levels",
            "oxygen dips",
            "oxygen score",
        ],
        "steps": [
            "steps",
            "step count",
            "walking",
            "walk",
            "daily steps",
            "distance walked",
            "movement",
            "stride",
            "pedometer",
            "step goal",
        ],
        "calorie": [
            "calories",
            "calorie burn",
            "energy burn",
            "burned",
            "metabolism",
            "active calories",
            "basal calories",
            "kcal",
            "energy expenditure",
            "fat burn",
            "cal",
        ],
        "exercise": [
            "exercise",
            "workout",
            "training",
            "session",
            "sports",
            "activity",
            "reps",
            "sets",
            "routine",
            "intensity",
            "activities",
        ],
    }
    text = text.lower()
    doc = nlp(text)
    words_to_dates = {}
    dates_total = []
    table_list = []
    table_word = ""  ## to make sure the table name isnt accidently used as a date
    for word in text.split(" "):
        for table, keys in Keywords_Table.items():
            for k in keys:
                if k in word:
                    table_list.append(table)
                    table_word = word

    ## spacy entity dates + dateparser.parse()
    for ent in doc.ents:
        if ent.label_ == "DATE":
            parsed = dateparser.parse(ent.text)
            if parsed and ent.text not in table_word:
                words_to_dates[ent.text] = parsed
    #
    dp_res = search_dates(text, languages=["en"])
    if dp_res:
        for phrase, dt in dp_res:
            if phrase not in table_word:
                words_to_dates[phrase] = dt

    ###########################################################
    ##REGEX
    MONTHS = r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec|january|february|march|april|may|june|july|august|september|october|november|december)"

    patterns = [
        # dd/mm/yyyy | dd-mm-yyyy | dd.mm.yyyy
        r"\b\d{1,2}[\/\-.]\d{1,2}[\/\-.]\d{2,4}\b",
        # yyyy-mm-dd
        r"\b\d{4}-\d{1,2}-\d{1,2}\b",
        # 12 Aug 2025
        rf"\b\d{{1,2}}(?:st|nd|rd|th)?\s+{MONTHS}\s+\d{{4}}\b",
        # Aug 12 2025
        rf"\b{MONTHS}\s+\d{{1,2}}(?:st|nd|rd|th)?\s+\d{{4}}\b",
        # August 12, 2025
        rf"\b{MONTHS}\s+\d{{1,2}}(?:st|nd|rd|th)?,\s+\d{{4}}\b",
        # 12th August
        rf"\b\d{{1,2}}(?:st|nd|rd|th)?\s+{MONTHS}\b",
        # Standalone month
        rf"\b{MONTHS}\b",
    ]

    found = []
    for p in patterns:
        matches = re.findall(p, text)
        for m in matches:
            found.append(m.strip())

    # Remove standalone month if part of a larger match
    filtered = []
    for f in found:
        if any((f != other and f in other) for other in found):
            continue
        filtered.append(f)

    # Unique + order preserved

    dates_regex = list(dict.fromkeys(filtered))

    # removing duplicates
    seen_dates = set()
    new_words_2_date_dict = {}
    for k, v in words_to_dates.items():
        date_only = v.date()  # removing hr/min/secs
        if date_only not in seen_dates:
            new_words_2_date_dict[k] = v
            seen_dates.add(date_only)

    return table_list, dates_regex, new_words_2_date_dict

def standardize_date(date_str, current_year=None):

    MONTHS = {
        "jan": 1,
        "january": 1,
        "feb": 2,
        "february": 2,
        "mar": 3,
        "march": 3,
        "apr": 4,
        "april": 4,
        "may": 5,
        "jun": 6,
        "june": 6,
        "jul": 7,
        "july": 7,
        "aug": 8,
        "august": 8,
        "sep": 9,
        "sept": 9,
        "september": 9,
        "oct": 10,
        "october": 10,
        "nov": 11,
        "november": 11,
        "dec": 12,
        "december": 12,
    }

    # if its datetime.datetime
    if isinstance(date_str, datetime):
        y = date_str.year
        m = date_str.month
        d = date_str.day

        return f"{y:04d}-{m:02d}-{d:02d}"

    # if its a string
    date_str = date_str.lower().strip()

    if current_year is None:
        current_year = datetime.now().year

    # Remove suffixes: 12th -> 12
    date_str = re.sub(r"(\d+)(st|nd|rd|th)", r"\1", date_str)

    # ---------- CASE 1: YYYY-MM-DD ----------
    if re.match(r"^\d{4}-\d{1,2}-\d{1,2}$", date_str):
        y, m, d = map(int, date_str.split("-"))
        return f"{y:04d}-{m:02d}-{d:02d}"

    # ---------- CASE 2: DD/MM/YY or DD/MM/YYYY ----------
    if "/" in date_str:
        parts = date_str.split("/")
        if len(parts) == 3:
            d, m, y = parts
            d, m, y = int(d), int(m), int(y)
            if y < 100:
                y += 2000
            return f"{y:04d}-{m:02d}-{d:02d}"

    # ---------- CASE 3: DD.MM.YY or DD.MM.YYYY ----------
    if "." in date_str:
        parts = date_str.split(".")
        if len(parts) == 3:
            d, m, y = parts
            d, m, y = int(d), int(m), int(y)
            if y < 100:
                y += 2000
            return f"{y:04d}-{m:02d}-{d:02d}"

    # ---------- CASE 4: DD-MM-YY or DD-MM-YYYY ----------
    if "-" in date_str:
        parts = date_str.split("-")
        if len(parts) == 3 and not re.match(r"^\d{4}-", date_str):
            d, m, y = parts
            d, m, y = int(d), int(m), int(y)
            if y < 100:
                y += 2000
            return f"{y:04d}-{m:02d}-{d:02d}"

    # ---------- CASE 5: Mixed Month + Day + Optional Year ----------
    tokens = date_str.replace(",", "").split()

    # Find month
    month = None
    for t in tokens:
        if t in MONTHS:
            month = MONTHS[t]
            break

    if month:
        # find day (1–31)
        day = None
        for t in tokens:
            if t.isdigit() and 1 <= int(t) <= 31:
                day = int(t)
                break

        # find year ( >31 )
        year = None
        for t in tokens:
            if t.isdigit() and int(t) > 31:
                year = int(t)
                break

        if year is None:
            year = current_year

        if year < 100:
            year += 2000

        if day:
            return f"{year:04d}-{month:02d}-{day:02d}"

    # ---------- CASE 6: Only month → return YYYY-MM-01 ----------
    if date_str in MONTHS:
        return f"{current_year:04d}-{MONTHS[date_str]:02d}-01"

    return None

def parse_prompt(nlp,Prompt):
    tables, dates2dates, words2dates = detect_tables_n_dates(nlp,Prompt)
    standardized_dates2dates = {}
    for t in dates2dates:
        standardized_dates2dates[t] = standardize_date(t)
    standardized_words2dates = {}
    for key, value in words2dates.items():
        standardized_words2dates[key] = standardize_date(value)


    final_dates = {**standardized_dates2dates, **standardized_words2dates}
    return tables, final_dates


# Prompt = input("Enter Prompt:")
Prompt = "How was my hr between 24 nov and 23 nov n this week n yesterday n last week n last month"
tables , dates = parse_prompt(nlp,Prompt)
print(tables, "\n", dates)