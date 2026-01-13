import psycopg2
from flask import g

DB_CONFIG = "dbname=test user=leroy password=Pa55ww00rrddd. host=localhost"

def get_db():
    if 'db' not in g:
        g.db = psycopg2.connect(DB_CONFIG)
    return g.db

def close_db(e=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()
