import streamlit as st
import pandas as pd
import numpy as np
import altair as alt
import time
from collections import Counter
from datetime import datetime, date

def clean_raw_df(raw_dataframes):
    df = raw_dataframes
    for key, value in df.items():
        if key == 'steps':
            continue       

        if "localized_time" in value.columns:
            value = value.rename(columns= lambda c: "start_time" if "localized_time" in c else c)
        elif "localized_start_time" in value.columns and "localized_end_time" in value.columns:
            value = value.rename(columns= lambda c: "start_time" if "localized_start_time" in c else c)
            value = value.rename(columns= lambda c: "end_time" if "localized_end_time" in c else c)
        
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
        datetime_col = None
        # normlizing day_time/start_time safely only if not already datetime
        if 'day_time' in tbl.columns:
            datetime_col = 'day_time'
        elif 'start_time' in tbl.columns:
            datetime_col = 'start_time'
        else:
            latest_dates.append(pd.NaT)
            continue

        if datetime_col == 'day_time':
            tbl['day_time'] = pd.to_datetime(tbl[datetime_col], unit='ms',errors='coerce')            
        else:
            tbl[datetime_col] = pd.to_datetime(tbl[datetime_col],errors='coerce')

        # nomalize and find the most latest date
        sleep_temp_tbl = pd.DataFrame() # temp table for storing latest date of sleep data
        if table_name == 'sleep':
            sleep_temp_tbl[datetime_col] = tbl[datetime_col].dt.normalize()
            latest_dates.append(sleep_temp_tbl[datetime_col].max())                      
        else:
            
            tbl[datetime_col] = tbl[datetime_col].dt.normalize()
            latest_dates.append(tbl[datetime_col].max())  
            

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
    majority_date = Counter(valid_dates).most_common(1)[0]
    target_date = majority_date[0]
    target_iso_year, target_iso_week, _ = target_date.isocalendar()     


    for table_name, table in dfs.items() :
        tbl = table.copy()
        datetime_col = None        
        if 'day_time' in tbl.columns:
            datetime_col = 'day_time'
        elif 'start_time' in tbl.columns:
            datetime_col = 'start_time'

        else:
            continue

        df_filtered =  None
        iso = tbl[datetime_col].dt.isocalendar()
        mask = (iso.year == target_iso_year) & (iso.week == target_iso_week)        
        df_filtered = tbl.loc[mask].sort_values(by=datetime_col,ascending = True).copy()        
        filtered_dfs[table_name] = df_filtered
    return filtered_dfs

def summarize_days(dfs):
    for key, table in dfs.items():
        if key == 'steps':
            continue
        elif key == 'hr':
            new_table = table.dropna().groupby('start_time').agg(
                hr = ('heart_rate_heart_rate','mean'),
                hr_min = ('heart_rate_min','min'),
                hr_max = ('heart_rate_max','max'),
            ).reset_index()
            dfs[key] = new_table
        elif key == 'calorie':
            continue
        elif key == 'food':
            new_table = table.dropna().groupby('start_time').agg(
                intake_cals = ('calorie','sum'),
            ).reset_index()
            dfs[key] = new_table
        elif key == 'sleep':
            # calculating the sleep duration from sleep start to end
            table['sleep_duration'] = table['end_time'] - table['start_time']
            new_table = table.drop(columns=['end_time'],errors = 'ignore')
            new_table['start_time'] = new_table['start_time'].dt.normalize()
            new_table['sleep_duration'] = new_table['sleep_duration'].dt.total_seconds() / 3600 # turning timedelta into hrs            
            dfs[key] = new_table
            

    return dfs

def aggregate_data(data,stat_col,placehlder_val):
    agg = placehlder_val
    if not data.empty and stat_col in data.columns:
        agg = data[stat_col].mean() 
    return agg

