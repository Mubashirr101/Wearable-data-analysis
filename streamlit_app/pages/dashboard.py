import streamlit as st
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

    
def show_dashboard():
    with st.spinner('Loading'):
        load_dotenv()
        engine = create_engine(f"postgresql+psycopg2://{os.getenv("user")}:{urllib.parse.quote_plus(os.getenv("password"))}@{os.getenv("host")}:{os.getenv("port")}/{os.getenv("dbname")}") 
        
        p1_tab1,p1_tab2,p1_tab3 = st.tabs(['Stress Graph','Heart-Rate Graph','Steps Graph'])
        with p1_tab1:                
            col1,col2 = st.columns([4,2])
            df_stress = querySupabase(engine,"start_time","score","time_offset","stress","binning_data") 
            df_stress['jsonPath'] = "com.samsung.shealth.stress/" + df_stress['binning_data'].str[0] + "/" + df_stress["binning_data"]                    
            col1.header("📆  Daily Stress Chart")
            stress_date_filter = col2.date_input("stress_Date",value=None,label_visibility='hidden')
            if stress_date_filter:
                df_stress_filtered = df_stress[df_stress["start_time"].dt.date == pd.to_datetime(stress_date_filter).date()].copy()
            else:
                df_stress_filtered = df_stress.iloc[0:0]
            stresschart = chartTimeData(df_stress_filtered,"start_time","score","Time/Date","Stress Level","⚡ Daily Stress Chart") 
            st.altair_chart(stresschart,use_container_width=True)
            ############################################################################                                
            col3,col4 = st.columns([4,2])
            col3.header("⌚  Hourly Stress Chart")
            stress_time_filter = col4.time_input("stress_Time",value=datetime.time(0,0),step = 3600,label_visibility='hidden')
            stess_offset_col = df_stress["time_offset"]                
            stress_jsonFilepath = None
            df_stress_bin = None
            chartStressBin = pd.DataFrame()
            if not df_stress_filtered.empty and stress_time_filter != datetime.time(0,0):
                match = df_stress_filtered.loc[df_stress_filtered['start_time'].dt.time == stress_time_filter]                
                if not match.empty:
                    stress_jsonFilepath = match.iloc[0]['jsonPath']
                    df_stress_bin = loadBinningjsons(stess_offset_col,stress_jsonFilepath)
                    chartStressBin = chartBinningjsons(df_stress_bin,"start_time","Time","score","Stress Level","score_min","score_max")
                else:
                    st.info("No Data found for the selected time.")
            else:
                st.info("Please select a date & time")
                
            st.altair_chart(chartStressBin,use_container_width=True)
        with p1_tab2:      
            col5,col6 = st.columns([4,2])
            df_hr = querySupabase(engine,"heart_rate_start_time","heart_rate_heart_rate","heart_rate_time_offset","tracker_heart_rate","heart_rate_binning_data") 
            df_hr['jsonPath'] = "com.samsung.shealth.tracker.heart_rate/" + df_hr['heart_rate_binning_data'].str[0] + "/" + df_hr["heart_rate_binning_data"]                    
            col5.header("📆  Daily Heart Rate Chart")
            hr_date_filter = col6.date_input("hr_Date",value=None,label_visibility='hidden')
            if hr_date_filter:
                df_hr_filtered = df_hr[df_hr["heart_rate_start_time"].dt.date == pd.to_datetime(hr_date_filter).date()].copy()
            else:
                df_hr_filtered = df_hr.iloc[0:0]
            hrchart = chartTimeData(df_hr_filtered,"heart_rate_start_time","heart_rate_heart_rate","Time/Date","Heart-Rate","🫀 Heart-Rate over Time")               
            st.altair_chart(hrchart,use_container_width=True)
            ############################################################################                                
            col7,col8 = st.columns([4,2])
            col7.header("⌚  Hourly Heart Rate Chart")
            hr_time_filter = col8.time_input("hr_Time",value=datetime.time(0,0),step = 3600,label_visibility='hidden')
            hr_offset_col = df_hr["heart_rate_time_offset"]                
            hr_jsonFilepath = None
            df_hr_bin = None
            chartHRBin = pd.DataFrame()
            if not df_hr_filtered.empty and hr_time_filter != datetime.time(0,0):
                match2 = df_hr_filtered.loc[df_hr_filtered['heart_rate_start_time'].dt.time == hr_time_filter]
                if not match2.empty:
                    hr_jsonFilepath = match2.iloc[0]['jsonPath']
                    df_hr_bin = loadBinningjsons(hr_offset_col,hr_jsonFilepath)
                    chartHRBin = chartBinningjsons(df_hr_bin,"start_time","Time","heart_rate","Heart Rate","heart_rate_min","heart_rate_max")
                else:
                    st.info("No Data found for the selected time.")
            else:
                st.info("Please select a date & time")                    
            st.altair_chart(chartHRBin,use_container_width=True)


