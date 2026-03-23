import psycopg2

# --- CLOUD CONFIGURATION ---
# Paste your Neon connection string inside the quotes below!
DATABASE_URL = "postgresql://neondb_owner:npg_fCz4XpU6yKWo@ep-patient-tooth-a1h2fgie-pooler.ap-southeast-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"

def create_tables():
    commands = (
        # 1. Create USERS Table (The Businesses)
        """
        CREATE TABLE IF NOT EXISTS users (
            user_id SERIAL PRIMARY KEY,
            company_name VARCHAR(100) NOT NULL,
            email VARCHAR(255) UNIQUE NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """,
        
        # 2. Create LOCATIONS Table (Warehouses, Customer Spots)
        # We use DECIMAL(9,6) for Lat/Lon because it offers ~11cm precision.
        """
        CREATE TABLE IF NOT EXISTS locations (
            location_id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(user_id) ON DELETE CASCADE,
            name VARCHAR(100),
            address TEXT,
            latitude DECIMAL(9,6),  -- Example: -6.2088 (Jakarta)
            longitude DECIMAL(9,6), -- Example: 106.8456
            type VARCHAR(20)        -- 'warehouse', 'customer', 'driver'
        )
        """,
        
        # 3. Create DELIVERIES Table (The actual work/jobs)
        """
        CREATE TABLE IF NOT EXISTS deliveries (
            delivery_id SERIAL PRIMARY KEY,
            location_id INTEGER REFERENCES locations(location_id),
            driver_name VARCHAR(100),
            status VARCHAR(20) DEFAULT 'Pending', -- 'Pending', 'In Transit', 'Done'
            delivery_date DATE
        )
        """
    )

    conn = None
    try:
        # Connect to the PostgreSQL server
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()

        # Run each command one by one
        for command in commands:
            cur.execute(command)
        
        # Save changes
        cur.close()
        conn.commit()
        print("SUCCESS: AreaMapper database schema created!")
        print("- Table 'users' created.")
        print("- Table 'locations' created.")
        print("- Table 'deliveries' created.")

    except (Exception, psycopg2.DatabaseError) as error:
        print(f"ERROR: {error}")
    finally:
        if conn is not None:
            conn.close()

if __name__ == '__main__':
    create_tables()