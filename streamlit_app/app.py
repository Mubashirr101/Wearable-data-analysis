import streamlit as st
import pandas as pd
import numpy as np
import os,json
import datetime
import urllib.parse
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
import re
from datetime import timedelta
import altair as alt
from supabase import create_client
from streamlit_navigation_bar import st_navbar
import pages as pg
class App:
    def __init__(self):
        self.run()
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
            'Dashboard':pg.show_dashboard,
            'Activity':pg.show_activity,
            'Coach':pg.show_coach,
            'More':pg.show_more,
        }

        go_to = functions.get(page)
        if go_to:
            go_to()       


if __name__ == "__main__":
    App()

