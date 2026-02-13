import os, json, urllib.parse, datetime, re
import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from supabase import create_client
from streamlit_navigation_bar import st_navbar
import pages as pg
from datetime import timedelta
import time

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
@st.cache_resource
def get_supabase_client():
    load_dotenv()
    url = os.getenv("url")
    key = os.getenv("key")
    return create_client(url, key)

@st.cache_resource
def get_engine():
    load_dotenv()
    return create_engine(
        f"postgresql+psycopg2://{os.getenv('user')}:{urllib.parse.quote_plus(os.getenv('password'))}@{os.getenv('host')}:{os.getenv('port')}/{os.getenv('dbname')}",
        pool_pre_ping=True,  # checks if connection is alive
        pool_recycle=1800    # recycle every 30 mins
    )


@st.cache_data
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
    },
    "step_daily_trend": {
        "table": "step_daily_trend",
        "columns": ["create_time","day_time","count","speed","distance","calorie","deviceuuid","binning_data"],
        "jsonPath_template": "com.samsung.shealth.step_daily_trend/{0}/{1}"
    },
    "food_intake":{
        "table":"food_intake",
        "columns": ["create_time","name","meal_type","calorie","time_offset","food_info_id","datauuid"],
        "jsonPath_template" : ""
    },
    "sleep":{
        "table":"sleep",
        "columns":["sleep_start_time","sleep_end_time","sleep_time_offset"],
        "jsonPath_template" : ""
    }
}

# -------------------- Warmup --------------------#
@st.cache_resource
def warmup():
    """Load all metrics into session and Supabase client safely."""
    supabase_client = get_supabase_client()
    engine = get_engine()
    
    dataframes = {}
    steps_time_offset = None  # Store steps time offset for calorie
    
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
            # Capture the most common time offset from steps for use with calorie data
            if not df.empty and "step_count_time_offset" in df.columns:
                steps_time_offset = df["step_count_time_offset"].mode()[0] if not df["step_count_time_offset"].mode().empty else df["step_count_time_offset"].iloc[0]
        # Calorie 
        elif metric == "calorie" and "calories_burned_create_time" in df.columns:
            # Add steps time offset to calorie dataframe
            if steps_time_offset is not None:
                df["calorie_time_offset"] = steps_time_offset
            df["localized_time"] = pd.to_datetime(df["calories_burned_create_time"], errors="coerce")
            df["localized_time"] = df.apply(lambda r: apply_offset(r, "calorie_time_offset", "calories_burned_create_time"), axis=1)
            
        # Exercise
        elif metric == "exercise" and "exercise_time_offset" in df.columns and "exercise_start_time" in df.columns:
            df["localized_time"] = df.apply(lambda r: apply_offset(r, "exercise_time_offset", "exercise_start_time"), axis=1)
        elif metric == "food_intake" and "time_offset" in df.columns and "create_time" in df.columns:
            df["localized_time"] = df.apply(lambda r: apply_offset(r, "time_offset","create_time" ), axis=1)
        elif metric == "sleep" and "sleep_time_offset" in df.columns and "sleep_start_time" in df.columns and "sleep_end_time" in df.columns:
            df["localized_start_time"] = df.apply(lambda r: apply_offset(r, "sleep_time_offset","sleep_start_time" ), axis=1)
            df["localized_end_time"] = df.apply(lambda r: apply_offset(r, "sleep_time_offset","sleep_end_time" ), axis=1)

        # -----------------------------------------------------

        dataframes[metric] = df
    
    return supabase_client, dataframes


# -------------------- App --------------------#
class App:
    def __init__(self):
        with st.spinner("Loading Cache...."):
            self.supabase_client, self.dataframes = warmup()
        self.run()
        
    def run(self):
        st.set_page_config(layout='wide', page_title='Athlete Tracker', initial_sidebar_state='collapsed')
        # Inject CSS
        st.markdown(
            """
            <style>
            /* Remove Streamlit top header space */
            header { 
                visibility: hidden; 
                height: 0px;
            }

            /* Remove top padding of main content */
            .block-container {
                padding-top: 0rem !important;
                margin-top: 0rem !important;
                
            }

            /* Remove extra spacing between elements */
            .st-emotion-cache-p6n0jw {
                gap: 0rem !important;
            }
            .st-emotion-cache-1n6tfoc {
                gap: 0rem !important;
            }
            .st-emotion-cache-tn0cau {
                gap: 0.1rem !important;
            }
            /* Remove navbar bottom margin if any */
            nav {
                margin-bottom: 0px !important;
            }
            </style>
            """,
            unsafe_allow_html=True
        )


        # Init session state
        if 'initialized' not in st.session_state:
            for metric in METRICS_CONFIG.keys():
                st.session_state.setdefault(f"{metric}_date_filter", None)
                st.session_state.setdefault(f"{metric}_time_filter", datetime.time(0, 0))
                st.session_state.setdefault(f"df_{metric}_filtered", pd.DataFrame())                
            st.session_state.setdefault("json_cache", {})        # mapping jsonPath -> DataFrame
            st.session_state["initialized"] = True

        # Navigation
        pages = ["Dashboard", "Activity", "Coach"]
        parent_dir = os.path.dirname(os.path.abspath(__file__))
        logo_path = os.path.join(parent_dir, "home_dark.svg")
        styles = {
            "nav": {
                "background-color": "rgba(46, 56, 71, 1)",

            },
            "div": {
                "max-width": "32rem",
                
            },
            "span": {
                "border-radius": "0.5rem",
                "color": "rgb(255, 255, 255)",
                "font-size": "clamp(18px, 1.2vw, 25px)",   
                "text-align":"center",
                "margin": "0 0.125rem",
                "padding": "0.4375rem 0.625rem",
            },
            "active": {
                "background-color": "rgba(255, 255, 255, 0.25)",
            },
            "hover": {
                "background-color": "rgba(255, 255, 255, 0.35)",
            },
        }
        options = {'show_menu': False, 'show_sidebar': False, 'use_padding': False}
        
        page = st_navbar(pages, logo_path=logo_path, styles=styles, options=options)

        functions = {
            'Home': lambda: pg.show_home(
                self.dataframes.get("hr"),
                self.dataframes.get("step_daily_trend"),
                self.dataframes.get("calorie"),
                self.dataframes.get("food_intake"),
                self.dataframes.get("sleep"),
                self.supabase_client

            ),
            'Dashboard': lambda: pg.show_dashboard(
                self.dataframes.get("stress"),
                self.dataframes.get("hr"),
                self.dataframes.get("spo2"),
                self.dataframes.get("steps"),
                self.dataframes.get("calorie"),
                self.supabase_client
            ),
            'Activity': lambda: pg.show_activity(
                self.dataframes.get("exercise"),
                self.dataframes.get("exercise_routine"),
                self.dataframes.get("custom_exercise"),
                self.dataframes.get("inbuilt_exercises"),
                self.supabase_client
            ),
            'Coach': lambda: pg.show_coach(
                self.dataframes.get("stress"),
                self.dataframes.get("hr"),
                self.dataframes.get("spo2"),
                self.dataframes.get("steps"),
                self.dataframes.get("calorie"),
                self.dataframes.get("exercise"),
                self.dataframes.get("exercise_routine"),
                self.dataframes.get("custom_exercise"),
                self.dataframes.get("inbuilt_exercises"),                
                self.supabase_client 
            ),
        }

        go_to = functions.get(page)
        if go_to:
            go_to()

if __name__ == "__main__":
    App()
