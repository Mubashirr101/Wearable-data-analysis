import streamlit as st
import pandas as pd
import numpy as np
import altair as alt
import time
from collections import Counter

def clean_raw_df(raw_dataframes):
    df = raw_dataframes
    for key, value in df.items():
        if key == 'steps':
            continue
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
def filter_dfs(dfs):
    filtered_dfs = {}
    latest_dates = []
    for table_name, table in dfs.items():
        tbl = table.copy()
        # normlizing day_time/start_time safely only if not already datetime
        if 'day_time' in tbl.columns:
            tbl['day_time'] = pd.to_datetime(tbl['day_time'], unit='ms',errors='coerce')            
            tbl['day_time'] = tbl['day_time'].dt.normalize()
            latest_dates.append(tbl['day_time'].max())            
        else:
            # ensureing start time exists and it datetime
            if not pd.api.types.is_datetime64_any_dtype(tbl['start_time']):
                tbl['start_time']  = pd.to_datetime(tbl['start_time'],errors = 'coerce')
                tbl['start_time'] = tbl['start_time'].dt.normalize()
            else:
                tbl['start_time']  = pd.to_datetime(tbl['start_time'],errors = 'coerce')
                tbl['start_time'] = tbl['start_time'].dt.normalize()
            latest_dates.append(tbl['start_time'].max())

        dfs[table_name] = tbl


    # guard against empty datasets having NaT
    valid_dates = []
    for d in latest_dates:
        if pd.notna(d):
            valid_dates.append(d)
    if not valid_dates:
        # return empty data frames if noting valid        
        return {k:v.iloc[0:0].copy() for k,v in dfs.items()}

    # which latest date is the majority in the tables, that dates week will be shown
    majority_date = Counter(latest_dates).most_common(1)[0]
    target_date = majority_date[0]
    target_iso_year, target_iso_week, _ = target_date.isocalendar()   
    for table_name, table in dfs.items() :
        tbl = table.copy()
        if 'day_time' in tbl.columns:
            mask = (tbl["day_time"].dt.isocalendar().year == target_iso_year) & (tbl["day_time"].dt.isocalendar().week == target_iso_week)
            df_filtered = tbl.loc[mask].sort_values(by='day_time',ascending = True).copy()
        else:
            mask = (tbl["start_time"].dt.isocalendar().year == target_iso_year) & (tbl["start_time"].dt.isocalendar().week == target_iso_week)
            df_filtered = tbl.loc[mask].sort_values(by='start_time',ascending = True).copy()
        
        filtered_dfs[table_name] = df_filtered
    return filtered_dfs

def summarize_days(dfs):
    for key, table in dfs.items():
        if key == 'steps':
            continue

        
    

