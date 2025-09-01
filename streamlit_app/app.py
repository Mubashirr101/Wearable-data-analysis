import streamlit as st
import streamlit as st
import pandas as pd
import numpy as np
import os,json
import urllib.parse
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from supabase import create_client
from streamlit_navigation_bar import st_navbar
import pages as pg 
import datetime
# -------------------- Cache -----------------------#
@st.cache_resource
def get_supabase_client():
    load_dotenv()
    url = os.getenv("url")
    key = os.getenv("key")
    return create_client(url, key)

def querySupabase(engine,xvar,yvar,offset,table,binningjson):
        query = text(f"SELECT {xvar},{yvar},{offset},{binningjson} FROM {table}")
        with engine.connect() as conn:
            df = pd.read_sql(query,conn,)
        return df

@st.cache_data
def get_stress_df():
    engine = get_engine()
    df_stress = querySupabase(engine,"start_time","score","time_offset","stress","binning_data") 
    df_stress['jsonPath'] = "com.samsung.shealth.stress/" + df_stress['binning_data'].str[0] + "/" + df_stress["binning_data"]
    return df_stress

@st.cache_data
def get_hr_df():
    engine = get_engine()
    df_hr = querySupabase(engine,"heart_rate_start_time","heart_rate_heart_rate","heart_rate_time_offset","tracker_heart_rate","heart_rate_binning_data") 
    df_hr['jsonPath'] = "com.samsung.shealth.tracker.heart_rate/" + df_hr['heart_rate_binning_data'].str[0] + "/" + df_hr["heart_rate_binning_data"] 
    return df_hr

@st.cache_resource
def get_engine():
    load_dotenv()
    return create_engine(
        f"postgresql+psycopg2://{os.getenv("user")}:{urllib.parse.quote_plus(os.getenv("password"))}@{os.getenv("host")}:{os.getenv("port")}/{os.getenv("dbname")}"
    )

# ---------------------- warmup -------------------------#
@st.cache_resource
def warmup():
    """"Force all heavy cached resources to load once at startup."""
    supabase_client = get_supabase_client()
    stress_df = get_stress_df()
    hr_df = get_hr_df()
    return supabase_client,stress_df,hr_df
    
session = st.session_state
for k in session.keys():
    session[k] = session[k]
class App:
    def __init__(self):
        with st.spinner("Loading Cache...."):
            self.supabase_client,self.stress_df,self.hr_df = warmup()
        self.run()    
        
    def run(self):
        st.set_page_config(layout='wide',page_title='Athlete Tracker',initial_sidebar_state='collapsed')
        if 'initialized' not in st.session_state:
            st.session_state.setdefault("stress_date_filter", None)
            st.session_state.setdefault("stress_time_filter", datetime.time(0, 0))
            st.session_state.setdefault("hr_date_filter", None)
            st.session_state.setdefault("hr_time_filter", datetime.time(0, 0))
            # caches
            st.session_state.setdefault("df_stress_filtered", pd.DataFrame())
            st.session_state.setdefault("df_hr_filtered", pd.DataFrame())
            st.session_state.setdefault("json_cache", {})        # mapping jsonPath -> DataFrame
            st.session_state.setdefault("last_stress_bin_df", None)
        #     st.session_state.setdefault("last_hr_bin_df", None)
            st.session_state["initialized"] = True

        pages = ["Dashboard","Activity","Coach","More","Github"]
        parent_dir = os.path.dirname(os.path.abspath(__file__))
        logo_path = os.path.join(parent_dir,"home_light.svg")
        urls = {"Github":"https://github.com/Mubashirr101/Wearable-data-analysis"}
        styles = {
            'nav': {
                'background-color':'#2E3847',
                'justify-content' : 'left',
                'margin-bottom' : '1px',
            },
            'img': {
                'margin-left':'25px',
                'margin-right':'300px',
                'padding-right' :'13px',
            },
            'span': {
                'color' : 'white',
                'padding': '10px'
                
            },
            'active' : {
                'background-color':'#4A5970',
                'color':'white',
                'font-weight':'normal',
                'padding':'14px'
            }
        }

        options = {
            'show_menu' : False,
            'show_sidebar':False,
        }

        page = st_navbar(
            pages,
            logo_path = logo_path,
            styles= styles,
            urls=urls,
            options=options,
        )

        functions = {
            'Home': pg.show_home,
            'Dashboard':lambda: pg.show_dashboard(self.stress_df,self.hr_df,self.supabase_client),
            'Activity':pg.show_activity,
            'Coach':pg.show_coach,
            'More':pg.show_more,
        }

        go_to = functions.get(page)
        if go_to:
            go_to()       


if __name__ == "__main__":
    App()

