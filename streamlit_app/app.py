import os, json, urllib.parse, datetime
import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from supabase import create_client
from streamlit_navigation_bar import st_navbar
import pages as pg
import time

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
                st.warning(f"Query failed, retrying... ({attempt + 1}/{retries})")
                import time; time.sleep(2)
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
}

# -------------------- Warmup --------------------#
@st.cache_resource
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
        if cfg["jsonPath_template"]:
            bin_col = df.columns[-1]  # assume last column is the binning column
            df['jsonPath'] = df[bin_col].apply(lambda x: safe_jsonpath(x, cfg["jsonPath_template"]))
        else:
            df['jsonPath'] = ""
        
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
            """<style>
            .block-container {padding-top: 0rem !important; margin-top: 0rem !important;}
            .st-emotion-cache-p6n0jw {gap: 0rem !important;}
            </style>""",
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
        pages = ["Dashboard", "Activity", "Coach", "More", "Github"]
        parent_dir = os.path.dirname(os.path.abspath(__file__))
        logo_path = os.path.join(parent_dir, "home_light.svg")
        urls = {"Github": "https://github.com/Mubashirr101/Wearable-data-analysis"}
        styles = {'nav': {'background-color':'#2E3847','justify-content':'left','margin-bottom':'1px'}}
        options = {'show_menu': False, 'show_sidebar': False}
        
        page = st_navbar(pages, logo_path=logo_path, styles=styles, urls=urls, options=options)

        functions = {
            'Home': pg.show_home,
            'Dashboard': lambda: pg.show_dashboard(
                self.dataframes.get("stress"),
                self.dataframes.get("hr"),
                self.dataframes.get("spo2"),
                self.dataframes.get("steps"),
                self.dataframes.get("calorie"),
                self.supabase_client
            ),
            'Activity': pg.show_activity,
            'Coach': pg.show_coach,
            'More': pg.show_more,
        }

        go_to = functions.get(page)
        if go_to:
            go_to()

if __name__ == "__main__":
    App()
