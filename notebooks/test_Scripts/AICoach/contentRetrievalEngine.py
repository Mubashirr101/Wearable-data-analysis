import os, json, urllib.parse, datetime, re
import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from supabase import create_client
from streamlit_navigation_bar import st_navbar
from datetime import timedelta
import time
import spacy
import dateparser
from dateparser.search import search_dates
import re
from datetime import datetime

nlp = spacy.load("en_core_web_sm")
#####################################################################

def apply_offset(row, offset_col, time_col):
    offset_val = row[offset_col]
    if pd.isnull(offset_val):
        return row[time_col]
    offset_str = str(offset_val)
    match = None
    # Accept both "UTC+0530" and "+05:30" formats
    if offset_str.startswith("UTC"):
        match = re.match(r"UTC([+-])(\d{2})(\d{2})", offset_str)
    else:
        match = re.match(r"([+-])(\d{2}):?(\d{2})", offset_str)
    if match:
        sign, hh, mm = match.groups()
        hours, minutes = int(hh), int(mm)
        delta = timedelta(hours=hours, minutes=minutes)
        if sign == "-":
            delta = -delta
        return row[time_col] + delta
    return row[time_col]

# -------------------- Cache -----------------------#
def get_supabase_client():
    load_dotenv()
    url = os.getenv("url")
    key = os.getenv("key")
    return create_client(url, key)

def get_engine():
    load_dotenv()
    return create_engine(
        f"postgresql+psycopg2://{os.getenv('user')}:{urllib.parse.quote_plus(os.getenv('password'))}@{os.getenv('host')}:{os.getenv('port')}/{os.getenv('dbname')}",
        pool_pre_ping=True,  # checks if connection is alive
        pool_recycle=1800    # recycle every 30 mins
    )

def querySupabase(_engine, table: str, columns: list, retries=3):
    #Query Supabase/Postgres with retry logic.
    cols_str = ",".join(columns)
    query = text(f"SELECT {cols_str} FROM {table}")
    
    for attempt in range(retries):
        try:
            with _engine.connect() as conn:
                df = pd.read_sql(query, conn)
                return df
        except Exception as e:
            if attempt < retries - 1:
                st.warning(f"Query failed, retryingg... ({attempt + 1}/{retries}) — {e}")                
                time.sleep(2)
            else:
                st.error(f"Query failed after {retries} attempts: {e}")
                raise e

# -------------------- Metric Config --------------------#
METRICS_CONFIG = {
    "stress": {
        "table": "stress",
        "columns": ["start_time", "score","min","max", "time_offset", "binning_data"],
        "jsonPath_template": "com.samsung.shealth.stress/{0}/{1}",
    },
    "hr": {
        "table": "tracker_heart_rate",
        "columns": ["heart_rate_start_time", "heart_rate_heart_rate", "heart_rate_min", "heart_rate_max", "heart_rate_time_offset", "heart_rate_heart_beat_count", "heart_rate_deviceuuid", "heart_rate_binning_data"],
        "jsonPath_template": "com.samsung.shealth.tracker.heart_rate/{0}/{1}",
    },
    "spo2": {
        "table": "tracker_oxygen_saturation",
        "columns": ["oxygen_saturation_start_time", "oxygen_saturation_spo2","oxygen_saturation_heart_rate", "oxygen_saturation_time_offset", "oxygen_saturation_binning"],
        "jsonPath_template": "com.samsung.shealth.tracker.oxygen_saturation/{0}/{1}",
    },
    "steps": {
        "table": "tracker_pedometer_step_count",
        "columns": ["step_count_start_time", "step_count_count","run_step","walk_step","step_count_speed","step_count_distance","step_count_calorie", "step_count_time_offset"],
        "jsonPath_template": "",
    },
    "calorie": {
        "table": "calories_burned_details",
        "columns": ["calories_burned_day_time","calories_burned_create_time","active_calories_goal","total_exercise_calories","calories_burned_tef_calorie","calories_burned_active_time","calories_burned_rest_calorie","calories_burned_active_calorie", "extra_data"],
        "jsonPath_template": "com.samsung.shealth.calories_burned.details/{0}/{1}",
    },
    "exercise":{
        "table":"exercise",
        "columns": ["exercise_start_time","live_data_internal","routine_datauuid","custom_id","exercise_duration","exercise_calorie","exercise_max_heart_rate","exercise_min_heart_rate","exercise_mean_heart_rate","activity_type","exercise_exercise_type","exercise_count","exercise_time_offset","exercise_live_data"],
        "jsonPath_template": "com.samsung.shealth.exercise/{0}/{1}",        
    },
    "exercise_routine":{
        "table":"exercise_routine",
        "columns":["datauuid","custom_id","total_calorie","activities"],
        "jsonPath_template": "com.samsung.shealth.exercise.routine/{0}/{1}",        
    },
    "custom_exercise":{
        "table":"exercise_custom_exercise",
        "columns":["custom_name","datauuid","custom_id","custom_type","preference"],
        "jsonPath_template": "com.samsung.shealth.exercise.custom_exercise/{0}/{1}",                
    },
    "inbuilt_exercises": {
    "table": "inbuilt_exercises",
    "columns":["exercise_type","exercise_name"],
    "jsonPath_template" : ""
    }
}

