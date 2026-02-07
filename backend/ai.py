from db import get_connection

def check_anomaly(wallet):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT COUNT(*) 
        FROM vote_attempts
        WHERE wallet = %s
        AND timestamp > NOW() - INTERVAL '1 minute'
    """, (wallet,))

    count = cur.fetchone()[0]

    cur.close()
    conn.close()

    if count > 3:
        return True, "Rapid voting attempts detected"

    return False, None
