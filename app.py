from flask import Flask, render_template, request, redirect, session, url_for, g
import psycopg2
import os
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv
from db import get_db, close_db

load_dotenv()

app = Flask(__name__)
app.secret_key = 'super_secret_key_for_wizwallet'
app.teardown_appcontext(close_db)

def get_user_stats(cur, user_id):
    """Helper to get common user stats"""
    stats = {'spent_month': 0, 'highest_expense': 0}
    
    # Balance
    cur.execute("""
        SELECT 
            SUM(CASE WHEN transaction_type = 'credit' THEN asset_value ELSE 0 END) - 
            SUM(CASE WHEN transaction_type = 'debit' THEN asset_value ELSE 0 END) 
        FROM assets WHERE user_id = %s AND category = 'main';
    """, (user_id,))
    balance = cur.fetchone()[0] or 0.00
    
    # Vault
    cur.execute("""
        SELECT 
            SUM(CASE WHEN transaction_type = 'credit' THEN asset_value ELSE 0 END) - 
            SUM(CASE WHEN transaction_type = 'debit' THEN asset_value ELSE 0 END) 
        FROM assets WHERE user_id = %s AND category = 'vault';
    """, (user_id,))
    vault_balance = cur.fetchone()[0] or 0.00
    
    # Spent Month
    cur.execute("""
        SELECT SUM(asset_value) FROM assets 
        WHERE user_id = %s AND transaction_type = 'debit' 
        AND date_added >= DATE_TRUNC('month', CURRENT_DATE);
    """, (user_id,))
    stats['spent_month'] = cur.fetchone()[0] or 0.00
    
    return balance, vault_balance, stats

def get_system_stats(cur):
    """Helper to get system-wide stats for Admin"""
    stats = {}
    
    # Total Users
    cur.execute("SELECT COUNT(*) FROM users WHERE role = 'user';")
    stats['total_users'] = cur.fetchone()[0]
    
    # Total Liquidity (Total Money In - Total Money Out)
    cur.execute("""
        SELECT 
            SUM(CASE WHEN transaction_type = 'credit' THEN asset_value ELSE 0 END) - 
            SUM(CASE WHEN transaction_type = 'debit' THEN asset_value ELSE 0 END) 
        FROM assets;
    """)
    stats['total_liquidity'] = cur.fetchone()[0] or 0.00
    
    # Total Transactions
    cur.execute("SELECT COUNT(*) FROM assets;")
    stats['total_transactions'] = cur.fetchone()[0]
    
    # Flow: Credits vs Debits
    cur.execute("SELECT SUM(asset_value) FROM assets WHERE transaction_type = 'credit';")
    stats['total_credits'] = cur.fetchone()[0] or 0.00
    cur.execute("SELECT SUM(asset_value) FROM assets WHERE transaction_type = 'debit';")
    stats['total_debits'] = cur.fetchone()[0] or 0.00
    
    # Trend: Last 7 Days Volume
    # We use a CTE or simple retrieval and fill gaps in Python for simplicity
    cur.execute("""
        SELECT to_char(date_added, 'YYYY-MM-DD'), COUNT(*) 
        FROM assets 
        WHERE date_added >= CURRENT_DATE - INTERVAL '6 days' 
        GROUP BY 1 ORDER BY 1;
    """)
    rows = cur.fetchall()
    
    # Process into lists for Chart.js
    from datetime import datetime, timedelta
    dates = []
    counts = []
    data_dict = {row[0]: row[1] for row in rows}
    
    for i in range(6, -1, -1):
        d = (datetime.now() - timedelta(days=i)).strftime('%Y-%m-%d')
        dates.append(d)
        counts.append(data_dict.get(d, 0))
        
    stats['trend_dates'] = dates
    stats['trend_counts'] = counts
    
    return stats

