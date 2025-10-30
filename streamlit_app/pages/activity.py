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
from datetime import datetime
import io
from xml.etree import ElementTree as ET
import time
from httpx import RemoteProtocolError, ReadTimeout, ConnectError

def show_activity(df_exercise,df_exercise_routine,df_custom_exercise,df_inbuilt_exercises,supabase_client):
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

    tab1, tab2 = st.tabs(['Indoor Activities 🏋🏻‍♂️', 'Outdoor Activities 👟'])
    
    with tab1:
        with tab1:

            t1c1,t2c2 = st.columns([4,1])
            t1c1.subheader("🏋🏻 Workout Session")

            # Date selector
            selected_date = t2c2.date_input("Select a Date to View Exercises", key="indoor_activity_date")          

            # Filter by selected date
            if selected_date:
                daily_exercises = df_exercise[df_exercise["localized_time"].dt.date == pd.to_datetime(selected_date).date()]
                if daily_exercises.empty:
                    st.warning(f"No exercise sessions found for {selected_date}.")
                else:
                    workout_routine_name = "Workout Routine"
                    ## Workout details (duration,total no. of workouts, total cals, avg hr, max hr, etc)
                    if daily_exercises['routine_datauuid'].nunique() == 1:
                        for i, row in df_exercise_routine.iterrows():
                            if row.get('datauuid') == daily_exercises['routine_datauuid'].iloc[0]:
                                for i2, row2 in df_custom_exercise.iterrows():
                                    if row2.get('custom_id') == row.get('custom_id'):
                                        workout_routine_name = row2.get('custom_name')
                    
                    st.markdown(f"#### {workout_routine_name}")
                    ## Workout flow (warmups n cooldowns in separate blocks, breaks in small gaps between exercises
                    st.markdown("---")                    
                    activity_count = 0
                    for i, row in daily_exercises.iterrows():
                        if row.get('activity_type') == 10:
                            st.write(f"Warmup")                        
                        elif row.get('activity_type') == 40:
                            st.write(f"Break")
                        elif row.get('activity_type') == 50:
                            st.write(f"Cooldown")
                        elif row.get('activity_type') == 20:
                            # 20 is inbuilt exercise
                            activity_count += 1        
                            if row.get('exercise_exercise_type'):
                                for i2, row2 in df_inbuilt_exercises.iterrows():
                                    if row2.get('exercise_type') == row.get('exercise_exercise_type'):
                                        workout_name = row2.get('exercise_name')
                                st.write(f"{workout_name}")         
                        elif row.get('activity_type') == 30: 
                            # 30 is custom exercise
                            activity_count += 1
                            if row.get('custom_id'):
                                for i2, row2 in df_custom_exercise.iterrows():
                                    if row2.get('custom_id') == row.get('custom_id'):
                                        workout_name = row2.get('custom_name')
                                st.write(f"{workout_name}")
                        else:
                            activity_count += 1
                            if row.get('custom_id'):
                                for i2, row2 in df_custom_exercise.iterrows():
                                    if row2.get('custom_id') == row.get('custom_id'):
                                        workout_name = row2.get('custom_name')
                                st.write(f"{workout_name}")
                            elif row.get('exercise_exercise_type'):
                                for i2, row2 in df_inbuilt_exercises.iterrows():
                                    if row2.get('exercise_type') == row.get('exercise_exercise_type'):
                                        workout_name = row2.get('exercise_name')
                                st.write(f"{workout_name}")
                            

                #         # Duration and stats
                #         col1, col2, col3 = st.columns(3)
                #         with col1:
                #             st.metric("Duration (min)", round(row.get("duration", 0) / 60, 1))
                #         with col2:
                #             st.metric("Calories Burned", row.get("calories", "N/A"))
                #         with col3:
                #             st.metric("Distance (km)", round(row.get("distance", 0) / 1000, 2))

                #         # Link to routine/custom exercise if available
                #         custom_info = custom_df[custom_df["id"] == row.get("custom_exercise_id")] if "id" in custom_df.columns else None
                #         if custom_info is not None and not custom_info.empty:
                #             st.write(f"**Custom Exercise:** {custom_info.iloc[0].get('name', 'Unnamed')}")
                #         routine_info = routine_df[routine_df["id"] == row.get("routine_id")] if "id" in routine_df.columns else None
                #         if routine_info is not None and not routine_info.empty:
                #             st.write(f"**Routine:** {routine_info.iloc[0].get('name', 'Unnamed')}")

                #         # Recovery HR
                #         recovery_info = recovery_df[recovery_df["exercise_id"] == row.get("id")] if "id" in recovery_df.columns else None
                #         if recovery_info is not None and not recovery_info.empty:
                #             st.metric("Recovery Heart Rate", recovery_info.iloc[0].get("recovery_heart_rate", "N/A"))

                #         # Load and display vitals (from JSONs)
                #         import json
                #         try:
                #             with open("/mnt/data/47bafabf-51bb-4f50-87bc-101692d93dee.com.samsung.health.exercise.live_data.json") as f:
                #                 live_data = json.load(f)
                #             with open("/mnt/data/47bafabf-51bb-4f50-87bc-101692d93dee.sensing_status.json") as f:
                #                 sensing = json.load(f)

                #             hr_values = [d.get("heart_rate") for d in live_data if "heart_rate" in d]
                #             if hr_values:
                #                 st.line_chart(pd.Series(hr_values, name="Heart Rate"))
                #             st.write(f"**Sampling Rate:** {sensing.get('sampling_rate', 'N/A')} ms")
                #             st.write(f"**Max HR:** {sensing['heart_rate'].get('max_hr_auto', 'N/A')}")
                #         except Exception as e:
                #             st.warning(f"Could not load HR/vitals data: {e}")

            else:
                st.info("👆 Select a date to view indoor exercise sessions.")

    
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
        def parse_fit(file_data) -> pd.DataFrame:
            try:
                # Convert bytes to file-like object
                file_obj = io.BytesIO(file_data)
                fitfile = FitFile(file_obj)
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
        def parse_gpx(file_data) -> pd.DataFrame:
            try:
                # Convert bytes to string for gpxpy
                file_content = file_data.decode('utf-8')
                gpx = gpxpy.parse(file_content)
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

        @st.cache_data
        def parse_kml(file_data) -> pd.DataFrame:
            try:
                # Convert bytes to string and parse XML
                file_content = file_data.decode('utf-8')
                root = ET.fromstring(file_content)
                
                # Namespace handling for KML
                ns = {'kml': 'http://www.opengis.net/kml/2.2'}
                
                records = []
                
                # Find all Placemark elements with LineString (the actual route)
                for placemark in root.findall('.//kml:Placemark', ns):
                    # Look for LineString coordinates (the route)
                    linestring = placemark.find('.//kml:LineString', ns)
                    if linestring is not None:
                        coords_elem = linestring.find('.//kml:coordinates', ns)
                        if coords_elem is not None and coords_elem.text:
                            # Split coordinates by whitespace and newlines
                            coords_list = coords_elem.text.strip().split()
                            for coord in coords_list:
                                # Handle coordinates format: lon,lat[,elevation]
                                parts = coord.split(',')
                                if len(parts) >= 2:
                                    lon, lat = float(parts[0]), float(parts[1])
                                    elevation = float(parts[2]) if len(parts) > 2 else 0
                                    records.append({
                                        "lat": lat,
                                        "lon": lon,
                                        "elevation": elevation
                                    })
                
                # If no LineString found, look for any coordinates in the file
                if not records:
                    for coords_elem in root.findall('.//kml:coordinates', ns):
                        if coords_elem.text:
                            coords_list = coords_elem.text.strip().split()
                            for coord in coords_list:
                                parts = coord.split(',')
                                if len(parts) >= 2:
                                    lon, lat = float(parts[0]), float(parts[1])
                                    elevation = float(parts[2]) if len(parts) > 2 else 0
                                    records.append({
                                        "lat": lat,
                                        "lon": lon,
                                        "elevation": elevation
                                    })
                
                return pd.DataFrame(records)
            except Exception as e:
                st.error(f"Error parsing KML file: {str(e)}")
                st.error(f"KML content: {file_data[:500]}...")  # Show first 500 chars for debugging
                return pd.DataFrame()

        @st.cache_data
        def parse_tcx(file_data) -> pd.DataFrame:
            try:
                # Convert bytes to string and parse XML
                file_content = file_data.decode('utf-8')
                root = ET.fromstring(file_content)
                
                # Namespace handling for TCX
                ns = {'ns': 'http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2'}
                
                records = []
                
                for trackpoint in root.findall('.//ns:Trackpoint', ns):
                    time_elem = trackpoint.find('ns:Time', ns)
                    pos_elem = trackpoint.find('ns:Position', ns)
                    
                    if pos_elem is not None:
                        lat_elem = pos_elem.find('ns:LatitudeDegrees', ns)
                        lon_elem = pos_elem.find('ns:LongitudeDegrees', ns)
                        
                        if lat_elem is not None and lon_elem is not None:
                            record = {
                                "time": time_elem.text if time_elem is not None else None,
                                "lat": float(lat_elem.text),
                                "lon": float(lon_elem.text)
                            }
                            
                            # Get elevation if available
                            alt_elem = trackpoint.find('ns:AltitudeMeters', ns)
                            if alt_elem is not None:
                                record["elevation"] = float(alt_elem.text)
                            
                            # Get heart rate if available
                            hr_elem = trackpoint.find('.//ns:HeartRateBpm/ns:Value', ns)
                            if hr_elem is not None:
                                record["heart_rate"] = float(hr_elem.text)
                            
                            records.append(record)
                
                return pd.DataFrame(records)
            except Exception as e:
                st.error(f"Error parsing TCX file: {str(e)}")
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
                st.warning("No valid coordinate data found for mapping.")

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
     
        def loadMapfiles(type, date, file_type, supabase):    
            bucket_name = "healthsync-bucket"
            date_obj = datetime.strptime(str(date), "%Y-%m-%d")
            formatted_date = date_obj.strftime("%d.%m.%Y")
            folder_path = 'Health Sync Activities/'

            # Fetch all files with pagination and retry logic
            all_files = []
            limit = 100
            offset = 0
            max_pages = 100  # safety limit to avoid infinite loops


            while True:
                retries = 3
                for attempt in range(retries):
                    try:
                        files = supabase.storage.from_(bucket_name).list(
                            folder_path,
                            {"limit": limit, "offset": offset}
                        )
                        break  # success → break retry loop
                    except (RemoteProtocolError, ReadTimeout, ConnectError) as e:
                        if attempt < retries - 1:
                            st.warning(f"⚠️ Connection issue (attempt {attempt + 1}/{retries}). Retrying...")
                            time.sleep(1)
                        else:
                            st.error(f"❌ Failed to fetch files after {retries} attempts: {str(e)}")
                            return []
                    except Exception as e:
                        st.error(f"Unexpected error while listing files: {str(e)}")
                        return []

                if not files:
                    break

                all_files.extend(files)
                offset += limit

                # Safety break
                if offset // limit > max_pages:
                    st.warning("⚠️ Too many pages of files; stopping early to prevent overload.")
                    break

            # Filter files by activity type, date, and file type
            matching_files = []
            expected_prefix = f"{type}-{formatted_date}"  
            file_extension = f".{file_type.lower()}"

            for file in all_files:
                file_name = file['name']
                if (file_name.startswith(expected_prefix) and 
                    file_name.lower().endswith(file_extension)):
                    matching_files.append(file_name)

            if not matching_files:
                return []

            downloaded_files = []
            for name in matching_files:
                file_path = folder_path + name

                # Retry download in case of disconnection
                for attempt in range(retries):
                    try:
                        file_data = supabase.storage.from_(bucket_name).download(file_path)
                        downloaded_files.append({
                            'name': name,
                            'data': file_data,
                            'type': file_type
                        })
                        break
                    except (RemoteProtocolError, ReadTimeout, ConnectError) as e:
                        if attempt < retries - 1:
                            st.warning(f"⚠️ Download failed for {name} (attempt {attempt + 1}/{retries}). Retrying...")
                            time.sleep(1)
                        else:
                            st.error(f"❌ Failed to download {name}: {str(e)}")
                    except Exception as e:
                        st.error(f"Unexpected error downloading {name}: {str(e)}")
                        break

            return downloaded_files


        # -------------------
        # Main App
        # -------------------
        
        # Create two columns for date and file type selection
        col_date, col_type = st.columns(2)
        
        with col_date:
            outdoor_activity_calender = st.date_input(
                "Select Activity Date", 
                key="outdoor_activity_date_filter"
            )
        
        with col_type:
            # File type dropdown
            file_type_options = ["FIT", "GPX", "KML", "TCX"]
            outdoor_activity_file_type = st.selectbox(
                "Select File Type",
                options=file_type_options,
                key="outdoor_activity_file_type"
            )
        
        outdoor_activity_type = 'WALKING'
        
        # Load files based on selected date and file type
        if outdoor_activity_calender:
            mapfiles = loadMapfiles(
                outdoor_activity_type, 
                outdoor_activity_calender, 
                outdoor_activity_file_type, 
                supabase_client
            )
            
            if mapfiles:
                st.success(f"Found {len(mapfiles)} {outdoor_activity_file_type} file(s) for {outdoor_activity_calender}")
                
                # If multiple files found, let user choose which one to display
                selected_file = None
                if len(mapfiles) > 1:
                    file_options = [f["name"] for f in mapfiles]
                    selected_file_name = st.selectbox(
                        "Select specific file to display:",
                        options=file_options,
                        key="file_selector"
                    )
                    selected_file = next((f for f in mapfiles if f["name"] == selected_file_name), None)
                else:
                    selected_file = mapfiles[0]
                
                if selected_file:
                    # Parse the selected file based on its type
                    file_data = selected_file['data']
                    file_type = selected_file['type']
                    
                    # Create a hash of the file data to track changes
                    current_file_hash = hashlib.md5(file_data).hexdigest()
                    
                    # Reset map state only if a new file is selected
                    if st.session_state.get('current_file_hash') != current_file_hash:
                        st.session_state.map_center = None
                        st.session_state.map_zoom = None
                        st.session_state.map_user_interacted = False
                        st.session_state.current_file_hash = current_file_hash
                    
                    # Parse file based on type
                    df = None
                    if file_type == "FIT":
                        df = parse_fit(file_data)
                    elif file_type == "GPX":
                        df = parse_gpx(file_data)
                    elif file_type == "KML":
                        df = parse_kml(file_data)
                    elif file_type == "TCX":
                        df = parse_tcx(file_data)
                    
                    if df is not None and not df.empty:
                        df = normalize_data(df)
                        st.session_state.activity_df = df
                        
                        # Display success message
                        st.success(f"Successfully parsed {len(df)} data points from {selected_file['name']}")
                    else:
                        st.error(f"Failed to process the {file_type} file or file is empty")
            else:
                st.warning(f"No {outdoor_activity_file_type} files found for {outdoor_activity_calender}")
                df = None
        else:
            df = None
            st.info("👆 Please select a date and file type to load activity data")

        # Display the map and charts if we have data
        if df is not None and not df.empty:                
            col1, col2 = st.columns([2, 1])
            
            with col1:
                st.subheader("📍 Route Map (Leaflet)")
                show_map(df)
            
            with col2:
                st.subheader("📊 Activity Vitals")
                show_charts(df)

            with st.expander("View raw data"):
                st.dataframe(df.head())