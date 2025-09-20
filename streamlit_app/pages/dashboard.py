import streamlit as st
import streamlit as st
import pandas as pd
import numpy as np
import os,json
import datetime
import re
from datetime import timedelta
import altair as alt

session = st.session_state
for k in session.keys():
    session[k] = session[k]


def render_metric_tab(tab,metric_name,df,config,supabase_client=None):
    with tab:
        col1,col2 = st.columns([4,2])
        col1.header(f"{config['daily_icon']} Daily {config['title']} Chart")

        #date inpt
        date_filter = col2.date_input(
            f'{metric_name}_Date',
            key = f"{metric_name}_date_filter",
            label_visibility="hidden"
        )

        if date_filter:
            df_filtered = df[df[config["start_time"]].dt.date == pd.to_datetime(date_filter).date()].copy()
            st.session_state[f"df_{metric_name}_filtered"] = df_filtered
        else:
            df_filtered = df.iloc[0:0]

        chart_type_map = {
            'hr': 'hr',
            'stress': 'stress',
            'spo2': 'spo2',
            'steps': 'steps',
            'calorie': 'calorie'
        }

        
        # Daily chart
        chart_daily = chartTimeData(
            df_filtered,
            config["start_time"],
            config["value"],
            "Time/Date",
            config["y_label"],
            f"{config['daily_icon']} {config['title']} over Time",
            chart_type=chart_type_map.get(metric_name,'line')
        )

        st.altair_chart(chart_daily,use_container_width=True)

        if "jsonPath" in df_filtered.columns:            
            # Huurly chart
            col3, col4 = st.columns([4, 2])
            col3.header(f"{config['hourly_icon']}  Hourly {config['title']} Chart")
            time_filter = col4.time_input(
                f"{metric_name}_Time",
                key=f"{metric_name}_time_filter",
                step=3600,
                label_visibility="hidden"
            )

            jsonFilepath = None
            df_bin = None
            chartBin = pd.DataFrame()

            if not df_filtered.empty and time_filter != datetime.time(0, 0):
                match = df_filtered.loc[df_filtered[config["start_time"]].dt.time == time_filter]
                if not match.empty:
                    jsonFilepath = match.iloc[0]['jsonPath']
                    # cache json
                    json_cache = st.session_state.setdefault("json_cache", {})
                    if jsonFilepath in json_cache:
                        df_bin = json_cache[jsonFilepath]
                    else:
                        with st.spinner(f"Fetching {config['title']} details..."):
                            df_bin = loadBinningjsons(df[config["time_offset"]], jsonFilepath, supabase_client)
                            json_cache[jsonFilepath] = df_bin

                    st.session_state[f"last_{metric_name}_bin_df"] = df_bin
                    chartBin = chartBinningjsons(
                        df_bin,
                        "start_time",
                        "Time",
                        config["value_bin"],
                        config["y_label"],
                        config["min"],
                        config["max"]
                    )
                else:
                    st.info("No Data found for the selected time.")
            else:
                st.info("Please select a date & time")

            # Session state save
            if f"{metric_name}_chartBin" not in st.session_state:
                st.session_state[f"{metric_name}_chartBin"] = pd.DataFrame()

            st.session_state[f"{metric_name}_chartBin"] = chartBin
            st.altair_chart(st.session_state[f"{metric_name}_chartBin"], use_container_width=True)
        else:
            st.info("No binning data available")


        
    
