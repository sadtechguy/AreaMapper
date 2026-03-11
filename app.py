import streamlit as st
import streamlit_authenticator as stauth
import psycopg2
import pandas as pd
import folium
import requests
from streamlit_folium import st_folium
from geopy.geocoders import Nominatim

st.set_page_config(page_title="AreaMapper", layout="wide")
st.title("📍 AreaMapper Logistics Dashboard (Cloud Edition)")

# --- SECURE CLOUD CONNECTION ---
# Streamlit automatically looks in .streamlit/secrets.toml for this URL
DATABASE_URL = st.secrets["DATABASE_URL"]

# --- AUTHENTICATION SETUP ---
# Fetch the credentials and cookie settings from secrets.toml
credentials = st.secrets["credentials"].to_dict()
cookie_name = st.secrets["cookie"]["name"]
cookie_key = st.secrets["cookie"]["key"]
cookie_expiry = st.secrets["cookie"]["expiry_days"]

# Initialize the authenticator
authenticator = stauth.Authenticate(
    credentials,
    cookie_name,
    cookie_key,
    cookie_expiry
)

# Display the login widget on the main screen
authenticator.login()

# --- THE SECURITY GATE ---
if st.session_state["authentication_status"] is False:
    st.error('Username/password is incorrect')
    
elif st.session_state["authentication_status"] is None:
    st.warning('Please enter your username and password to access AreaMapper')
    
