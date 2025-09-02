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
    
    # first row
    col1,col2,col3,col4,col5 = st.columns([4,2,2,2,2])
    with col1:
        container1 = st.container(border=True)
        progress_data = pd.DataFrame({
        "Category": ["Completed", "Remaining"],
        "Value": [4, 2]
        })
        # container1.subheader("🔥Goal Completion")        
        donut_chart = (
        alt.Chart(progress_data,height=100,width=100)
        .mark_arc(innerRadius = 20,outerRadius=40)
        .encode(
            theta = "Value",
            color = alt.Color("Category",legend = None),
            tooltip = ["Category","Value"],
            
            )
        )
        container1.subheader('⚡Goals Completed')
        c1c1,c1c2 = container1.columns([1,2])
        c1c1.altair_chart(donut_chart,use_container_width=True)
        c1c2.metric(label='⚡Goals Completed', value='4/6', delta='+1', label_visibility='collapsed')
    with col2:
        container2 = st.container(border=True)
        # container2.markdown("<h3 style = 'text-align:left;'>💤 Sleep</h3>",unsafe_allow_html=True)
        container2.metric(label='💤 Sleep',value='7.5 hrs',delta='-0.5h')
    with col3:
        container3 = st.container(border=True)
        container3.metric(label='🍎 Calories', value='1800 kcal', delta='+300')
    with col4:
        container4 = st.container(border=True)
        container4.metric(label='👟 Steps',value='8200',delta='+500')
    with col5:
        container5 = st.container(border=True)   
        container5.metric(label='❤️ HR (avg)',value='72 bpm',delta='+5')


    # second row 
    col6,col7 = st.columns([4,8])
    with col6:
        container6 = st.container(border=True)
        container6.subheader('🎯 Your Goals..')
        for k , v in goals.items():
            container6.write(f'- {k}: **{v}**')
    
    with col7:
        container7 = st.container(border=True)
        container7.subheader('📊Steps Trend (Weekly)')
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
        container7.altair_chart(steps_chart,use_container_width=True)

  
        
        
         
        
