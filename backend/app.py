from dotenv import load_dotenv
load_dotenv()

from flask import Flask, request, jsonify
from flask_cors import CORS
from db import get_connection, release_connection
from ai import check_anomaly
import psycopg2
from datetime import datetime, timedelta
from email_service import send_verification_otp
import random


app = Flask(__name__)
CORS(app)

OTP_STORE = {}
OTP_EXPIRY_MINUTES = 10
OTP_MAX_ATTEMPTS = 3
OTP_RESEND_COOLDOWN_SECONDS = 30


def ensure_schema():
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                email TEXT UNIQUE NOT NULL,
                wallet TEXT UNIQUE NOT NULL,
                blocked_until TIMESTAMP,
                email_verified BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT NOW()
            );
            CREATE TABLE IF NOT EXISTS candidates (
                id SERIAL PRIMARY KEY,
                name TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS votes (
                id SERIAL PRIMARY KEY,
                candidate_id INTEGER NOT NULL REFERENCES candidates(id) ON DELETE CASCADE,
                wallet TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT NOW()
            );
            CREATE TABLE IF NOT EXISTS vote_attempts (
                id SERIAL PRIMARY KEY,
                wallet TEXT NOT NULL,
                election_id TEXT,
                result TEXT NOT NULL,
                timestamp TIMESTAMP DEFAULT NOW()
            );
            CREATE TABLE IF NOT EXISTS ai_flags (
                id SERIAL PRIMARY KEY,
                wallet TEXT NOT NULL,
                reason TEXT NOT NULL,
                severity INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT NOW()
            );
        """)
        cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS blocked_until TIMESTAMP;")
        cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS email_verified BOOLEAN DEFAULT FALSE;")
        cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS votes_wallet_unique ON votes(wallet);")
        conn.commit()
    finally:
        cur.close()
        release_connection(conn)

def is_valid_vit_email(email):
    return isinstance(email, str) and email.endswith("@vit.edu")

def _otp_key(email, wallet):
    return f"{email}|{wallet}"


@app.route("/register/start", methods=["POST"])
def register_start():
    data = request.json or {}
    email = data.get("email")
    raw_wallet = data.get("wallet")
    wallet = raw_wallet.strip().upper() if isinstance(raw_wallet, str) else None

    if not is_valid_vit_email(email):
        return jsonify({"error": "Only @vit.edu emails are allowed."}), 400
    if not wallet:
        return jsonify({"error": "Wallet is required."}), 400

    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT 1 FROM users WHERE wallet = %s", (wallet,))
        if cur.fetchone():
            return jsonify({"error": "Wallet already registered"}), 409
        cur.execute("SELECT 1 FROM users WHERE email = %s", (email,))
        if cur.fetchone():
            return jsonify({"error": "Email already registered"}), 409
    finally:
        cur.close()
        release_connection(conn)

    key = _otp_key(email, wallet)
    now = datetime.utcnow()
    existing = OTP_STORE.get(key)
    if existing and existing.get("last_sent"):
        cooldown_until = existing["last_sent"] + timedelta(seconds=OTP_RESEND_COOLDOWN_SECONDS)
        if now < cooldown_until:
            return jsonify({"error": "Please wait before requesting another code."}), 429

    otp = f"{random.randint(0, 999999):06d}"
    OTP_STORE[key] = {
        "otp": otp,
        "expires_at": now + timedelta(minutes=OTP_EXPIRY_MINUTES),
        "attempts": 0,
        "last_sent": now,
    }

    send_verification_otp(email, otp)
    return jsonify({"message": "Verification code sent"}), 200


@app.route("/register/verify", methods=["POST"])
def register_verify():
    data = request.json or {}
    email = data.get("email")
    raw_wallet = data.get("wallet")
    wallet = raw_wallet.strip().upper() if isinstance(raw_wallet, str) else None
    otp = data.get("otp")

    key = _otp_key(email, wallet)
    record = OTP_STORE.get(key)
    if not record:
        return jsonify({"error": "Verification code not found. Please request a new code."}), 400

    if record["attempts"] >= OTP_MAX_ATTEMPTS:
        return jsonify({"error": "Too many attempts. Please request a new code."}), 429

    if datetime.utcnow() > record["expires_at"]:
        return jsonify({"error": "Verification code expired. Please request a new code."}), 400

    if otp != record["otp"]:
        record["attempts"] += 1
        return jsonify({"error": "Invalid verification code."}), 400

    conn = None
    cur = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO users (email, wallet, email_verified) VALUES (%s, %s, %s)",
            (email, wallet, True)
        )
        conn.commit()
    except psycopg2.errors.UniqueViolation:
        if conn:
            conn.rollback()
        return jsonify({"error": "Email or wallet already registered"}), 409
    except Exception:
        if conn:
            conn.rollback()
        return jsonify({"error": "Database error"}), 500
    finally:
        if cur:
            cur.close()
        if conn:
            release_connection(conn)

    OTP_STORE.pop(key, None)
    return jsonify({"message": "Email verified and registration complete"}), 200


@app.route("/register", methods=["POST"])
def register():
    return jsonify({"error": "Use /register/start and /register/verify for email verification."}), 410


@app.route("/login", methods=["POST"])
def login():
    data = request.json or {}
    email = data.get("email")
    wallet = data.get("wallet")

    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT blocked_until, email_verified FROM users WHERE email = %s AND wallet = %s", (email, wallet))
        user = cur.fetchone()
        if user:
            blocked_until, email_verified = user
            if blocked_until and blocked_until > datetime.utcnow():
                return jsonify({"error": "Account temporarily blocked. Please try again later."}), 403
            if not email_verified:
                return jsonify({"error": "Please verify your email before logging in."}), 403
            return jsonify({"message": "Login successful"})
        return jsonify({"error": "Invalid credentials"}), 401
    finally:
        cur.close()
        release_connection(conn)


@app.route("/candidates", methods=["GET"])
def get_candidates():
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT id, name FROM candidates ORDER BY name")
        rows = cur.fetchall()
        return jsonify([{"id": r[0], "name": r[1]} for r in rows])
    finally:
        cur.close()
        release_connection(conn)


@app.route("/vote", methods=["POST"])
def vote():
    data = request.json or {}
    wallet = data.get("wallet")
    candidate_id = data.get("candidate_id")

    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT blocked_until, email_verified FROM users WHERE wallet = %s", (wallet,))
        user = cur.fetchone()
        if not user:
            return jsonify({"error": "User not found"}), 404
        blocked_until, email_verified = user
        if blocked_until and blocked_until > datetime.utcnow():
            return jsonify({"error": "Account temporarily blocked. Please try again later."}), 403
        if not email_verified:
            return jsonify({"error": "Please verify your email before voting."}), 403

        cur.execute("""
            SELECT COUNT(*) 
            FROM vote_attempts
            WHERE wallet = %s
            AND timestamp > NOW() - INTERVAL '5 minutes'
        """, (wallet,))
        recent_attempts = cur.fetchone()[0]

        suspicious = recent_attempts >= 3
        reason = "Rapid voting attempts detected" if suspicious else None

        cur.execute("""
            INSERT INTO vote_attempts (wallet, election_id, result)
            VALUES (%s, %s, %s)
        """, (wallet, None, "flagged" if suspicious else "ok"))

        if suspicious:
            cur.execute("""
                INSERT INTO ai_flags (wallet, reason, severity)
                VALUES (%s, %s, %s)
            """, (wallet, reason, 7))
            conn.commit()
            return jsonify({"error": reason}), 403
        # Commit attempt logging before vote write so attempts are recorded
        conn.commit()

        cur.execute(
            "INSERT INTO votes (candidate_id, wallet) VALUES (%s, %s) ON CONFLICT (wallet) DO NOTHING",
            (candidate_id, wallet)
        )
        if cur.rowcount == 0:
            return jsonify({"error": "You have already voted"}), 400
        conn.commit()
        return jsonify({"message": "Vote cast successfully"})
    finally:
        cur.close()
        release_connection(conn)


@app.route("/vote-attempt", methods=["POST"])
def vote_attempt():
    data = request.json or {}
    wallet = data["wallet"]
    election_id = data.get("election_id")

    suspicious, reason = check_anomaly(wallet)

    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO vote_attempts (wallet, election_id, result)
            VALUES (%s, %s, %s)
        """, (wallet, election_id, "flagged" if suspicious else "ok"))

        if suspicious:
            cur.execute("""
                INSERT INTO ai_flags (wallet, reason, severity)
                VALUES (%s, %s, %s)
            """, (wallet, reason, 7))

        conn.commit()
        return jsonify({
            "allowed": not suspicious,
            "reason": reason
        })
    finally:
        cur.close()
        release_connection(conn)


