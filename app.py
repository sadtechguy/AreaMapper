import streamlit as st
import psycopg2
import pandas as pd
import folium
from streamlit_folium import st_folium
from geopy.geocoders import Nominatim

st.set_page_config(page_title="AreaMapper", layout="wide")
st.title("📍 AreaMapper Logistics Dashboard (Cloud Edition)")

# --- SECURE CLOUD CONNECTION ---
# Streamlit automatically looks in .streamlit/secrets.toml for this URL
DATABASE_URL = st.secrets["DATABASE_URL"]

# --- DATABASE LOGIC ---
@st.cache_data(ttl=10) 
def load_data():
    # Connecting using the secure URL
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    query = """
        SELECT l.name AS "Location", l.address AS "Address", 
               l.latitude, l.longitude, l.type, COALESCE(d.status, 'No Delivery') AS "Status"
        FROM locations l
        LEFT JOIN deliveries d ON l.location_id = d.location_id;
    """
    cur.execute(query)
    records = cur.fetchall()
    columns = [desc[0] for desc in cur.description]
    df = pd.DataFrame(records, columns=columns)
    cur.close()
    conn.close()
    return df

def insert_location_to_db(name, address, lat, lon, loc_type):
    # Connecting using the secure URL
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    query = """
        INSERT INTO locations (user_id, name, address, latitude, longitude, type)
        VALUES (%s, %s, %s, %s, %s, %s)
    """
    cur.execute(query, (1, name, address, lat, lon, loc_type))
    conn.commit()
    cur.close()
    conn.close()

def update_delivery_status(location_name, new_status):
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    # This SQL finds the delivery associated with a specific location name and updates it
    query = """
        UPDATE deliveries 
        SET status = %s 
        FROM locations 
        WHERE deliveries.location_id = locations.location_id 
        AND locations.name = %s
    """
    cur.execute(query, (new_status, location_name))
    conn.commit()
    cur.close()
    conn.close()

def get_coordinates(address_text):
    geolocator = Nominatim(user_agent="AreaMapper_App")
    try:
        location = geolocator.geocode(address_text + ", Indonesia")
        if location:
            return location.latitude, location.longitude
        return None, None
    except:
        return None, None
    
# ==========================================
# 🚨 CRITICAL FIX: LOAD DATA FIRST
# We must load the data before the sidebar or the main UI tries to use it!
# ==========================================

df = load_data()
# --- SIDEBAR: SMART DATA ENTRY FORM ---
st.sidebar.header("➕ Add New Drop Point")

# 1. MOVED OUTSIDE THE FORM: Now it triggers an instant UI update!
manual_override = st.sidebar.checkbox("I have exact coordinates")

# 2. THE FORM:
with st.sidebar.form("add_location_form"):
    new_name = st.text_input("Location Name", placeholder="e.g., Hidden Warehouse")
    new_address = st.text_input("Address", placeholder="e.g., Unmapped Street 123")
    new_type = st.selectbox("Location Type", ["customer", "warehouse"])
    
    st.markdown("---")
    
    # These will now correctly unlock when the box above is checked
    manual_lat = st.number_input("Latitude", value=-6.200000, format="%.6f", disabled=not manual_override)
    manual_lon = st.number_input("Longitude", value=106.816666, format="%.6f", disabled=not manual_override)
    
    submitted = st.form_submit_button("Save to Database")
    
    if submitted:
        if new_name and new_address:
            lat, lon = None, None
            
            if manual_override:
                lat, lon = manual_lat, manual_lon
                source_msg = "Saved with manual coordinates"
            else:
                with st.spinner('Calculating coordinates automatically...'):
                    lat, lon = get_coordinates(new_address)
                    source_msg = "Address mapped automatically"
            
            if lat and lon:
                insert_location_to_db(new_name, new_address, lat, lon, new_type)
                st.sidebar.success(f"{source_msg}! Added {new_name} to map.")
                st.cache_data.clear()
                st.rerun()
            else:
                st.sidebar.error("Could not find that address. Please check the 'exact coordinates' box and enter them manually.")
        else:
            st.sidebar.error("Please fill in both the Name and Address.")

# --- SECTION 2: UPDATE STATUS ---
st.sidebar.markdown("---") # Visual separator line
st.sidebar.subheader("Manage Deliveries")

# Get a list of locations that have deliveries to show in the dropdown
delivery_locations = df[df['Status'] != 'No Delivery']['Location'].tolist()

if delivery_locations:
    selected_loc = st.sidebar.selectbox("Select Location", delivery_locations)
    new_stat = st.sidebar.selectbox("New Status", ["Pending", "In Transit", "Done"])
    
    if st.sidebar.button("Update Status"):
        update_delivery_status(selected_loc, new_stat)
        st.success(f"Updated {selected_loc} to {new_stat}!")
        st.rerun() # Refresh the app to show the new color on the map
else:
    st.sidebar.info("No active deliveries to manage.")


# --- MAIN UI ---
col1, col2 = st.columns([1, 2])

with col1:
    st.subheader("Data Overview")
    st.dataframe(df[["Location", "Address", "Status"]], use_container_width=True)

with col2:
    st.subheader("Live Operations Map")
    m = folium.Map(location=[-6.25, 106.75], zoom_start=11)
    
    for index, row in df.iterrows():
        if pd.notna(row['latitude']) and pd.notna(row['longitude']):
            if row['type'] == 'warehouse':
                color = "blue"
            elif row['Status'] == 'Done':
                color = "green"
            else:
                color = "red"
                
            folium.Marker(
                location=[row['latitude'], row['longitude']],
                popup=f"<b>{row['Location']}</b><br>Status: {row['Status']}",
                icon=folium.Icon(color=color)
            ).add_to(m)
            
    st_folium(m, width=800, height=500)