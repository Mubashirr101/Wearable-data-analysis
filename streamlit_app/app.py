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
        engine = create_engine(f"postgresql+psycopg2://{os.getenv("user")}:{urllib.parse.quote_plus(os.getenv("password"))}@{os.getenv("host")}:{os.getenv("port")}/{os.getenv("dbname")}")        
        # make tabs
        tab1,tab2 = st.tabs(['Stress Graph','Heart-Rate Graph'])        
        with tab1:
            df_stress = self.querySupabase(engine,"start_time","score","time_offset","stress","2025-08-17") 
            stresschart = self.chartTimeData(df_stress,"start_time","score","Time/Date","Stress Level","⚡ Stress Level over Time") 
            st.altair_chart(stresschart,use_container_width=True)
        with tab2:
            df_hr = self.querySupabase(engine,"heart_rate_end_time","heart_rate_heart_rate","heart_rate_time_offset","tracker_heart_rate","2025-08-17") 
            hrchart = self.chartTimeData(df_hr,"heart_rate_end_time","heart_rate_heart_rate","Time/Date","Heart-Rate","🫀 Heart-Rate over Time") 
            st.altair_chart(hrchart,use_container_width=True)
                
    def querySupabase(self,engine,xvar,yvar,offset,table,datepattern):
        query = text(f"SELECT {xvar},{yvar},{offset} FROM {table} WHERE {xvar}:: text LIKE :date_pattern")
        with engine.connect() as conn:
            df = pd.read_sql(query,conn,params={"date_pattern":f"{datepattern}%"})
        return df
    def chartTimeData(self,df,xval,yval,xtitle,ytitle,chart_title):
        df[xval] = pd.to_datetime(df[xval])
        offset_col = None
        for col in df.columns:
            if "time_offset" in col:
                offset_col = col
                break
        df["localized_time"] = df.apply(lambda row: self.apply_offset(row,offset_col,xval),axis=1)
        chart = alt.Chart(df).mark_bar().encode(
            alt.X("localized_time").title(xtitle),
            alt.Y(yval).title(ytitle)
        ).properties(
            title = chart_title
        )
        return chart






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

