import json
import hashlib
from db import get_connection, release_connection

def check_anomaly(identity_key):
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT COUNT(*) 
            FROM vote_attempts
            WHERE wallet = %s
            AND timestamp > NOW() - INTERVAL '1 minute'
        """, (identity_key,))

        count = cur.fetchone()[0]
    finally:
        cur.close()
        release_connection(conn)

    return payload, payload_hash