# -------------------- Warmup --------------------#
def warmup():
    """Load all metrics into session and Supabase client safely."""
    supabase_client = get_supabase_client()
    engine = get_engine()
    
    dataframes = {}
    
    def safe_jsonpath(val, template):
        """Generate jsonPath safely for binning columns."""
        if pd.isna(val) or val == "":
            return ""
        val_str = str(val)
        first_char = val_str[0] if len(val_str) > 0 else ""
        return template.format(first_char, val)
    
    for metric, cfg in METRICS_CONFIG.items():
        # Query columns
        df = querySupabase(engine, cfg["table"], cfg["columns"])
        
        # Add jsonPath column if template exists
        if metric == 'exercise':
            if cfg["jsonPath_template"]:
                bin_col1 = 'exercise_live_data'
                bin_col2 = 'live_data_internal'
                df['jsonPath_LiveData'] = df[bin_col1].apply(lambda x: safe_jsonpath(x, cfg["jsonPath_template"]))
                df['jsonPath_LiveInternal'] = df[bin_col2].apply(lambda x: safe_jsonpath(x, cfg["jsonPath_template"]))            
            else:
                df['jsonPath_LiveData'] = ""
                df['jsonPath_LiveInternal'] = ""
        elif metric == 'exercise_routine':
            if cfg["jsonPath_template"]:
                bin_col1 = 'activities'
                df['jsonPath_activities'] = df[bin_col1].apply(lambda x: safe_jsonpath(x, cfg["jsonPath_template"]))
            else:
                df['jsonPath_activities'] = ""
        elif metric == 'custom_exercise':
            if cfg["jsonPath_template"]:
                bin_col1 = 'preference'
                df['jsonPath_preference'] = df[bin_col1].apply(lambda x: safe_jsonpath(x, cfg["jsonPath_template"]))
            else:
                df['jsonPath_preference'] = ""                
        else:
            if cfg["jsonPath_template"]:
                bin_col = df.columns[-1]  # assume last column is the binning column
                df['jsonPath'] = df[bin_col].apply(lambda x: safe_jsonpath(x, cfg["jsonPath_template"]))
            else:
                df['jsonPath'] = ""

        # ----------- Apply offset ONCE per metric -----------
        # Stress
        if metric == "stress" and "time_offset" in df.columns and "start_time" in df.columns:
            df["localized_time"] = df.apply(lambda r: apply_offset(r, "time_offset", "start_time"), axis=1)
        # Heart Rate
        elif metric == "hr" and "heart_rate_time_offset" in df.columns and "heart_rate_start_time" in df.columns:
            df["localized_time"] = df.apply(lambda r: apply_offset(r, "heart_rate_time_offset", "heart_rate_start_time"), axis=1)
        # SpO2
        elif metric == "spo2" and "oxygen_saturation_time_offset" in df.columns and "oxygen_saturation_start_time" in df.columns:
            df["localized_time"] = df.apply(lambda r: apply_offset(r, "oxygen_saturation_time_offset", "oxygen_saturation_start_time"), axis=1)
        # Steps
        elif metric == "steps" and "step_count_time_offset" in df.columns and "step_count_start_time" in df.columns:
            df["localized_time"] = df.apply(lambda r: apply_offset(r, "step_count_time_offset", "step_count_start_time"), axis=1)
        # Calorie 
        elif metric == "calorie" and "calories_burned_day_time" in df.columns:
            df["localized_time"] = pd.to_datetime(df["calories_burned_day_time"], errors="coerce")
        # Exercise
        elif metric == "exercise" and "exercise_time_offset" in df.columns and "exercise_start_time" in df.columns:
            df["localized_time"] = df.apply(lambda r: apply_offset(r, "exercise_time_offset", "exercise_start_time"), axis=1)
        # -----------------------------------------------------

        dataframes[metric] = df
    
    return supabase_client, dataframes