def fetch_stats(dfs):
    summarized_data = dfs


    ## STEPS DATA week chart
    steps_data = summarized_data['steps'].copy()
    if not steps_data.empty and 'day_time' in steps_data.columns:
        steps_data = steps_data.reset_index(drop = True)
        steps_data.loc[:,'weekday'] = steps_data['day_time'].dt.day_name().str[:3]
    else:
        steps_data['weekday'] = []
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

    # for weekly aggregates
   
    agg_steps = aggregate_data(steps_data,'count',6000)
    ## HR DATA
    hr_data = summarized_data['hr'].copy()
    agg_hr = aggregate_data(hr_data,'hr',80)

    ## Cal data
    cal_data = summarized_data['food'].copy()
    agg_cal = aggregate_data(cal_data,'food',2000) 

    ## Sleep Data
    sleep_data = summarized_data['sleep'].copy()
    agg_sleep = aggregate_data(sleep_data,'sleep_duration',7.5)
    # Round to 1 decimal place only if needed
    if agg_sleep != round(agg_sleep,1):
        agg_sleep = round(agg_sleep,1)

    ##########################   GOALS  ####################################### 
    ## daily stats and targets

    daily_steps_target = 10000 # aka 10k steps for each day
    daily_cal_target = 1700 # 1700 cal per day
    daily_sleep_target = 8 # 8hrs a day
    daily_active_mins_target = 60 # an hour of activity

    
    if not steps_data.empty:
        daily_steps = steps_data.loc[steps_data['day_time'].idxmax(),'count']
    else:
        daily_steps = 2000
    if not cal_data.empty:
        daily_cal = cal_data.loc[cal_data['start_time'].idxmax(),'intake_cals']
    else:
        daily_cal = 1600
    if not sleep_data.empty:
        daily_sleep = sleep_data.loc[sleep_data['start_time'].idxmax(),'sleep_duration']
    else:
        daily_sleep = 7
    
    daily_active_mins = 60 # placeholder    


    goals = {
    "Steps": f"{daily_steps:.0f} / {daily_steps_target}",
    "Sleep": f"{daily_sleep:.1f} / {daily_sleep_target} hrs",
    "Calories": f"{daily_cal:.0f} / {daily_cal_target} kcal",
    "Active Minutes": f"{daily_active_mins:.0f} / {daily_active_mins_target} min"
    }   
    
    ########## goals donut chart ############################

    goals_dict = {
            daily_steps_target : daily_steps,
            daily_sleep_target : daily_sleep,
            daily_cal_target : daily_cal,
            daily_active_mins_target : daily_active_mins,
        }     
    completed_goals = 0
    remaining_goals = 4  
    for target,value in goals_dict.items():
        if value >= target:
            completed_goals += 1
            remaining_goals -= 1  
    
    return agg_sleep,agg_steps,agg_cal,agg_sleep,agg_hr,weekly_steps,weekday_order,goals,completed_goals,remaining_goals

def show_home(df_hr,df_steps_daily,df_calorie,df_food_intake,df_sleep,supabase_client):        
    
    ####################################################3
    ## data fetching
    ## only combined step count is used from both devices (both phone and watch)
    df_steps_daily = df_steps_daily[df_steps_daily['deviceuuid'] == 'VfS0qUERdZ']
    dfs ={
        'hr':df_hr[['heart_rate_start_time','heart_rate_heart_rate','heart_rate_min','heart_rate_max','localized_time']],
        'steps':df_steps_daily[['day_time','count']],
        'calorie':df_calorie,
        'food': df_food_intake[['create_time','calorie','localized_time']],
        'sleep': df_sleep[['localized_start_time','localized_end_time']]
    }
    cleaned_dfs = clean_raw_df(dfs)
    filtered_dfs = filter_dfs(cleaned_dfs) 
    summarized_data = summarize_days(filtered_dfs)


    agg_sleep,agg_steps,agg_cal,agg_sleep,agg_hr,weekly_steps,weekday_order,goals,completed_goals,remaining_goals = fetch_stats(summarized_data)


    # Use HTML instead of st.title
    with st.container():
        st.markdown("""
                    <h1 style ="  
                    font-size: 2.3em; 
                    white-space: nowrap; 
                    overflow: hidden; 
                    text-overflow: ellipsis; 
                    width: 100%;
                    margin: 0px !important; 
                    padding-bottom: 2rem;   
                ">
                    🏃🏻‍♂️ AthleteX
                </h1>
                """,
            unsafe_allow_html=True)
    
        
    col1,col2 = st.columns([4,8])        
         
    with col1:
        # goal donut
        goalContainer_1 = st.container(border=True)
        progress_data = pd.DataFrame({
        "Category": ["Completed", "Remaining"],
        "Value": [1, 3]
        })
        total_goals = completed_goals + remaining_goals
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
        c1c1.altair_chart(donut_chart,width='stretch')
        c1c2.metric(label='⚡Goals Completed', value=f'{completed_goals}/{total_goals}', delta='+1', label_visibility='collapsed')

        ###### goal list         
        goalContainer_2 = st.container(border=True)
        goalContainer_2.subheader('🎯 Your Goals..')
        for k , v in goals.items():
            goalContainer_2.write(f'- {k}: **{v}**')

    with col2:
        agg_container = st.container(border = True,gap=None,vertical_alignment = 'distribute')
        agg_container.markdown("""
        <span style="
            font-weight: 700;
            font-size: 1.4rem;
            opacity: 0.8;
        ">
            *Weekly Averages*
        </span>
        """, unsafe_allow_html=True)
        col2_subcol1, col2_subcol2 ,col2_subcol3,col2_subcol4 = agg_container.columns([2,2,2,2])
        with col2_subcol1:
            sleepContainer = st.container(border=True)
            sleepContainer.metric(label='💤 Sleep',value=f'{agg_sleep} hrs',delta=f'-0.5h')
        with col2_subcol2:
            caloriesContainer = st.container(border=True)
            caloriesContainer.metric(label='🍎 Calories', value=f'{agg_cal:.0f} kcal', delta=f'+300')
        with col2_subcol3:
            stepsContainer = st.container(border=True)
            stepsContainer.metric(label='👟 Steps',value=f'{agg_steps:.0f}',delta=f'+500')
        with col2_subcol4:
            hravgContainer = st.container(border=True)   
            hravgContainer.metric(label='❤️ HR (avg)',value=f'{agg_hr:.0f} bpm',delta=f'+5')
        
        
       
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
        stepstrendsContainer.altair_chart(steps_chart,width='stretch')
       