############ MAIN DASHBOARD #############
def show_dashboard(df_stress,df_hr,df_spo2,df_steps,supabase_client):
    p1_tab1,p1_tab2,p1_tab3,p1_tab4,p1_tab5 = st.tabs(['Stress Graph','Heart-Rate Graph','SpO2 Graph','Steps Graph','Calorie Graph'])

    configs = {
        "stress": {
            "title": "Stress",
            "daily_icon": "📆🧠",
            "hourly_icon": "⌚🧠",
            "start_time": "start_time",
            "time_offset": "time_offset",
            "value": "score",
            "value_bin": "score",
            "y_label": "Stress Level",
            "min": "score_min",
            "max": "score_max"
        },
        "hr": {
            "title": "Heart Rate",
            "daily_icon": "📆🫀",
            "hourly_icon": "⌚🫀",
            "start_time": "heart_rate_start_time",
            "time_offset": "heart_rate_time_offset",
            "value": "heart_rate_heart_rate",
            "value_bin": "heart_rate",
            "y_label": "Heart Rate",
            "min": "heart_rate_min",
            "max": "heart_rate_max"
        },
        "spo2": {
            "title": "SpO₂",
            "daily_icon": "📆🩸",
            "hourly_icon": "⌚🩸",
            "start_time": "oxygen_saturation_start_time",
            "time_offset": "oxygen_saturation_time_offset",
            "value": "oxygen_saturation_spo2",
            "value_bin": "spo2",
            "y_label": "SpO₂",
            "min": "spo2_min",
            "max": "spo2_max"
        },
        "steps":{
            "title": "Steps",
            "daily_icon": "📆👟",
            "hourly_icon": "⌚👟",
            "start_time": "step_count_start_time",
            "time_offset": "step_count_time_offset",
            "value": "step_count_count",
            "value_bin": "steps",
            "y_label": "Steps",
            "min": "steps_min",
            "max": "steps_max"
        }
        # to add steps, calorie later with same structure
    }

    render_metric_tab(p1_tab1,"stress",df_stress,configs["stress"],supabase_client)
    render_metric_tab(p1_tab2,"hr",df_hr,configs["hr"],supabase_client)
    render_metric_tab(p1_tab3,"spo2",df_spo2,configs["spo2"],supabase_client)
    render_metric_tab(p1_tab4,"steps",df_steps,configs["steps"],supabase_client)
    # to add steps and cals


def chartTimeData(df,xval,yval,xtitle,ytitle,chart_title,chart_type="line"):

    if df.empty:
        df = pd.DataFrame({xval :[],yval:[]})

    #date time conversion
    df[xval] = pd.to_datetime(df[xval],errors ="coerce")
    # detect offset colmn
    offset_col = None
    for col in df.columns:
        if "time_offset" in col:
            offset_col = col
            break
    if offset_col and not df.empty:
        df[xval] = df.apply(lambda row: apply_offset(row,offset_col,xval),axis=1)
    
    # base date
    if df[xval].notna().any():
        base_date = df[xval].dt.date.min()
    else:
        base_date = datetime.date.today()

    # force xaxis domain from 6:00 to 24
    x_domain = [
        datetime.datetime.combine(base_date, datetime.time(0,0)),
        datetime.datetime.combine(base_date, datetime.time(23,59,59))
    ]

    # chart type
    if chart_type == "hr":
        base = alt.Chart(df).encode(
            x=alt.X(xval, title=xtitle, scale=alt.Scale(domain=x_domain))
        )
        line = base.mark_line(point=True, color="red").encode(
            y=alt.Y(yval, title=ytitle),
            tooltip=[xval, yval]
        )
        band = None
        if "heart_rate_min" in df.columns and "heart_rate_max" in df.columns:
            band = base.mark_area(opacity=0.3, color="lightblue").encode(
                y="heart_rate_min:Q",
                y2="heart_rate_max:Q"
            )
        resting = None
        if "heart_rate_custom" in df.columns and df["heart_rate_custom"].notna().any():
            resting_val = df["heart_rate_custom"].iloc[0]
            resting = base.mark_rule(color="green", strokeDash=[5, 5]).encode(
                y=alt.Y(value=resting_val)
            )
        chart = line
        if band is not None: chart = band + chart
        if resting is not None: chart = chart + resting

    elif chart_type == "stress":
        chart = alt.Chart(df).mark_line(point=True, color="orange").encode(
            alt.X(xval, title=xtitle, scale=alt.Scale(domain=x_domain)),
            alt.Y(yval, title=ytitle),
            tooltip=[xval, yval]
        )

    elif chart_type == "spo2":
        chart = alt.Chart(df).mark_line(point=True, color="blue").encode(
            alt.X(xval, title=xtitle, scale=alt.Scale(domain=x_domain)),
            alt.Y(yval, title=ytitle),
            tooltip=[xval, yval]
        )

    elif chart_type == "steps":
        chart = alt.Chart(df).mark_bar(color="purple").encode(
            alt.X(xval, title=xtitle, scale=alt.Scale(domain=x_domain)),
            alt.Y(yval, title=ytitle),
            tooltip=[xval, yval]
        )

    elif chart_type == "calorie":
        chart = alt.Chart(df).mark_bar(color="brown").encode(
            alt.X(xval, title=xtitle, scale=alt.Scale(domain=x_domain)),
            alt.Y(yval, title=ytitle),
            tooltip=[xval, yval]
        )

    else:  # fallback
        chart = alt.Chart(df).mark_line(point=True).encode(
            alt.X(xval, title=xtitle, scale=alt.Scale(domain=x_domain)),
            alt.Y(yval, title=ytitle),
            tooltip=[xval, yval]
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

def loadBinningjsons(offset_col,jsonfilepath,supabase):    
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