elif st.session_state["authentication_status"]:
    # 🟢 IF LOGIN IS SUCCESSFUL, SHOW THE APP!
    
    # Put a logout button in the sidebar
    authenticator.logout('Logout', 'sidebar')
    st.sidebar.write(f'Welcome, *{st.session_state["name"]}*')

    # --- NEW: Check if the logged-in user is the boss ---
    is_admin = st.session_state["username"] == "admin"
    
    # ==========================================
    # 🚨 INDENT EVERYTHING ELSE BELOW THIS LINE! 🚨
    # ==========================================

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

    def update_location_details(old_name, new_name, new_address, new_type):
        """Updates the text details of an existing location."""
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        query = """
            UPDATE locations 
            SET name = %s, address = %s, type = %s 
            WHERE name = %s
        """
        cur.execute(query, (new_name, new_address, new_type, old_name))
        conn.commit()
        cur.close()
        conn.close()

    def delete_location_from_db(location_name):
        """Deletes a location AND its associated delivery record to prevent database errors."""
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        
        # 1. Delete the linked delivery first (using Postgres' USING clause)
        query_deliveries = """
            DELETE FROM deliveries 
            USING locations 
            WHERE deliveries.location_id = locations.location_id 
            AND locations.name = %s
        """
        cur.execute(query_deliveries, (location_name,))
        
        # 2. Now it is safe to delete the location
        query_locations = "DELETE FROM locations WHERE name = %s"
        cur.execute(query_locations, (location_name,))
        
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
        
    def get_driving_route(start_lat, start_lon, end_lat, end_lon):
        """Fetches driving route coordinates from the free OSRM API."""
        try:
            # OSRM requires coordinates in Longitude,Latitude format
            url = f"http://router.project-osrm.org/route/v1/driving/{start_lon},{start_lat};{end_lon},{end_lat}?overview=full&geometries=geojson"
            
            response = requests.get(url)
            if response.status_code == 200:
                data = response.json()
                # Extract the raw route data
                route_coords = data['routes'][0]['geometry']['coordinates']
                
                # Folium needs [Latitude, Longitude], but OSRM gives [Longitude, Latitude]
                # So we flip them around in this list!
                folium_route = [[coord[1], coord[0]] for coord in route_coords]
                return folium_route
            return None
        except Exception as e:
            st.error(f"Routing error: {e}")
            return None
        
    # ==========================================
    # 🚨 CRITICAL FIX: LOAD DATA FIRST
    # We must load the data before the sidebar or the main UI tries to use it!
    # ==========================================

    df = load_data()
    # --- SIDEBAR: SMART DATA ENTRY FORM ---
    if is_admin:
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
    # Create two tabs for the main dashboard
    # Conditional Tabs!
    if is_admin:
        tab1, tab2 = st.tabs(["🗺️ Live Map", "📊 Admin Dashboard"])
    else:
        tab1 = st.container() # Driver just gets a normal screen for the map
        tab2 = None           # Driver doesn't get a second tab

    # --- TAB 1: THE OPERATIONS MAP ---
    with tab1:
        col1, col2 = st.columns([1, 2])
        
        with col1:
            st.subheader("Data Overview")
            st.dataframe(df[["Location", "Address", "Status"]], use_container_width=True)
        
        with col2:
            st.subheader("Live Operations Map")
            m = folium.Map(location=[-6.25, 106.75], zoom_start=11)
            
            # --- NEW: Find the Warehouse starting point ---
            # We look inside 'df' for the first location that is marked as a warehouse
            warehouse_data = df[df['type'] == 'warehouse']
            if not warehouse_data.empty:
                warehouse = warehouse_data.iloc[0] # Grab the first warehouse we find
            else:
                warehouse = None
            
            # --- Draw Markers and Routes ---
            for index, row in df.iterrows():
                if pd.notna(row['latitude']) and pd.notna(row['longitude']):
                    
                    # 1. Set Marker Colors
                    if row['type'] == 'warehouse':
                        color = "blue"
                    elif row['Status'] == 'Done':
                        color = "green"
                    else:
                        color = "red"
                        
                    # 2. Place the Marker
                    folium.Marker(
                        location=[row['latitude'], row['longitude']],
                        popup=f"<b>{row['Location']}</b><br>Status: {row['Status']}",
                        icon=folium.Icon(color=color)
                    ).add_to(m)
                    
                    # 3. NEW: Draw the Driving Route!
                    # If we have a warehouse, and this location is an active delivery...
                    if warehouse is not None and row['type'] != 'warehouse' and row['Status'] in ['Pending', 'In Transit']:
                        
                        # Ask OSRM for the path
                        route_coords = get_driving_route(
                            warehouse['latitude'], warehouse['longitude'],
                            row['latitude'], row['longitude']
                        )
                        
                        # If OSRM successfully gives us the path, draw a line!
                        if route_coords:
                            folium.PolyLine(
                                locations=route_coords,
                                color="#3388ff", # A nice bright routing blue
                                weight=3,        # Thickness of the line
                                opacity=0.8
                            ).add_to(m)
                    
            st_folium(m, width=800, height=500)

    # --- TAB 2: THE ADMIN DASHBOARD ---
    if is_admin:
        with tab2:
            st.subheader("Delivery Status Summary")
            
            # 1. Filter out the warehouses to only look at actual deliveries
            deliveries_only = df[df['Status'] != 'No Delivery']
            
            # 2. Count how many deliveries are in each status
            total_deliveries = len(deliveries_only)
            done_count = len(deliveries_only[deliveries_only['Status'] == 'Done'])
            transit_count = len(deliveries_only[deliveries_only['Status'] == 'In Transit'])
            pending_count = len(deliveries_only[deliveries_only['Status'] == 'Pending'])
            
            # 3. Display the numbers using Streamlit 'metrics' (big beautiful numbers)
            m1, m2, m3, m4 = st.columns(4)
            m1.metric(label="Total Deliveries", value=total_deliveries)
            m2.metric(label="Completed ✅", value=done_count)
            m3.metric(label="In Transit 🚚", value=transit_count)
            m4.metric(label="Pending ⏳", value=pending_count)
            
            st.markdown("---")
            
            # 4. Show a clean table of only the active/completed jobs
            st.subheader("Delivery Roster")
            st.dataframe(deliveries_only[["Location", "Address", "Status", "type"]], use_container_width=True)

            # ==========================================
            # --- VERSION 3.0: DATABASE MANAGEMENT ---
            # ==========================================
            st.markdown("---")
            st.subheader("🛠️ Database Management")
            
            # Get a list of ALL locations (warehouses and customers)
            all_locations = df['Location'].tolist()
            
            if all_locations:
                loc_to_manage = st.selectbox("Select a Location to Edit or Delete", all_locations)
                
                # Find the current details of the selected location so we can pre-fill the edit form
                current_details = df[df['Location'] == loc_to_manage].iloc[0]
                
                # Create two columns so the Edit and Delete forms sit side-by-side
                manage_col1, manage_col2 = st.columns(2)
                
                # --- EDIT FORM ---
                with manage_col1:
                    with st.form("edit_location_form"):
                        st.write("**✏️ Edit Location Details**")
                        
                        # Pre-fill the inputs with the existing data
                        edit_name = st.text_input("Name", value=current_details['Location'])
                        edit_address = st.text_input("Address", value=current_details['Address'])
                        
                        # Figure out which dropdown option should be selected by default
                        type_index = 0 if current_details['type'] == 'customer' else 1
                        edit_type = st.selectbox("Location Type", ["customer", "warehouse"], index=type_index)
                        
                        update_btn = st.form_submit_button("Save Changes")
                        
                        if update_btn:
                            update_location_details(loc_to_manage, edit_name, edit_address, edit_type)
                            st.success(f"Successfully updated '{loc_to_manage}'!")
                            st.cache_data.clear()
                            st.rerun()
                            
                # --- DELETE FORM ---
                with manage_col2:
                    with st.form("delete_location_form"):
                        st.write("**🗑️ Delete Location**")
                        st.warning(f"Warning: This will permanently erase '{loc_to_manage}' and its delivery history.")
                        
                        # Use type="primary" to make the delete button stand out (usually turns it red)
                        delete_btn = st.form_submit_button("Permanently Delete", type="primary")
                        
                        if delete_btn:
                            delete_location_from_db(loc_to_manage)
                            st.success(f"Successfully deleted '{loc_to_manage}'.")
                            st.cache_data.clear()
                            st.rerun()