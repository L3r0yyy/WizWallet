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
    
    cur.execute("DROP TABLE IF EXISTS assets;")
    cur.execute("""
        CREATE TABLE assets (
            id SERIAL PRIMARY KEY,
            date_added TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            asset_name TEXT NOT NULL,
            asset_value NUMERIC(10, 2) NOT NULL,
            user_id TEXT NOT NULL,
            transaction_type TEXT CHECK (transaction_type IN ('credit', 'debit')) NOT NULL,
            category TEXT DEFAULT 'main'
        );
    """)

    cur.execute("DROP TABLE IF EXISTS users;")
    cur.execute("""
        CREATE TABLE users (
            id SERIAL PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT CHECK (role IN ('admin', 'user')) NOT NULL,
            is_active BOOLEAN DEFAULT TRUE
        );
    """)

    # Seed the initial admin (Password: AdminSecure789)
    from werkzeug.security import generate_password_hash
    admin_pw_hash = generate_password_hash('AdminSecure789')
    cur.execute("INSERT INTO users (username, password_hash, role) VALUES (%s, %s, %s)", ('boss', admin_pw_hash, 'admin'))

    conn.commit()
    print("Tables 'assets' and 'users' created/seeded successfully.")
    cur.close()
    conn.close()
except Exception as e:
    print(f"Error: {e}")
