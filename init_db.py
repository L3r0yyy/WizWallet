import psycopg2
DB_CONFIG = "dbname=test user=leroy password=Pa55ww00rrddd. host=localhost"

try:
    conn = psycopg2.connect(DB_CONFIG)
    cur = conn.cursor()
    # Create schema if it doesn't exist? The error said relation "assets" does not exist, implied schema "test" might exist or default search path Issue.
    # Code sets search_path TO test. So schema test MUST exist.
    # I'll ensure schema exists too just in case, though error was strictly about table.
    
    cur.execute("CREATE SCHEMA IF NOT EXISTS test;")
    cur.execute("SET search_path TO test;")
    
    cur.execute("""
        CREATE TABLE IF NOT EXISTS assets (
            id SERIAL PRIMARY KEY,
            date_added TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            asset_name TEXT NOT NULL,
            asset_value NUMERIC(10, 2) NOT NULL
        );
    """)
    conn.commit()
    print("Table 'assets' created successfully in schema 'test'.")
    cur.close()
    conn.close()
except Exception as e:
    print(f"Error: {e}")
