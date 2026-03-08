import psycopg2

# --- CLOUD CONFIGURATION ---
# PASTE YOUR NEON CONNECTION STRING INSIDE THE QUOTES BELOW:
DATABASE_URL = "postgresql://neondb_owner:npg_fCz4XpU6yKWo@ep-patient-tooth-a1h2fgie-pooler.ap-southeast-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"

def insert_dummy_data():
    conn = None
    try:
        # Connecting directly to your Neon server
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()

        print("Inserting dummy data into Cloud AreaMapper...")

        # 1. Insert a Company (User)
        cur.execute("""
            INSERT INTO users (company_name, email) 
            VALUES (%s, %s) RETURNING user_id;
        """, ("JktExpress Logistics", "admin@jktexpress.co.id"))
        
        user_id = cur.fetchone()[0]
        print(f"-> Created User 'JktExpress Logistics' with ID: {user_id}")

        # 2. Insert Locations (Jakarta, Tangerang, and Bekasi)
        locations_data = [
            (user_id, "Central Hub", "Jl. Sudirman, Jakarta", -6.208800, 106.845600, "warehouse"),
            (user_id, "Drop Point A", "BSD City, South Tangerang", -6.300641, 106.643596, "customer"),
            (user_id, "Drop Point B", "Alam Sutera, Tangerang", -6.225012, 106.653115, "customer"),
            (user_id, "Drop Point C", "Summarecon Bekasi, West Java", -6.223933, 106.989563, "customer")
        ]

        location_ids = []
        for loc in locations_data:
            cur.execute("""
                INSERT INTO locations (user_id, name, address, latitude, longitude, type)
                VALUES (%s, %s, %s, %s, %s, %s) RETURNING location_id;
            """, loc)
            loc_id = cur.fetchone()[0]
            location_ids.append(loc_id)
            print(f"-> Added Location: {loc[1]}")

        # 3. Insert Deliveries for those locations
        deliveries_data = [
            (location_ids[1], "Budi", "In Transit", "2026-03-05"), # Going to BSD
            (location_ids[2], "Budi", "Done", "2026-03-05"),       # Completed in Alam Sutera
            (location_ids[3], "Siti", "Pending", "2026-03-08")     # Going to Bekasi
        ]

        for dev in deliveries_data:
            cur.execute("""
                INSERT INTO deliveries (location_id, driver_name, status, delivery_date)
                VALUES (%s, %s, %s, %s);
            """, dev)
            print(f"-> Assigned Delivery to driver: {dev[1]}")

        # Save all changes to the cloud database
        conn.commit()
        cur.close()
        print("\nSUCCESS: All data inserted perfectly into the cloud!")

    except (Exception, psycopg2.DatabaseError) as error:
        print(f"ERROR: {error}")
    finally:
        if conn is not None:
            conn.close()

if __name__ == '__main__':
    insert_dummy_data()