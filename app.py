from flask import Flask, render_template, request, redirect
import psycopg2

app = Flask(__name__)

# Using the secure credentials we set up earlier
DB_CONFIG = "dbname=test user=leroy password=Pa55ww00rrddd. host=localhost"

def get_db_connection():
    conn = psycopg2.connect(DB_CONFIG)
    return conn

@app.route('/')
def home():
    conn = get_db_connection()
    cur = conn.cursor()
    # Point to your practice schema
    cur.execute("SET search_path TO test;")
    cur.execute("SELECT date_added, asset_name, asset_value FROM assets ORDER BY date_added DESC;")
    transactions = cur.fetchall()
    
    # Calculate balance
    cur.execute("SELECT SUM(asset_value) FROM assets;")
    total_balance = cur.fetchone()[0] or 0.00
    
    cur.close()
    conn.close()
    return render_template('index.html', transactions=transactions, balance=total_balance)

@app.route('/add', methods=['POST'])
def add_transaction():
    description = request.form['description']
    amount = request.form['amount']
    
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SET search_path TO test;")
    cur.execute("INSERT INTO assets (asset_name, asset_value) VALUES (%s, %s)", (description, amount))
    conn.commit()
    cur.close()
    conn.close()
    return redirect('/')

if __name__ == '__main__':
    app.run(debug=True)