import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import altair as alt
from fitparse import FitFile
import gpxpy
import numpy as np
from math import radians, sin, cos, sqrt, atan2
import time

st.set_page_config(layout="wide")
st.title("🏃 Athlete Tracker (Leaflet Version)")

# Initialize session state for map interactions
if 'map_center' not in st.session_state:
    st.session_state.map_center = None
if 'map_zoom' not in st.session_state:
    st.session_state.map_zoom = None
if 'map_initialized' not in st.session_state:
    st.session_state.map_initialized = False
if 'last_map_data' not in st.session_state:
    st.session_state.last_map_data = None
if 'use_static_map' not in st.session_state:
    st.session_state.use_static_map = False

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

def validate_map_center(center):
    if isinstance(center, dict):
        return [center['lat'], center['lng']]
    elif isinstance(center, (list, tuple)) and len(center) == 2:
        return center
    else:
        return None

def downsample_data(df: pd.DataFrame, max_points=1000):
    """Reduce number of points while preserving route shape"""
    if len(df) <= max_points:
        return df
        
    # Simple downsampling - keep every nth point
    step = len(df) // max_points
    return df.iloc[::step].copy()

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

# -------------------
# Normalization (with dtype fixes)
# -------------------
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

# -------------------
# Visualization Functions
# -------------------
def show_map_interactive(df: pd.DataFrame):
    """Interactive map with performance optimizations"""
    if "lat" in df.columns and "lon" in df.columns and not df.empty:
        # Handle center coordinates
        if st.session_state.map_center:
            center = validate_map_center(st.session_state.map_center) or [df["lat"].mean(), df["lon"].mean()]
            zoom = st.session_state.map_zoom or 13
        else:
            center = [df["lat"].mean(), df["lon"].mean()]
            zoom = 13
        
        # Create map
        m = folium.Map(location=center, zoom_start=zoom, tiles="OpenStreetMap")
        
        # Add route and markers
        coords = df[["lat", "lon"]].values.tolist()
        folium.PolyLine(coords, color="red", weight=3).add_to(m)
        folium.Marker(coords[0], popup="Start", icon=folium.Icon(color="green")).add_to(m)
        folium.Marker(coords[-1], popup="End", icon=folium.Icon(color="blue")).add_to(m)
        
        # Add elevation markers if available
        if "Elevation" in df.columns:
            for _, row in df.iloc[::20].iterrows():  # Sample every 20th point
                folium.CircleMarker(
                    [row["lat"], row["lon"]],
                    radius=3,
                    color="brown",
                    fill=True,
                    fill_opacity=0.7,
                    popup=f"Elev: {row['Elevation']} m"
                ).add_to(m)

        # Display map with optimized parameters
        map_data = st_folium(
            m, 
            center=center,
            zoom=zoom,
            width=800, 
            height=500,
            key="folium_map",
            return_on_zoom=False,
            return_on_move=False,
            returned_objects=["last_clicked", "bounds"]
        )
        
        # Update session state only if map data changed
        if map_data and map_data != st.session_state.last_map_data:
            st.session_state.last_map_data = map_data
            if "center" in map_data:
                st.session_state.map_center = map_data["center"]
            if "zoom" in map_data:
                st.session_state.map_zoom = map_data["zoom"]
            
            # Force a rerun to update with new coordinates
            st.rerun()
            
        return map_data

def show_map_static(df: pd.DataFrame):
    """Static map rendering without interactivity"""
    if "lat" in df.columns and "lon" in df.columns and not df.empty:
        center = [df["lat"].mean(), df["lon"].mean()]
        m = folium.Map(location=center, zoom_start=13, tiles="OpenStreetMap")
        
        # Add route and markers
        coords = df[["lat", "lon"]].values.tolist()
        folium.PolyLine(coords, color="red", weight=3).add_to(m)
        folium.Marker(coords[0], popup="Start", icon=folium.Icon(color="green")).add_to(m)
        folium.Marker(coords[-1], popup="End", icon=folium.Icon(color="blue")).add_to(m)
        
        # Use static rendering
        st.components.v1.html(m._repr_html_(), height=500)

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

# Add performance options in sidebar
with st.sidebar:
    st.header("Performance Options")
    st.session_state.use_static_map = st.checkbox("Use Static Map", value=False)
    max_points = st.slider("Max Map Points", 100, 5000, 1000, 
                          help="Reduce for better performance with large files")

if uploaded_file:
    start_time = time.time()
    
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
        
        # Downsample if needed
        if len(df) > max_points:
            original_count = len(df)
            df = downsample_data(df, max_points=max_points)
            st.info(f"Downsampled from {original_count} to {len(df)} points for better performance")
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.subheader("📍 Route Map")
            
            if st.session_state.use_static_map:
                show_map_static(df)
                st.caption("Static map rendering (no interactivity)")
            else:
                map_data = show_map_interactive(df)
                if map_data and "center" in map_data:
                    st.caption(f"Center: {map_data['center']}, Zoom: {map_data.get('zoom', 'N/A')}")
        
        with col2:
            st.subheader("📊 Activity Vitals")
            show_charts(df)

        st.success(f"Loaded {len(df)} records in {time.time() - start_time:.2f} seconds ✅")
        
        with st.expander("View raw data"):
            st.dataframe(df.head())
    else:
        st.error("Failed to process the file or file is empty")
else:
    # Display instructions when no file is uploaded
    st.info("👆 Please upload a FIT or GPX file to get started")
    st.markdown("""
    ### Supported File Formats:
    - **FIT**: Garmin activity files
    - **GPX**: GPS Exchange Format
    - **CSV**: Comma-separated values with latitude/longitude columns
    - **JSON**: JSON files with geographic data
    
    ### Tips for Best Performance:
    - Use the static map option for large files
    - Reduce the max map points for faster rendering
    - FIT files are processed with coordinate conversion
    - GPX files automatically calculate speed from position data
    """)