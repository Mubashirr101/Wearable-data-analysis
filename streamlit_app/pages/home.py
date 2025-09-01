import streamlit as st

def show_home():                                    
    st.header('Athlete Tracker')

    # first row
    col1,col2,col3,col4,col5 = st.columns([4,2,2,2,2])
    with col1:
        container1 = st.container(border=True)
        container1.write('PieChart of completed goals')
    with col2:
        container2 = st.container(border=True)
        container2.write('Sleep (hrs)')
    with col3:
        container3 = st.container(border=True)
        container3.write('Food (kcal)')
    with col4:
        container4 = st.container(border=True)
        container4.write('steps')
    with col5:
        container5 = st.container(border=True)   
        container5.write('HeartRate(bpm)')

    # second row 
    col6,col7 = st.columns([4,8])
    with col6:
        container6 = st.container(border=True)
        container6.write('list of goals..')
    with col7:
        container7 = st.container(border=True)
        container7.write('Steps Chart')
         
        