def querySupabase(engine,xvar,yvar,offset,table,binningjson):
    query = text(f"SELECT {xvar},{yvar},{offset},{binningjson} FROM {table}")
    with engine.connect() as conn:
        df = pd.read_sql(query,conn,)
    return df
def chartTimeData(df,xval,yval,xtitle,ytitle,chart_title):
    df[xval] = pd.to_datetime(df[xval])
    offset_col = None
    for col in df.columns:
        if "time_offset" in col:
            offset_col = col
            break
    df[xval] = df.apply(lambda row: apply_offset(row,offset_col,xval),axis=1)
    chart = alt.Chart(df).mark_bar().encode(
        alt.X(xval).title(xtitle),
        alt.Y(yval).title(ytitle)
    )
    return chart

def apply_offset(row,offset_col,time_col):
    ## extract offset from the offset feature
    offset_val = row[offset_col]
    if pd.isnull(offset_val):
        return row[offset_col]
    offset_str = str(offset_val)
    match = re.match(r"UTC([+-])(\d{2})(\d{2})",offset_str)
    if match:
        sign,hh,mm = match.groups()
        hours,minutes = int(hh),int(mm)
        delta = timedelta(hours=hours,minutes=minutes)
        if sign == "-":
            delta = -delta
        ## shift time
        return row[time_col]+delta
    return row[time_col]

def loadBinningjsons(offset_col,jsonfilepath):
    url = os.getenv("url")
    key = os.getenv("key")
    supabase = create_client(url,key)
    bucket_name = "json-bucket"
    file_path = jsonfilepath
    res = supabase.storage.from_(bucket_name).download(file_path)
    data = json.loads(res.decode("utf-8"))
    dfjson = pd.DataFrame(data)
    dfjson["start_time"] = pd.to_datetime(dfjson["start_time"],unit="ms")
    dfjson["end_time"] = pd.to_datetime(dfjson["end_time"],unit="ms")
    dfjson["offset_time"] = offset_col
    dfjson["start_time"] = dfjson.apply(lambda row: apply_offset(row,"offset_time","start_time"),axis =1)
    dfjson["end_time"] = dfjson.apply(lambda row: apply_offset(row,"offset_time","end_time"),axis =1)
    dfjson = dfjson.sort_values("start_time")
    return dfjson

def chartBinningjsons(dfJson,xval,xtitle,yval,ytitle,yminval,ymaxval):
    ### viz
    # base line (score)
    line = alt.Chart(dfJson).mark_line(point=True).encode(
        x=alt.X(f"{xval}:T",title = xtitle),
        y=alt.Y(f"{yval}:Q",title = ytitle),
        tooltip = [xval,yval,yminval,ymaxval]
    )
    # shaded minmax region
    band = alt.Chart(dfJson).mark_area(opacity=0.3).encode(
        x=f"{xval}:T",
        y=f"{yminval}:Q",
        y2=f"{ymaxval}:Q"
    )
    #combining
    chartBin = (band + line).properties(
        width = 700,
        height = 400,
    )
    return chartBin