def show_home(df_hr,df_steps_daily,df_calorie,supabase_client):        
    
    ####################################################3
    ## data fetching
    ## only combined step count is used from both devices (both phone and watch)
    df_steps_daily = df_steps_daily[df_steps_daily['deviceuuid'] == 'VfS0qUERdZ']
    dfs ={
        'hr':df_hr[['heart_rate_start_time','heart_rate_heart_rate','heart_rate_min','heart_rate_max','localized_time']],
        'steps':df_steps_daily[['day_time','count']],
        'calorie':df_calorie
    }
    
    cleaned_dfs = clean_raw_df(dfs)
    filtered_dfs = filter_dfs(cleaned_dfs) 

    print(filtered_dfs['hr'])
    summarize_days(filtered_dfs)




    ###########################################333
    steps_data = filtered_dfs['steps'].copy()
    if not steps_data.empty and 'day_time' in steps_data.columns:
        steps_data = steps_data.reset_index(drop = True)
        steps_data.loc[:,'weekday'] = steps_data['day_time'].dt.day_name().str[:3]
    else:
        steps_data['weekday'] = []


    # Fake placeholder data
    goals = {
    "Steps": "10,000 / 12,000",
    "Sleep": "7.5 / 8 hrs",
    "Calories": "1800 / 2000 kcal",
    "Active Minutes": "45 / 60 min"
    }                            
    # st.title('🏃🏻‍♂️ Athlete Tracker')
   

    # Use HTML instead of st.title
    st.markdown("""
                <h1 style ="  
                font-size: 2.3em; 
                white-space: nowrap; 
                overflow: hidden; 
                text-overflow: ellipsis; 
                width: 100%;
            ">
                🏃🏻‍♂️ Athlete Tracker
            </h1>
            """,
          unsafe_allow_html=True)
    
        
    col1,col2 = st.columns([4,8])        
         
    with col1:
        # goal donut
        goalContainer_1 = st.container(border=True)
        progress_data = pd.DataFrame({
        "Category": ["Completed", "Remaining"],
        "Value": [4, 2]
        })
        # goalContainer_1.subheader("🔥Goal Completion")        
        donut_chart = (
        alt.Chart(progress_data,height=100,width=100)
        .mark_arc(innerRadius = 20,outerRadius=40)
        .encode(
            theta = "Value",
            color = alt.Color("Category",legend = None),
            tooltip = ["Category","Value"],
            
            )
        )
        goalContainer_1.subheader('⚡Goals Completed')
        c1c1,c1c2 = goalContainer_1.columns([1,2])
        c1c1.altair_chart(donut_chart,use_container_width=True)
        c1c2.metric(label='⚡Goals Completed', value='4/6', delta='+1', label_visibility='collapsed')

        ###### goal list         
        goalContainer_2 = st.container(border=True)
        goalContainer_2.subheader('🎯 Your Goals..')
        for k , v in goals.items():
            goalContainer_2.write(f'- {k}: **{v}**')

    with col2:        
        col2_subcol1, col2_subcol2 ,col2_subcol3,col2_subcol4 = st.columns([2,2,2,2])
        with col2_subcol1:
            sleepContainer = st.container(border=True)
            # sleepContainer.markdown("<h3 style = 'text-align:left;'>💤 Sleep</h3>",unsafe_allow_html=True)
            sleepContainer.metric(label='💤 Sleep',value='7.5 hrs',delta='-0.5h')
        with col2_subcol2:
            caloriesContainer = st.container(border=True)
            caloriesContainer.metric(label='🍎 Calories', value='1800 kcal', delta='+300')
        with col2_subcol3:
            stepsContainer = st.container(border=True)
            stepsContainer.metric(label='👟 Steps',value='8200',delta='+500')
        with col2_subcol4:
            hravgContainer = st.container(border=True)   
            hravgContainer.metric(label='❤️ HR (avg)',value='72 bpm',delta='+5')
        
        
        weekday_order = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        full_week = pd.DataFrame({'weekday': weekday_order})
        weekly_steps = full_week.merge(
            steps_data[['weekday','day_time','count']], 
            on = 'weekday',
            how='left'
        )
        weekly_steps['count'] = weekly_steps['count'].fillna(0)
        # filling dates if na
        week_start = steps_data['day_time'].min().normalize()
        weekly_steps['day_time'] = pd.date_range(start=week_start,periods=7,freq='D')
        stepstrendsContainer = st.container(border=True)
        stepstrendsContainer.subheader('📊Steps Trend (Weekly)')
        steps_chart = (
            alt.Chart(weekly_steps)
                .mark_line(point=True)
                .encode(
                    x=alt.X('weekday',sort=weekday_order,title='Day',axis=alt.Axis(labelAngle=0) ),
                    y=alt.Y('count',title='Steps'),
                    tooltip = [
                        alt.Tooltip('day_time:T',title = 'Date'),
                        alt.Tooltip('count:Q',title='Steps')
                    ]
                )
                .interactive()
        )
        stepstrendsContainer.altair_chart(steps_chart,use_container_width=True)
       

