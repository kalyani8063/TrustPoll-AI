from db import get_connection, release_connection

def check_anomaly(wallet):
    conn = get_connection()
    cur = conn.cursor()

    try:
        cur.execute("""
            SELECT COUNT(*) 
            FROM vote_attempts
            WHERE wallet = %s
            AND timestamp > NOW() - INTERVAL '1 minute'
        """, (wallet,))

        count = cur.fetchone()[0]
    finally:
        cur.close()
        release_connection(conn)

    if count >= 3:
        return True, "Rapid voting attempts detected"

    return False, None
