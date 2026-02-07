import psycopg2
import os

DATABASE_URL = "postgresql://postgres:[YOUR-PASSWORD]@db.ukglpfwaaxjcelwjlepm.supabase.co:5432/postgres"

def get_connection():
    return psycopg2.connect(DATABASE_URL)