@app.route("/admin/add-candidate", methods=["POST"])
def add_candidate():
    data = request.json or {}
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"error": "Candidate name is required"}), 400

    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("INSERT INTO candidates (name) VALUES (%s) RETURNING id", (name,))
        candidate_id = cur.fetchone()[0]
        conn.commit()
        return jsonify({"message": "Candidate added", "id": candidate_id, "name": name})
    finally:
        cur.close()
        release_connection(conn)


@app.route("/admin/candidates", methods=["GET"])
def admin_candidates():
    conn = get_connection()
    cur = conn.cursor()
    try:
        query = "SELECT c.id, c.name, COUNT(v.wallet) FROM candidates c LEFT JOIN votes v ON c.id = v.candidate_id GROUP BY c.id ORDER BY c.name"
        cur.execute(query)
        rows = cur.fetchall()
        return jsonify([{"id": r[0], "name": r[1], "votes": r[2]} for r in rows])
    finally:
        cur.close()
        release_connection(conn)


@app.route("/admin/stats", methods=["GET"])
def admin_stats():
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT COUNT(*) FROM users")
        users = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM vote_attempts")
        vote_attempts = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM ai_flags")
        ai_flags = cur.fetchone()[0]
        return jsonify({"users": users, "vote_attempts": vote_attempts, "ai_flags": ai_flags})
    finally:
        cur.close()
        release_connection(conn)