############################################################################


def detect_tables_n_dates(nlp,text):
    #keywords : Data,Time,Filter
    Keywords_Table = { "stress": ["stress", "stress level", "stress score", "tension", "anxiety", "strain", "mental load", "stress pattern", "stress zones", "stress chart", "vitals"],
        "hr":["heart rate", "hr", "bpm", "resting heart rate", "max heart rate", "pulse","cardio", "hr zone", "heart beat", "heart-rate","heart", "vitals"],
        "spo2":["spo2", "oxygen", "blood oxygen", "oxygen saturation", "o2 level","breathing", "respiration", "air levels", "oxygen dips", "oxygen score", "vitals"],
        "steps":["steps", "step count", "walking", "walk", "daily steps", "distance walked","movement", "stride", "pedometer", "step goal"],
        "calorie": ["calories", "calorie burn", "energy burn", "burned", "metabolism","active calories", "basal calories", "kcal", "energy expenditure", "fat burn","cal", "vitals"],
        "exercise": ["exercise", "workout", "training", "session", "sports", "activity","reps", "sets", "routine", "intensity","activities"],    
        }
    text = text.lower()    
    doc = nlp(text)
    words_to_dates = {}
    dates_total = []
    table_list =[]
    table_word = "" ## to make sure the table name isnt accidently used as a date
    for word in text.split(" "):
        for table , keys in Keywords_Table.items():
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
    dp_res = search_dates(text,languages=["en"])
    if dp_res:
        for phrase, dt in dp_res:
            if phrase not in table_word:
                words_to_dates[phrase] = dt

    ###########################################################
    ##REGEX
    MONTHS = r"(?:january|february|march|april|may|june|july|august|september|october|november|december|jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)"


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
    for k , v in words_to_dates.items():
        date_only = v.date() # removing hr/min/secs
        if date_only not in seen_dates:
            new_words_2_date_dict[k] = v
            seen_dates.add(date_only)

    return table_list,dates_regex,new_words_2_date_dict

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





# removing old start_time and adding the localized time as start_time
# removing unnecessary cols from the tables (jsonPath, binning, time offset)
def clean_raw_df(raw_dataframes):
    df = raw_dataframes
    for key, value in df.items():
        value = value.loc[:,~value.columns.str.contains("start_time")]
        value = value.loc[:,~value.columns.str.contains("time_offset")]
        value = value.loc[:,~value.columns.str.contains("jsonPath")]
        value = value.loc[:,~value.columns.str.contains("binning")]
        value = value.loc[:,~value.columns.str.contains("uuid")]
        value = value.loc[:,~value.columns.str.contains("live_data")]
        

        value = value.rename(columns= lambda c: "start_time" if "localized_time" in c else c)
        cols = value.columns.tolist()
        if "start_time" in cols:
            cols.insert(0, cols.pop(cols.index("start_time")))
            value = value[cols]
        df[key] = value
    
    return df


    ## Now we take the 'phrase : date' pair and create context for filtering the detected tables

