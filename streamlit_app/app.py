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

class App:
    def __init__(self):
        self.stress_df, self.hr_df, self.supabase_client = self.loadCache()
        self.run()
    def loadCache(self):
        with st.spinner('Loading Cache'):
            load_dotenv()
            engine = create_engine(f"postgresql+psycopg2://{os.getenv("user")}:{urllib.parse.quote_plus(os.getenv("password"))}@{os.getenv("host")}:{os.getenv("port")}/{os.getenv("dbname")}") 
            # gets stress data
            df_stress = self.querySupabase(engine,"start_time","score","time_offset","stress","binning_data") 
            df_stress['jsonPath'] = "com.samsung.shealth.stress/" + df_stress['binning_data'].str[0] + "/" + df_stress["binning_data"]

            # gets HR data
            df_hr = self.querySupabase(engine,"heart_rate_start_time","heart_rate_heart_rate","heart_rate_time_offset","tracker_heart_rate","heart_rate_binning_data") 
            df_hr['jsonPath'] = "com.samsung.shealth.tracker.heart_rate/" + df_hr['heart_rate_binning_data'].str[0] + "/" + df_hr["heart_rate_binning_data"] 

            # making supabase client to fetch jsons
            url = os.getenv("url")
            key = os.getenv("key")
            supabase = create_client(url,key)

        return df_stress,df_hr,supabase

    def querySupabase(self,engine,xvar,yvar,offset,table,binningjson):
        query = text(f"SELECT {xvar},{yvar},{offset},{binningjson} FROM {table}")
        with engine.connect() as conn:
            df = pd.read_sql(query,conn,)
        return df
        
    def run(self):
        st.set_page_config(layout='wide',page_title='Athlete Tracker',initial_sidebar_state='collapsed')
        pages = ["Dashboard","Activity","Coach","More","Github"]
        parent_dir = os.path.dirname(os.path.abspath(__file__))
        logo_path = os.path.join(parent_dir,"home_light.svg")
        urls = {"Github":"https://github.com/Mubashirr101/Wearable-data-analysis"}
        styles = {
            'nav': {
                'background-color':'#2E3847',
                'justify-content' : 'left',
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

