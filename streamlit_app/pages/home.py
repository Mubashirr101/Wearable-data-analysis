import streamlit as st
import pandas as pd
import numpy as np
import altair as alt

def show_home():        
    
    # Fake placeholder data
    steps_data = pd.DataFrame({
    "Day": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
    "Steps": [4500, 7200, 6800, 8200, 10400, 9500, 5000]
    })


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
        
        stepstrendsContainer = st.container(border=True)
        stepstrendsContainer.subheader('📊Steps Trend (Weekly)')
        steps_chart = (
            alt.Chart(steps_data)
                .mark_line(point=True)
                .encode(
                    x='Day',
                    y='Steps',
                    tooltip = ['Day','Steps']
                )
                .interactive()
        )
        stepstrendsContainer.altair_chart(steps_chart,use_container_width=True)
       