@app.route('/')
def root():
    if 'user_id' in session:
        return redirect('/dashboard')
    return render_template('landing.html')

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session: return redirect('/login')
    
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SET search_path TO test;")
    
    if session.get('role') == 'admin':
        # Admin View: System Stats
        system_stats = get_system_stats(cur)
        cur.close()
        return render_template('dashboard.html', 
                             active_page='dashboard',
                             admin_mode=True,
                             stats=system_stats)
    
    # Normal User View
    user_id = session['username']
    
    # Get Stats
    balance, vault_balance, stats = get_user_stats(cur, user_id)
    
    # Recent Transactions (Limit 5)
    cur.execute("SELECT id, date_added, asset_name, asset_value, transaction_type, category FROM assets WHERE user_id = %s ORDER BY date_added DESC LIMIT 5;", (user_id,))
    recent_transactions = cur.fetchall()
    cur.close()
    
    return render_template('dashboard.html', 
                         active_page='dashboard',
                         balance=balance,
                         vault_balance=vault_balance,
                         stats=stats,
                         recent_transactions=recent_transactions)

@app.route('/transactions')
def transactions():
    if 'user_id' not in session: return redirect('/login')
    
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SET search_path TO test;")
    
    if session.get('role') == 'admin':
        # Admin: See ALL transactions + user_id
        cur.execute("""
            SELECT id, date_added, asset_name, asset_value, transaction_type, category, user_id 
            FROM assets 
            ORDER BY date_added DESC;
        """)
    else:
        # User: See OWN transactions (user_id is selected for consistency/template logic)
        cur.execute("""
            SELECT id, date_added, asset_name, asset_value, transaction_type, category, user_id 
            FROM assets 
            WHERE user_id = %s 
            ORDER BY date_added DESC;
        """, (session['username'],))
        
    transactions = cur.fetchall()
    cur.close()
    
    return render_template('transactions.html', active_page='transactions', transactions=transactions)

@app.route('/vault')
def vault():
    if 'user_id' not in session: return redirect('/login')
    if session.get('role') == 'admin': return redirect('/dashboard') # Admins have no vault
    
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SET search_path TO test;")
    
    balance, vault_balance, stats = get_user_stats(cur, session['username'])
    cur.close()
    
    return render_template('vault.html', active_page='vault', vault_balance=vault_balance)

@app.route('/admin')
def admin_panel():
    if session.get('role') != 'admin': return redirect('/dashboard')
    
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SET search_path TO test;")
    
    cur.execute("SELECT id, username, role, is_active FROM users ORDER BY id;")
    users_list = cur.fetchall()
    cur.close()
    
    return render_template('admin.html', active_page='admin', users_list=users_list)
    
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        return render_template('login.html')
        
    username = request.form['username']
    password = request.form['password']
    
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SET search_path TO test;")
    cur.execute("SELECT id, username, password_hash, role, is_active FROM users WHERE username = %s;", (username,))
    user = cur.fetchone()
    cur.close()
    
    if user:
         if not user[4]: # is_active
            return render_template('login.html', error="Account Frozen.")
         if check_password_hash(user[2], password):
            session['user_id'] = user[0]
            session['username'] = user[1]
            session['role'] = user[3]
            return redirect('/dashboard')
            
    return render_template('login.html', error="Invalid Credentials")

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'GET':
        return render_template('register.html')
        
    username = request.form['username']
    password = request.form['password']
    hashed_pw = generate_password_hash(password)
    
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SET search_path TO test;")
    try:
        cur.execute("INSERT INTO users (username, password_hash, role) VALUES (%s, %s, %s)", (username, hashed_pw, 'user'))
        conn.commit()
    except psycopg2.IntegrityError:
        conn.rollback()
        cur.close()
        return "Username already taken."
        
    cur.close()
    return redirect('/login')

@app.route('/create_admin', methods=['POST'])
def create_admin():
    if 'role' not in session or session['role'] != 'admin':
        return "Unauthorized", 403
        
    new_admin_name = request.form['username']
    new_admin_pass = request.form['password']
    hashed_pw = generate_password_hash(new_admin_pass)
    
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SET search_path TO test;")
    try:
        cur.execute("INSERT INTO users (username, password_hash, role) VALUES (%s, %s, %s)", (new_admin_name, hashed_pw, 'admin'))
        conn.commit()
    except psycopg2.IntegrityError:
        conn.rollback()
        return "Username already taken."
    
    cur.close()
    return redirect('/admin') # Redirect back to admin panel