def filter_df(dfs,type,date = None,start_date=None,end_date=None):
    filtered_dfs = {}
    if date:
        target_date = pd.to_datetime(date).date()
        target_iso_year, target_iso_week, _ = target_date.isocalendar()
    for table_name, table in dfs.items():
        if type == "range":
            df_filtered = table[(table["start_time"] >= start_date) & (table["start_time"] <= end_date)]
        elif type == "day":
            df_filtered = table[table["start_time"].dt.date == target_date]
        elif type == "week":
            df_filtered = table[(table["start_time"].dt.isocalendar().year == target_iso_year) & (table["start_time"].dt.isocalendar().week == target_iso_week)]
        elif type == "month":
            df_filtered = table[(table["start_time"].dt.year == target_date.year) & (table["start_time"].dt.month == target_date.month)]            
        filtered_dfs[table_name] = df_filtered

    return filtered_dfs    

#############################################################
def fetch_dfs(df,Prompt,tables,phrase_date_pair):
    ## cases:
    ## case 1: data for one or more date to be fetched (all dates which are specified) eg: 24 nov, yesterday
    ## case 2: data for one or more week to be fetched (all dates which are specified) eg: last week, this week
    ## case 3: data for one or more month to be fetched (all months which are specified) eg : aug, last month, this month
    ## case 4: a range of data from one date to another is to be fetched (both dates which are specified) eg: [23 nov, 30 nov], [1 aug, 18 aug]

    # logic: 
    # for fetching dates: check for patterns in phrases like : 24 nov, yesterday, today
    # for fetching weeks: check for patterns in phrases like : last week, this week
    # for fetching months: check for patterns in phrases like: month names 
    # for fetching range: check for keywords in received prompt like: from .. to .. 

    # phrases
    pattern = r"\b\d{1,2}\s+(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec|january|february|march|april|june|july|august|september|october|november|december)\b"
    phrases = ["yesterday","today"]
    # month_patterns = r"(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec|january|february|march|april|may|june|july|august|september|october|november|december)"

    month_patterns = r"(?:january|february|march|april|may|june|july|august|september|october|november|december|jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)"
    range_pattern = rf"from\s+((?:\d{{1,2}}(?:st|nd|rd|th)?\s+)?{month_patterns})\s+to\s+((?:\d{{1,2}}(?:st|nd|rd|th)?\s+)?{month_patterns})"


    # dataframes -> df
    specified_dfs = {}
    for table in tables:
        if table in df:
            specified_dfs[table] = df[table] 

    r = re.search(range_pattern, Prompt, re.IGNORECASE)
    # check for ranged filtering (from {date} to {date} )
    if r:
        # print('range found:',r.group(0))  
        start_date = phrase_date_pair[r.group(1)] # from date
        end_date = phrase_date_pair[r.group(2)]  # to date
        # now fetch all the entries that between from date and to date    
        filtered_dfs = filter_df(specified_dfs,"range",start_date=start_date,end_date=end_date)
    else:
        # check for other non-ranged filtering like days,weeks n monthss
        for key, value in phrase_date_pair.items():
            if re.fullmatch(pattern, key.lower()) or key in phrases:
                print(f'fetch a day: {key} -> {value}') 
                # now fetch all the entries matching this date 
                filtered_dfs = filter_df(specified_dfs,"day",date=value)        
            elif 'week' in key:
                print('fetch a week:',{key} ,'->', {value})
                # now fetch all the entries present on this dates week
                filtered_dfs = filter_df(specified_dfs,"week",date=value)        

            elif 'month' in key or re.fullmatch(month_patterns, key.lower()):
                print('fetch a month:',{key} ,'->', {value})
                # now fetch all the entries matching this dates month
                filtered_dfs = filter_df(specified_dfs,"month",date=value)   

    return filtered_dfs 







supabase_client, dataframes = warmup()
# dataframes = None # this will be the fetch raw df from app.py
# Prompt = input("Enter Prompt:")
Prompt = "vitals , steps n exercise at 6 october "
tables , phrase_date_pair = parse_prompt(nlp,Prompt)
# print(tables, "\n", phrase_date_pair)
cleaned_dfs = clean_raw_df(dataframes)
print(fetch_dfs(cleaned_dfs,Prompt,tables,phrase_date_pair))