@app.route("/admin/ai-flags", methods=["GET"])
def admin_ai_flags():
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT wallet, reason, severity, created_at FROM ai_flags ORDER BY created_at DESC")
        rows = cur.fetchall()
        return jsonify([
            {"wallet": r[0], "reason": r[1], "severity": r[2], "created_at": r[3].isoformat()}
            for r in rows
        ])
    finally:
        cur.close()
        release_connection(conn)


@app.route("/admin/acknowledge-flag", methods=["POST"])
def admin_acknowledge_flag():
    data = request.json or {}
    wallet = data.get("wallet")
    if not wallet:
        return jsonify({"error": "Wallet is required"}), 400
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM ai_flags WHERE wallet = %s", (wallet,))
        conn.commit()
        return jsonify({"message": "Flag acknowledged"})
    finally:
        cur.close()
        release_connection(conn)


@app.route("/admin/block-wallet", methods=["POST"])
def admin_block_wallet():
    data = request.json or {}
    wallet = data.get("wallet")
    minutes = data.get("minutes", 30)
    try:
        minutes = int(minutes)
    except Exception:
        minutes = 30
    if not wallet:
        return jsonify({"error": "Wallet is required"}), 400
    if minutes <= 0:
        return jsonify({"error": "Minutes must be positive"}), 400

    conn = get_connection()
    cur = conn.cursor()
    try:
        blocked_until = datetime.utcnow() + timedelta(minutes=minutes)
        cur.execute("UPDATE users SET blocked_until = %s WHERE wallet = %s", (blocked_until, wallet))
        if cur.rowcount == 0:
            return jsonify({"error": "Wallet not found"}), 404
        conn.commit()
        return jsonify({"message": "Wallet blocked", "blocked_until": blocked_until.isoformat()})
    finally:
        cur.close()
        release_connection(conn)


@app.route("/health")
def health():
    return "Backend running"


if __name__ == "__main__":
    ensure_schema()
    app.run(debug=True)
