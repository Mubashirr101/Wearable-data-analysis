import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
from folium import plugins
import altair as alt
from fitparse import FitFile
import gpxpy
import numpy as np
from math import radians, sin, cos, sqrt, atan2
from branca.element import Template, MacroElement
from jinja2 import Template
import hashlib

# Initialize session state for map persistence
if 'map_center' not in st.session_state:
    st.session_state.map_center = None
if 'map_zoom' not in st.session_state:
    st.session_state.map_zoom = None
if 'map_user_interacted' not in st.session_state:
    st.session_state.map_user_interacted = False
if 'activity_df' not in st.session_state:
    st.session_state.activity_df = None
if 'current_file_hash' not in st.session_state:
    st.session_state.current_file_hash = None

def show_activity():
    st.header('Activity')
    tab1, tab2 = st.tabs(['Workout', 'Running Route'])
    
    with tab1:
        st.write('exercises')
    
    with tab2:       
        # -------------------
        # Helper Functions
        # -------------------
        def haversine_distance(lat1, lon1, lat2, lon2):
            R = 6371000  # Earth radius in meters
            phi1 = radians(lat1)
            phi2 = radians(lat2)
            delta_phi = radians(lat2 - lat1)
            delta_lambda = radians(lon2 - lon1)
            
            a = sin(delta_phi/2)**2 + cos(phi1)*cos(phi2)*sin(delta_lambda/2)**2
            c = 2 * atan2(sqrt(a), sqrt(1-a))
            
            return R * c

        # -------------------
        # Parsing Functions (with caching)
        # -------------------
        @st.cache_data
        def parse_fit(file) -> pd.DataFrame:
            try:
                fitfile = FitFile(file)
                records = []
                for record in fitfile.get_messages("record"):
                    rec_data = {}
                    for data in record:
                        rec_data[data.name] = data.value
                    # Convert coordinates from semicircles to degrees
                    if 'position_lat' in rec_data and rec_data['position_lat']:
                        rec_data['position_lat'] = rec_data['position_lat'] * (180 / 2**31)
                    if 'position_long' in rec_data and rec_data['position_long']:
                        rec_data['position_long'] = rec_data['position_long'] * (180 / 2**31)
                    records.append(rec_data)
                return pd.DataFrame(records)
            except Exception as e:
                st.error(f"Error parsing FIT file: {str(e)}")
                return pd.DataFrame()

        @st.cache_data
        def parse_gpx(file) -> pd.DataFrame:
            try:
                gpx = gpxpy.parse(file)
                records = []
                for track in gpx.tracks:
                    for segment in track.segments:
                        for point in segment.points:
                            records.append({
                                "time": point.time,
                                "lat": point.latitude,
                                "lon": point.longitude,
                                "elevation": point.elevation
                            })
                return pd.DataFrame(records)
            except Exception as e:
                st.error(f"Error parsing GPX file: {str(e)}")
                return pd.DataFrame()

        def normalize_data(df: pd.DataFrame) -> pd.DataFrame:
            rename_map = {
                "heart_rate": "Heart Rate",
                "cadence": "Cadence",
                "speed": "Speed",
                "distance": "Distance",
                "altitude": "Elevation",
                "elevation": "Elevation",
                "position_lat": "lat",
                "position_long": "lon",
                "longitude": "lon",
                "latitude": "lat",
            }
            df = df.rename(columns={c: rename_map.get(c, c) for c in df.columns})
            
            # Ensure numeric columns have appropriate dtypes
            numeric_columns = ["Heart Rate", "Cadence", "Speed", "Distance", "Elevation"]
            for col in numeric_columns:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            
            # Calculate cumulative distance if we have lat/lon data
            if "lat" in df.columns and "lon" in df.columns and not df.empty:
                df = df.dropna(subset=["lat", "lon"])
                if not df.empty:
                    # Initialize as float to avoid dtype issues
                    if 'Distance' not in df.columns:
                        df['Distance'] = 0.0
                    else:
                        df['Distance'] = df['Distance'].astype(float)
                        
                    # Pre-calculate distances to avoid repeated calculations
                    df['distance_delta'] = 0.0
                    for i in range(1, len(df)):
                        dist = haversine_distance(
                            df.iloc[i-1]['lat'], df.iloc[i-1]['lon'],
                            df.iloc[i]['lat'], df.iloc[i]['lon']
                        )
                        df.iloc[i, df.columns.get_loc('distance_delta')] = float(dist)
                        df.iloc[i, df.columns.get_loc('Distance')] = float(df.iloc[i-1]['Distance'] + dist)
            
            return df

        def show_map(df: pd.DataFrame):
            if "lat" in df.columns and "lon" in df.columns and not df.empty:
                coords = list(zip(df["lat"], df["lon"]))
                
                # Use stored map center/zoom if available, otherwise fit to bounds
                if (st.session_state.map_center and 
                    st.session_state.map_zoom and 
                    st.session_state.map_user_interacted):
                    center = st.session_state.map_center
                    zoom = st.session_state.map_zoom
                    fit_bounds = False
                else:
                    # Fit to the route bounds
                    center = [df["lat"].mean(), df["lon"].mean()]
                    zoom = 13
                    fit_bounds = True

                m = folium.Map(location=center, zoom_start=zoom, tiles="OpenStreetMap")
                folium.PolyLine(coords, color="blue", weight=3).add_to(m)
                folium.Marker(coords[0], tooltip="Start", icon=folium.Icon(color="green")).add_to(m)
                folium.Marker(coords[-1], tooltip="End", icon=folium.Icon(color="red")).add_to(m)

                if fit_bounds:
                    m.fit_bounds([
                        [df["lat"].min(), df["lon"].min()],
                        [df["lat"].max(), df["lon"].max()]
                    ])

                # Display the map and capture interactions
                map_data = st_folium(
                    m,
                    width=800,
                    height=500,
                    returned_objects=["bounds", "center", "zoom"],
                    key="activity_map"
                )

                # Update session state with map interactions
                if map_data and "center" in map_data:
                    st.session_state.map_center = [map_data["center"]["lat"], map_data["center"]["lng"]]
                    st.session_state.map_zoom = map_data.get("zoom", 13)
                    st.session_state.map_user_interacted = True
            else:
                st.warning("DataFrame must have 'lat' and 'lon' columns with at least one row.")

        def show_charts(df: pd.DataFrame):
            vitals = ["Heart Rate", "Speed", "Cadence", "Elevation", "Distance"]
            for vital in vitals:
                if vital in df.columns:
                    chart = (
                        alt.Chart(df.reset_index())
                        .mark_line()
                        .encode(x="index", y=alt.Y(vital, title=vital))
                        .properties(width="container", height=200, title=vital)
                    )
                    st.altair_chart(chart, use_container_width=True)

        # -------------------
        # Main App
        # -------------------
        uploaded_file = st.file_uploader(
            "Upload your activity file", 
            type=["fit", "gpx", "csv", "json"]
        )

        # Check if a new file was uploaded
        current_file_hash = hashlib.md5(uploaded_file.getvalue()).hexdigest() if uploaded_file else None
        
        # Reset map state only if a new file is uploaded
        if (uploaded_file is not None and 
            st.session_state.current_file_hash != current_file_hash):
            st.session_state.map_center = None
            st.session_state.map_zoom = None
            st.session_state.map_user_interacted = False
            st.session_state.current_file_hash = current_file_hash

        # Process uploaded file or use existing data
        if uploaded_file is not None:
            if uploaded_file.name.endswith(".fit"):
                df = parse_fit(uploaded_file)
            elif uploaded_file.name.endswith(".gpx"):
                df = parse_gpx(uploaded_file)
            elif uploaded_file.name.endswith(".csv"):
                df = pd.read_csv(uploaded_file)
            elif uploaded_file.name.endswith(".json"):
                df = pd.read_json(uploaded_file)
            else:
                st.error("Unsupported file format")
                df = None

            if df is not None and not df.empty:
                df = normalize_data(df)
                st.session_state.activity_df = df
            else:
                st.error("Failed to process the file or file is empty")
        elif st.session_state.activity_df is not None:
            df = st.session_state.activity_df
        else:
            df = None
            st.info("👆 Please upload a FIT or GPX file to get started")

        # Display the map and charts if we have data
        if df is not None and not df.empty:                
            col1, col2 = st.columns([2, 1])
            
            with col1:
                st.subheader("📍 Route Map (Leaflet)")
                show_map(df)
            
            with col2:
                st.subheader("📊 Activity Vitals")
                show_charts(df)

            st.success(f"Loaded {len(df)} records ✅")
            with st.expander("View raw data"):
                st.dataframe(df.head())

