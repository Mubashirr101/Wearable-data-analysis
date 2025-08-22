import streamlit as st
import pandas as pd
import numpy as np
import os
import urllib.parse
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
import re
from datetime import timedelta
import altair as alt

class app:
    def __init__(self):
        load_dotenv()
        st.title("Athlete Fitness Tracker")
        #sqlalchemy engine syntax --> "postgresql+psycopg2://user:pass@host:port/dbname"
        engine = create_engine(f"postgresql+psycopg2://{os.getenv("user")}:{urllib.parse.quote_plus(os.getenv("password"))}@{os.getenv("host")}:{os.getenv("port")}/{os.getenv("dbname")}")
        query = text("SELECT start_time,score,time_offset FROM stress WHERE start_time:: text LIKE :date_pattern")
        with engine.connect() as conn:
            strs_df = pd.read_sql(query,conn,params={"date_pattern":"2025-08-17%"}) 
        strs_df["start_time"] = pd.to_datetime(strs_df["start_time"])
        offset_col = None
        for col in strs_df.columns:
            if "time_offset" in col:
                offset_col = col
                break
        strs_df["start_time_local"] = strs_df.apply(lambda row:self.apply_offset(row,offset_col,"start_time"),axis=1)
        chart = alt.Chart(strs_df).mark_bar().encode(
            x="start_time_local:T",
            y="score:Q"
        ).properties(
            title = "stress level over time"
        )
        
        query2 = text("SELECT heart_rate_end_time,heart_rate_heart_rate,heart_rate_time_offset FROM tracker_heart_rate WHERE heart_rate_end_time:: text LIKE :date_pattern")
        with engine.connect() as conn:
            hr_df = pd.read_sql(query2,conn,params={"date_pattern":"2025-08-17%"}) 
        hr_df["heart_rate_end_time"] = pd.to_datetime(hr_df["heart_rate_end_time"])
        offset_col2 = None
        for col in hr_df.columns:
            if "time_offset" in col:
                offset_col2 = col
                break
        hr_df["heart_rate_end_time_local"] = hr_df.apply(lambda row: self.apply_offset(row,offset_col2,"heart_rate_end_time"),axis=1)

        chart2 = alt.Chart(hr_df).mark_bar().encode(
                    x="heart_rate_end_time_local:T",
                    y="heart_rate_heart_rate:Q"
                ).properties(
                    title = "hr level over time"
                )
        with st.expander("Stress Level"):
            st.altair_chart(chart,use_container_width=True)
        with st.expander("HeartRate"):
            st.altair_chart(chart2,use_container_width=True)
            



    def apply_offset(self,row,offset_col,time_col):
        ## extract offset from the offset feature
        match = re.match(r"UTC([+-])(\d{2})(\d{2})",row[offset_col])
        if match:
            sign,hh,mm = match.groups()
            hours,minutes = int(hh),int(mm)
            delta = timedelta(hours=hours,minutes=minutes)
            if sign == "-":
                delta = -delta
            ## shift time
            return row[time_col]+delta
        return row[time_col]



if __name__ == "__main__":
    app()