@app.route('/transfer', methods=['POST'])
def transfer():
    if 'user_id' not in session: return redirect('/login')
    
    amount = float(request.form['amount'])
    direction = request.form['direction'] # 'deposit' (main->vault) or 'withdraw' (vault->main)
    user_id = session['username']
    
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SET search_path TO test;")
    
    # Check Balance logic inline for simplicity
    if direction == 'deposit':
        source = 'main'
        dest = 'vault'
        desc_debit = "Transfer to Vault"
        desc_credit = "Deposit from Main"
    else:
        source = 'vault'
        dest = 'main'
        desc_debit = "Withdrawal to Main"
        desc_credit = "Transfer from Vault"
        
    cur.execute("""
        SELECT 
            SUM(CASE WHEN transaction_type = 'credit' THEN asset_value ELSE 0 END) - 
            SUM(CASE WHEN transaction_type = 'debit' THEN asset_value ELSE 0 END) 
        FROM assets WHERE user_id = %s AND category = %s;
    """, (user_id, source))
    current_balance = cur.fetchone()[0] or 0.00
    
    if current_balance < amount:
        # Simplified error handling - just redirect back
        # Ideally we use flash messages here
        cur.close()
        return redirect('/vault?error=insufficient_funds')
        
    # Perform Transfer (Atomic)
    # 1. Debit Source
    cur.execute("""
        INSERT INTO assets (asset_name, asset_value, user_id, transaction_type, category) 
        VALUES (%s, %s, %s, 'debit', %s)
    """, (desc_debit, amount, user_id, source))
    
    # 2. Credit Dest
    cur.execute("""
        INSERT INTO assets (asset_name, asset_value, user_id, transaction_type, category) 
        VALUES (%s, %s, %s, 'credit', %s)
    """, (desc_credit, amount, user_id, dest))
    
    conn.commit()
    cur.close()
    
    return redirect('/vault')

@app.route('/add', methods=['POST'])
def add_transaction():
    if 'user_id' not in session:
        return redirect('/')
        
    description = request.form['description']
    amount = request.form['amount']
    transaction_type = request.form.get('transaction_type', 'credit')
    category = request.form.get('category', 'main')
    
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SET search_path TO test;")
    cur.execute("""
        INSERT INTO assets (asset_name, asset_value, user_id, transaction_type, category) 
        VALUES (%s, %s, %s, %s, %s)
    """, (description, amount, session['username'], transaction_type, category))
    conn.commit()
    cur.close()
    
    # Redirect back to where they came from if possible, or default to transactions
    if category == 'vault':
        return redirect('/vault')
    return redirect('/transactions')

@app.route('/admin/delete_transaction/<int:trans_id>', methods=['POST'])
def delete_transaction(trans_id):
    if session.get('role') != 'admin':
        return "Unauthorized", 403
    # ... (Deletion logic same, redirect to dashboard or transactions?) 
    # Since admin view in dashboard was removed in the plan (admin has own panel), 
    # We might need to handle admin seeing transactions. 
    # For now, let's just implement the deletion logic. 
    # WAIT: Admin layout in plan says "User Management Table". 
    # For simplicity, admins can delete from their own view or we add a "Manage Transactions" page.
    # Let's keep it simple: Admin deletes usually happen in a feed. 
    # I'll redirect to dashboard for now or back to referring page.
    
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SET search_path TO test;")
    cur.execute("DELETE FROM assets WHERE id = %s;", (trans_id,))
    conn.commit()
    cur.close()
    return redirect(request.referrer or '/')

@app.route('/admin/toggle_user/<int:user_id>', methods=['POST'])
def toggle_user(user_id):
    if session.get('role') != 'admin': return "Unauthorized", 403
        
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SET search_path TO test;")
    cur.execute("UPDATE users SET is_active = NOT is_active WHERE id = %s;", (user_id,))
    conn.commit()
    cur.close()
    return redirect('/admin')

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')