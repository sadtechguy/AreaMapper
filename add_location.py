import psycopg2

# --- CONFIGURATION ---
DB_NAME = "postgres"
DB_USER = "postgres"
DB_PASS = "daf#90##salt"  # <--- UPDATE THIS!
DB_HOST = "localhost"

def insert_location(user_id, name, address, lat, lon, loc_type):
    """Takes specific location details and safely inserts them into the database."""
    conn = None
    try:
        conn = psycopg2.connect(
            dbname=DB_NAME, user=DB_USER, password=DB_PASS, host=DB_HOST
        )
        cur = conn.cursor()

        # The SQL INSERT command. Notice the %s placeholders. 
        # This protects your database from bad data or hacking attempts.
        insert_query = """
            INSERT INTO locations (user_id, name, address, latitude, longitude, type)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING location_id;
        """
        
        # Execute the query, pairing the %s placeholders with our actual data
        cur.execute(insert_query, (user_id, name, address, lat, lon, loc_type))
        
        # Grab the newly generated ID
        new_location_id = cur.fetchone()[0]
        
        # Save (commit) the changes to the database
        conn.commit()
        cur.close()
        
        print(f"SUCCESS! '{name}' has been added to the database.")
        print(f"-> Assigned Location ID: {new_location_id}")

    except (Exception, psycopg2.DatabaseError) as error:
        print(f"ERROR: {error}")
    finally:
        if conn is not None:
            conn.close()

# --- RUNNING THE CODE ---
if __name__ == '__main__':
    print("Initializing AreaMapper Database Connection...")
    
    # We are adding a new Drop Point in Bekasi for JktExpress (which is User ID 1)
    insert_location(
        user_id=1,
        name="Drop Point C",
        address="Summarecon Bekasi, West Java",
        lat=-6.223933,
        lon=106.989563,
        loc_type="customer"
    )