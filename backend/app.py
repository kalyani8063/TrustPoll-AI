import hashlib
import json
import os
import random
import time
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

import psycopg2
from algosdk import account, mnemonic, transaction
from algosdk.v2client import algod
from dotenv import load_dotenv
from flask import Flask, jsonify, request
from flask_cors import CORS
from werkzeug.security import check_password_hash, generate_password_hash

load_dotenv()

from ai import check_anomaly
from algorand_client import AlgorandGovernanceClient
from db import get_connection, release_connection
from email_service import send_verification_otp
from session_utils import create_session_token, verify_session_token

app = Flask(__name__)
CORS(app)

OTP_STORE: dict[str, dict[str, Any]] = {}
OTP_EXPIRY_MINUTES = 10
OTP_MAX_ATTEMPTS = 3
OTP_RESEND_COOLDOWN_SECONDS = 30
ELECTION_ID = os.getenv("ELECTION_ID", "default-election")
SESSION_TTL_SECONDS = int(os.getenv("SESSION_TTL_SECONDS", "3600"))
IDEMPOTENCY_PENDING_SECONDS = int(os.getenv("IDEMPOTENCY_PENDING_SECONDS", "20"))

ALGOD_ADDRESS = os.getenv("ALGORAND_ALGOD_ADDRESS")
ALGOD_TOKEN = os.getenv("ALGORAND_ALGOD_TOKEN", "")
ALGOD_APP_ID = int(os.getenv("ALGORAND_APP_ID", "0"))
SERVICE_MNEMONIC = os.getenv("ALGORAND_SERVICE_MNEMONIC")
ALGOD_HEADERS = {"X-API-Key": ALGOD_TOKEN} if ALGOD_TOKEN else {}

algod_client: algod.AlgodClient | None = None
private_key: str | None = None
sender_address: str | None = None
ALGOD_SETUP_ERROR: str | None = None
try:
    if not ALGOD_ADDRESS:
        raise RuntimeError("ALGORAND_ALGOD_ADDRESS is required")
    if not SERVICE_MNEMONIC:
        raise RuntimeError("ALGORAND_SERVICE_MNEMONIC is required")
    if ALGOD_APP_ID <= 0:
        raise RuntimeError("ALGORAND_APP_ID must be a positive integer")
    algod_client = algod.AlgodClient(ALGOD_TOKEN, ALGOD_ADDRESS, headers=ALGOD_HEADERS)
    private_key = mnemonic.to_private_key(SERVICE_MNEMONIC)
    sender_address = account.address_from_private_key(private_key)
except Exception as exc:
    ALGOD_SETUP_ERROR = str(exc)

ALGO_CLIENT: AlgorandGovernanceClient | None = None
ALGO_INIT_ERROR: str | None = None
try:
    ALGO_CLIENT = AlgorandGovernanceClient()
except Exception as exc:  # noqa: BLE001
    ALGO_INIT_ERROR = str(exc)


def ensure_schema() -> None:
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                email TEXT UNIQUE NOT NULL,
                wallet TEXT UNIQUE NOT NULL,
                password_hash TEXT,
                blocked_until TIMESTAMP,
                email_verified BOOLEAN DEFAULT FALSE,
                has_voted BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT NOW()
            );

            CREATE TABLE IF NOT EXISTS candidates (
                id SERIAL PRIMARY KEY,
                name TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS votes (
                id SERIAL PRIMARY KEY,
                election_id TEXT NOT NULL,
                candidate_id INTEGER REFERENCES candidates(id) ON DELETE CASCADE,
                wallet TEXT NOT NULL,
                email_hash TEXT,
                vote_hash TEXT,
                tx_id TEXT,
                confirmed_round BIGINT,
                block_timestamp BIGINT,
                created_at TIMESTAMP DEFAULT NOW()
            );

            CREATE TABLE IF NOT EXISTS pending_votes (
                id SERIAL PRIMARY KEY,
                election_id TEXT NOT NULL,
                email_hash TEXT NOT NULL,
                candidate_id INTEGER,
                vote_hash TEXT NOT NULL,
                status TEXT NOT NULL,
                tx_id TEXT,
                last_error TEXT,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW(),
                UNIQUE (election_id, email_hash)
            );

            CREATE TABLE IF NOT EXISTS vote_attempts (
                id SERIAL PRIMARY KEY,
                wallet TEXT NOT NULL,
                election_id TEXT,
                result TEXT NOT NULL,
                ip_hash TEXT,
                device_fingerprint_hash TEXT,
                timestamp TIMESTAMP DEFAULT NOW()
            );

            CREATE TABLE IF NOT EXISTS ai_flags (
                id SERIAL PRIMARY KEY,
                wallet TEXT NOT NULL,
                reason TEXT NOT NULL,
                severity INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT NOW()
            );

            CREATE TABLE IF NOT EXISTS audit_events (
                id SERIAL PRIMARY KEY,
                event_type TEXT NOT NULL,
                severity TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                entry_hash TEXT NOT NULL,
                anchored_tx_id TEXT,
                anchored_round BIGINT,
                created_at TIMESTAMP DEFAULT NOW()
            );

            CREATE TABLE IF NOT EXISTS governance_state (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT NOW()
            );

            CREATE TABLE IF NOT EXISTS fairness_snapshots (
                id SERIAL PRIMARY KEY,
                fairness_json TEXT NOT NULL,
                fairness_hash TEXT NOT NULL,
                tx_id TEXT,
                round BIGINT,
                score NUMERIC NOT NULL,
                created_at TIMESTAMP DEFAULT NOW()
            );
            """
        )

        cur.execute("ALTER TABLE votes ADD COLUMN IF NOT EXISTS election_id TEXT;")
        cur.execute("ALTER TABLE votes ADD COLUMN IF NOT EXISTS email_hash TEXT;")
        cur.execute("ALTER TABLE votes ADD COLUMN IF NOT EXISTS vote_hash TEXT;")
        cur.execute("ALTER TABLE votes ADD COLUMN IF NOT EXISTS tx_id TEXT;")
        cur.execute("ALTER TABLE votes ADD COLUMN IF NOT EXISTS confirmed_round BIGINT;")
        cur.execute("ALTER TABLE votes ADD COLUMN IF NOT EXISTS block_timestamp BIGINT;")
        cur.execute("ALTER TABLE votes ALTER COLUMN candidate_id DROP NOT NULL;")
        cur.execute("ALTER TABLE pending_votes ALTER COLUMN candidate_id DROP NOT NULL;")
        cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS blocked_until TIMESTAMP;")
        cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS email_verified BOOLEAN DEFAULT FALSE;")
        cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS password_hash TEXT;")
        cur.execute("DROP INDEX IF EXISTS votes_wallet_unique;")
        cur.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS votes_unique_election_email
            ON votes (election_id, email_hash)
            WHERE email_hash IS NOT NULL;
            """
        )
        cur.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS votes_unique_vote_hash
            ON votes (vote_hash)
            WHERE vote_hash IS NOT NULL;
            """
        )
        cur.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS votes_unique_tx_id
            ON votes (tx_id)
            WHERE tx_id IS NOT NULL;
            """
        )
        cur.execute(
            """
            INSERT INTO governance_state (key, value)
            VALUES ('governance_status', 'HEALTHY')
            ON CONFLICT (key) DO NOTHING;
            """
        )
        conn.commit()
    finally:
        cur.close()
        release_connection(conn)


def canonical_json(data: dict[str, Any]) -> str:
    return json.dumps(data, sort_keys=True, separators=(",", ":"))


def sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def normalize_email(email: str) -> str:
    return email.strip().lower()


def normalize_wallet(wallet: str) -> str:
    return wallet.strip().upper()


def is_valid_vit_email(email: str) -> bool:
    return isinstance(email, str) and normalize_email(email).endswith("@vit.edu")


def _otp_key(email: str) -> str:
    return normalize_email(email)


def _algo_or_error() -> tuple[AlgorandGovernanceClient | None, tuple[dict[str, str], int] | None]:
    if ALGO_CLIENT is None:
        return None, ({"error": f"Blockchain client unavailable: {ALGO_INIT_ERROR or 'unknown error'}"}, 503)
    return ALGO_CLIENT, None


def _algod_or_error() -> tuple[algod.AlgodClient | None, tuple[dict[str, str], int] | None]:
    if algod_client is None or private_key is None or sender_address is None:
        return None, ({"error": f"Algod client unavailable: {ALGOD_SETUP_ERROR or 'unknown error'}"}, 503)
    return algod_client, None


def wait_for_confirmation(client: algod.AlgodClient, txid: str, timeout: int = 10) -> dict[str, Any]:
    start_round = client.status()["last-round"]
    current_round = start_round
    while current_round < start_round + timeout:
        pending_txn = client.pending_transaction_info(txid)
        if pending_txn.get("confirmed-round", 0) > 0:
            return pending_txn
        if pending_txn.get("pool-error"):
            raise RuntimeError(f"Transaction rejected: {pending_txn['pool-error']}")
        current_round += 1
        client.status_after_block(current_round)
    raise TimeoutError("Transaction not confirmed within timeout")


def submit_candidate_app_call(method_name: bytes, candidate_id: int, timeout: int = 10) -> dict[str, int | str]:
    client, err = _algod_or_error()
    if err:
        raise RuntimeError(err[0]["error"])
    sp = client.suggested_params()
    txn = transaction.ApplicationCallTxn(
        sender=sender_address,
        sp=sp,
        index=ALGOD_APP_ID,
        on_complete=transaction.OnComplete.NoOpOC,
        app_args=[method_name, int(candidate_id).to_bytes(8, "big")],
    )
    signed_txn = txn.sign(private_key)
    tx_id = client.send_transaction(signed_txn)
    confirmed_txn = wait_for_confirmation(client, tx_id, timeout=timeout)
    confirmed_round = int(confirmed_txn["confirmed-round"])
    return {"tx_id": tx_id, "confirmed_round": confirmed_round}


def _extract_session() -> tuple[dict[str, Any] | None, tuple[dict[str, str], int] | None]:
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None, ({"error": "Missing bearer session token"}, 401)
    token = auth_header.split(" ", 1)[1].strip()
    try:
        payload = verify_session_token(token)
        return payload, None
    except ValueError as exc:
        return None, ({"error": str(exc)}, 401)


def get_governance_status(conn) -> str:
    cur = conn.cursor()
    try:
        cur.execute("SELECT value FROM governance_state WHERE key = 'governance_status'")
        row = cur.fetchone()
        return row[0] if row else "UNKNOWN"
    finally:
        cur.close()


def set_governance_status(conn, status: str) -> None:
    cur = conn.cursor()
    try:
        cur.execute(
            """
            INSERT INTO governance_state (key, value, updated_at)
            VALUES ('governance_status', %s, NOW())
            ON CONFLICT (key)
            DO UPDATE SET value = EXCLUDED.value, updated_at = NOW();
            """,
            (status,),
        )
    finally:
        cur.close()


def anchor_audit_event(event_type: str, severity: str, payload: dict[str, Any]) -> None:
    entry = {
        "event_type": event_type,
        "severity": severity,
        "payload": payload,
        "timestamp": int(time.time()),
    }
    payload_json = canonical_json(entry)
    entry_hash = sha256_hex(payload_json)
    anchored_tx_id = None
    anchored_round = None

    if severity in ("HIGH", "CRITICAL") and ALGO_CLIENT:
        try:
            anchored = ALGO_CLIENT.anchor_note_hash(entry_hash)
            anchored_tx_id = str(anchored["tx_id"])
            anchored_round = int(anchored["confirmed_round"])
        except Exception:
            pass

    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            INSERT INTO audit_events (event_type, severity, payload_json, entry_hash, anchored_tx_id, anchored_round)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (event_type, severity, payload_json, entry_hash, anchored_tx_id, anchored_round),
        )
        conn.commit()
    finally:
        cur.close()
        release_connection(conn)


def recalculate_fairness(trigger: str) -> dict[str, Any]:
    algo, err = _algo_or_error()
    if err:
        raise RuntimeError(err[0]["error"])

    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT COUNT(*) FROM votes WHERE tx_id IS NULL OR tx_id = ''")
        missing_tx = int(cur.fetchone()[0])

        cur.execute("SELECT tx_id FROM votes WHERE tx_id IS NOT NULL")
        tx_ids = [row[0] for row in cur.fetchall()]

        invalid_tx = 0
        for tx_id in tx_ids:
            try:
                verification = algo.verify_vote_transaction(tx_id)
                if verification.get("status") != "SUCCESS":
                    invalid_tx += 1
            except Exception:
                invalid_tx += 1

        governance_status = get_governance_status(conn)
        penalty = 0
        penalties: dict[str, int] = {}
        if missing_tx > 0:
            penalties["missing_vote_tx"] = min(40, missing_tx * 10)
            penalty += penalties["missing_vote_tx"]
        if invalid_tx > 0:
            penalties["invalid_vote_tx"] = min(40, invalid_tx * 5)
            penalty += penalties["invalid_vote_tx"]
        if governance_status == "COMPROMISED":
            penalties["governance_compromised"] = 30
            penalty += 30

        score = max(Decimal("0"), Decimal("100") - Decimal(str(penalty)))
        fairness_payload = {
            "trigger": trigger,
            "computed_at": int(time.time()),
            "missing_vote_tx_count": missing_tx,
            "invalid_vote_tx_count": invalid_tx,
            "governance_status": governance_status,
            "penalties": penalties,
            "score": float(score),
        }
        fairness_json = canonical_json(fairness_payload)
        fairness_hash = sha256_hex(fairness_json)
        anchor = algo.anchor_note_hash(fairness_hash)
        cur.execute(
            """
            INSERT INTO fairness_snapshots (fairness_json, fairness_hash, tx_id, round, score)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (
                fairness_json,
                fairness_hash,
                str(anchor["tx_id"]),
                int(anchor["confirmed_round"]),
                score,
            ),
        )
        conn.commit()
        fairness_payload["tx_id"] = str(anchor["tx_id"])
        fairness_payload["confirmed_round"] = int(anchor["confirmed_round"])
        fairness_payload["fairness_hash"] = fairness_hash
        return fairness_payload
    finally:
        cur.close()
        release_connection(conn)


def reconcile_audit_anchors() -> dict[str, Any]:
    algo, err = _algo_or_error()
    if err:
        raise RuntimeError(err[0]["error"])

    conn = get_connection()
    cur = conn.cursor()
    compromised = False
    checked = 0
    try:
        cur.execute(
            """
            SELECT id, payload_json, entry_hash, anchored_tx_id
            FROM audit_events
            WHERE severity IN ('HIGH', 'CRITICAL')
            AND anchored_tx_id IS NOT NULL
            ORDER BY id
            """
        )
        rows = cur.fetchall()
        for row in rows:
            _, payload_json, stored_hash, anchored_tx_id = row
            checked += 1
            recomputed = sha256_hex(payload_json)
            if recomputed != stored_hash:
                compromised = True
                continue
            try:
                note_text = algo.fetch_note_text(anchored_tx_id)
            except Exception:
                note_text = None
            if note_text != stored_hash:
                compromised = True

        if compromised:
            set_governance_status(conn, "COMPROMISED")
            conn.commit()
            anchor_audit_event(
                "governance_compromised",
                "CRITICAL",
                {"reason": "Audit reconciliation mismatch"},
            )
        fairness = recalculate_fairness("audit_reconciliation")
        return {
            "checked_events": checked,
            "governance_status": "COMPROMISED" if compromised else get_governance_status(conn),
            "fairness": fairness,
        }
    finally:
        cur.close()
        release_connection(conn)

@app.route("/register/start", methods=["POST"])
def register_start():
    data = request.json or {}
    email = normalize_email(str(data.get("email", "")))

    if not is_valid_vit_email(email):
        return jsonify({"error": "Only @vit.edu emails are allowed."}), 400

    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT 1 FROM users WHERE email = %s", (email,))
        if cur.fetchone():
            return jsonify({"error": "Email already registered"}), 409
    finally:
        cur.close()
        release_connection(conn)

    key = _otp_key(email)
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
    email = normalize_email(str(data.get("email", "")))
    otp = str(data.get("otp", "")).strip()
    password = str(data.get("password", ""))
    if len(password) < 8:
        return jsonify({"error": "Password must be at least 8 characters."}), 400
    password_hash = generate_password_hash(password)

    key = _otp_key(email)
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
        user_ref = _derive_user_ref(email)
        password_hash = generate_password_hash(password)

        cur.execute(
            "INSERT INTO users (email, wallet, password_hash, email_verified) VALUES (%s, %s, %s, %s)",
            (email, email, password_hash, True),
        )
        conn.commit()
    except psycopg2.errors.UniqueViolation:
        if conn:
            conn.rollback()
        return jsonify({"error": "Email already registered"}), 409
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
    try:
        send_registration_success_email(email)
    except Exception:
        pass

    return jsonify({"message": "Email verified and registration complete"}), 200


@app.route("/register", methods=["POST"])
def register():
    return jsonify({"error": "Use /register/start and /register/verify."}), 410


@app.route("/login", methods=["POST"])
def login():
    data = request.json or {}
    email = normalize_email(str(data.get("email", "")))
    password = str(data.get("password", ""))
    if not password:
        return jsonify({"error": "Password is required"}), 400

    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT blocked_until, email_verified, password_hash FROM users WHERE email = %s",
            (email,),
        )
        user = cur.fetchone()
        if not user:
            return jsonify({"error": "Invalid credentials"}), 401

        blocked_until, email_verified, password_hash = user
        if blocked_until and blocked_until > datetime.utcnow():
            return jsonify({"error": "Account temporarily blocked. Please try again later."}), 403
        if not email_verified:
            return jsonify({"error": "Please verify your email before logging in."}), 403
        if not password_hash:
            return jsonify({"error": "Password not set for this account. Re-register to continue."}), 403
        if not check_password_hash(password_hash, password):
            return jsonify({"error": "Invalid credentials"}), 401

        session_token = create_session_token(email=email, ttl_seconds=SESSION_TTL_SECONDS)
        return jsonify({"message": "Login successful", "session_token": session_token, "email": email})
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
    client, err = _algod_or_error()
    if err:
        return jsonify(err[0]), err[1]

    session_payload, session_err = _extract_session()
    if session_err:
        return jsonify(session_err[0]), session_err[1]

    data = request.json or {}
    candidate_id_raw = data.get("candidate_id")
    try:
        candidate_id = int(candidate_id_raw)
    except (TypeError, ValueError):
        return jsonify({"error": "candidate_id must be an integer"}), 400

    email = normalize_email(str(session_payload["email"]))

    email_hash = sha256_hex(email)
    timestamp = int(time.time())
    canonical_payload = {
        "election_id": ELECTION_ID,
        "email_hash": email_hash,
        "candidate_id": candidate_id,
        "timestamp": timestamp,
    }
    vote_hash = sha256_hex(canonical_json(canonical_payload))

    if not email or not candidate_id:
        return jsonify({"error": "Email and candidate_id are required"}), 400

    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT blocked_until, email_verified FROM users WHERE email = %s", (email,))
        user = cur.fetchone()
        if not user:
            return jsonify({"error": "User not found"}), 404
        blocked_until, email_verified, has_voted, user_ref = user
        if blocked_until and blocked_until > datetime.utcnow():
            return jsonify({"error": "Account temporarily blocked. Please try again later."}), 403
        if not email_verified:
            return jsonify({"error": "Please verify your email before voting."}), 403

        cur.execute("SELECT 1 FROM candidates WHERE id = %s", (candidate_id,))
        if not cur.fetchone():
            return jsonify({"error": "Candidate not found"}), 404

        cur.execute(
            """
            SELECT tx_id, confirmed_round, vote_hash
            FROM votes
            WHERE election_id = %s AND email_hash = %s
            """,
            (ELECTION_ID, email_hash),
        )
        existing_vote = cur.fetchone()
        if existing_vote:
            tx_id, confirmed_round, existing_vote_hash = existing_vote
            return (
                jsonify(
                    {
                        "status": "SUCCESS",
                        "tx_id": tx_id,
                        "confirmed_round": confirmed_round,
                        "vote_hash": existing_vote_hash,
                    }
                ),
                200,
            )

        cur.execute(
            """
            SELECT status, tx_id, updated_at
            FROM pending_votes
            WHERE election_id = %s AND email_hash = %s
            """,
            (ELECTION_ID, email_hash),
        )
        pending = cur.fetchone()
        if pending:
            pending_status, pending_tx_id, updated_at = pending
            if pending_status == "confirmed" and pending_tx_id:
                return jsonify({"status": "SUCCESS", "tx_id": pending_tx_id, "vote_hash": vote_hash}), 200
            if pending_status == "pending" and updated_at > datetime.utcnow() - timedelta(seconds=IDEMPOTENCY_PENDING_SECONDS):
                return jsonify({"error": "Vote submission already in progress"}), 409

        cur.execute(
            """
            INSERT INTO pending_votes (election_id, email_hash, vote_hash, status, updated_at)
            VALUES (%s, %s, %s, 'pending', NOW())
            ON CONFLICT (election_id, email_hash)
            DO UPDATE SET vote_hash = EXCLUDED.vote_hash, status = 'pending', updated_at = NOW()
            """,
            (ELECTION_ID, email_hash, vote_hash),
        )

        cur.execute(
            """
            SELECT COUNT(*)
            FROM vote_attempts
            WHERE wallet = %s AND timestamp > NOW() - INTERVAL '5 minutes'
            """,
            (email,),
        )
        recent_attempts = int(cur.fetchone()[0])
        suspicious = recent_attempts >= 3
        reason = "Rapid voting attempts detected" if suspicious else None
        cur.execute(
            "INSERT INTO vote_attempts (wallet, election_id, result) VALUES (%s, %s, %s)",
            (email, ELECTION_ID, "flagged" if suspicious else "ok"),
        )
        if suspicious:
            cur.execute(
                "INSERT INTO ai_flags (wallet, reason, severity) VALUES (%s, %s, %s)",
                (email, reason, 7),
            )
            conn.commit()
            anchor_audit_event(
                "vote_blocked",
                "HIGH",
                {"email": email, "reason": reason},
            )
            return jsonify({"error": reason}), 403

        conn.commit()
    finally:
        cur.close()
        release_connection(conn)

    try:
        sp = client.suggested_params()
        txn = transaction.ApplicationCallTxn(
            sender=sender_address,
            sp=sp,
            index=ALGOD_APP_ID,
            on_complete=transaction.OnComplete.NoOpOC,
            app_args=[b"vote", bytes.fromhex(email_hash), candidate_id.to_bytes(8, "big")],
            boxes=[(0, b"voter_" + bytes.fromhex(email_hash))],
        )
        signed_txn = txn.sign(private_key)
        tx_id = client.send_transaction(signed_txn)
        confirmed_txn = wait_for_confirmation(client, tx_id, timeout=10)
        confirmed_round = int(confirmed_txn["confirmed-round"])
        block_info = client.block_info(confirmed_round)
        block_timestamp = int(block_info["block"]["ts"])
    except Exception as exc:
        err_msg = str(exc)
        conn = get_connection()
        cur = conn.cursor()
        try:
            cur.execute(
                """
                UPDATE pending_votes
                SET status = 'failed', last_error = %s, updated_at = NOW()
                WHERE election_id = %s AND email_hash = %s
                """,
                (err_msg, ELECTION_ID, email_hash),
            )
            conn.commit()
        finally:
            cur.close()
            release_connection(conn)
        anchor_audit_event(
            "vote_chain_failure",
            "CRITICAL",
            {"email": email, "error": err_msg},
        )
        return jsonify({"error": "Blockchain transaction failed; vote not recorded"}), 502

    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            INSERT INTO votes (
                election_id,
                wallet,
                email_hash,
                vote_hash,
                tx_id,
                confirmed_round,
                block_timestamp
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (election_id, email_hash)
            WHERE email_hash IS NOT NULL
            DO NOTHING
            """,
            (
                ELECTION_ID,
                email,
                email_hash,
                vote_hash,
                tx_id,
                confirmed_round,
                block_timestamp,
            ),
        )
        if cur.rowcount == 0:
            cur.execute(
                "SELECT tx_id, confirmed_round, vote_hash FROM votes WHERE election_id = %s AND email_hash = %s",
                (ELECTION_ID, email_hash),
            )
            existing = cur.fetchone()
            conn.commit()
            return (
                jsonify(
                    {
                        "status": "SUCCESS",
                        "tx_id": existing[0],
                        "confirmed_round": existing[1],
                        "vote_hash": existing[2],
                    }
                ),
                200,
            )

        cur.execute(
            """
            UPDATE pending_votes
            SET status = 'confirmed', tx_id = %s, last_error = NULL, updated_at = NOW()
            WHERE election_id = %s AND email_hash = %s
            """,
            (tx_id, ELECTION_ID, email_hash),
        )
        conn.commit()
    finally:
        cur.close()
        release_connection(conn)

    try:
        recalculate_fairness("vote_cast")
    except Exception:
        pass

    return jsonify({"status": "SUCCESS", "tx_id": tx_id, "confirmed_round": confirmed_round, "vote_hash": vote_hash})


@app.route("/vote/status", methods=["GET"])
def vote_status():
    session_payload, session_err = _extract_session()
    if session_err:
        return jsonify(session_err[0]), session_err[1]

    email = normalize_email(str(session_payload["email"]))
    email_hash = sha256_hex(email)

    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT tx_id, confirmed_round, vote_hash, block_timestamp
            FROM votes
            WHERE election_id = %s AND email_hash = %s
            ORDER BY id DESC
            LIMIT 1
            """,
            (ELECTION_ID, email_hash),
        )
        row = cur.fetchone()
        if not row:
            return jsonify({"has_voted": False, "election_id": ELECTION_ID})
        return jsonify(
            {
                "has_voted": True,
                "election_id": ELECTION_ID,
                "tx_id": row[0],
                "confirmed_round": row[1],
                "vote_hash": row[2],
                "block_timestamp": row[3],
            }
        )
    finally:
        cur.close()
        release_connection(conn)


@app.route("/results", methods=["GET"])
def results():
    algo, err = _algo_or_error()
    if err:
        return jsonify(err[0]), err[1]

    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT id, name FROM candidates ORDER BY name")
        candidate_rows = cur.fetchall()
    finally:
        cur.close()
        release_connection(conn)

    ids = [row[0] for row in candidate_rows]
    chain_counts = algo.get_candidate_counts(ids)
    response = [{"id": cid, "name": name, "votes": int(chain_counts.get(cid, 0))} for cid, name in candidate_rows]
    return jsonify({"election_id": ELECTION_ID, "source": "blockchain", "results": response})


@app.route("/verify/vote/<tx_id>", methods=["GET"])
def verify_vote(tx_id: str):
    algo, err = _algo_or_error()
    if err:
        return jsonify(err[0]), err[1]
    try:
        verification = algo.verify_vote_transaction(tx_id)
        return jsonify(verification)
    except Exception as exc:
        return jsonify({"status": "FAILED", "error": str(exc)}), 404


@app.route("/vote-attempt", methods=["POST"])
def vote_attempt():
    data = request.json or {}
    email = normalize_email(str(data.get("email", "")))
    election_id = data.get("election_id") or ELECTION_ID
    suspicious, reason = check_anomaly(email)

    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO vote_attempts (wallet, election_id, result) VALUES (%s, %s, %s)",
            (email, election_id, "flagged" if suspicious else "ok"),
        )
        if suspicious:
            cur.execute(
                "INSERT INTO ai_flags (wallet, reason, severity) VALUES (%s, %s, %s)",
                (email, reason, 7),
            )
            anchor_audit_event("vote_attempt_flagged", "HIGH", {"email": email, "reason": reason})
        conn.commit()
        return jsonify({"allowed": not suspicious, "reason": reason})
    finally:
        cur.close()
        release_connection(conn)


@app.route("/admin/add-candidate", methods=["POST"])
def add_candidate():
    _, err = _algod_or_error()
    if err:
        return jsonify(err[0]), err[1]

    data = request.json or {}
    admin_id = (data.get("admin_id") or "unknown-admin").strip()
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"error": "Candidate name is required"}), 400

    voting_active = _is_voting_window_active()
    has_anchor = _has_any_anchoring_activity()
    risk_level = "LOW"
    event_type = "CANDIDATE_ADDED"
    if voting_active:
        risk_level = "HIGH"
        event_type = "CANDIDATE_ADDED_DURING_VOTING_WINDOW"
    elif has_anchor:
        risk_level = "HIGH"
        event_type = "CANDIDATE_ADDED_AFTER_ANCHORING"
    log_admin_event(
        admin_id=admin_id,
        event_type=event_type,
        election_id=FAIRNESS_DEFAULT_ELECTION_ID,
        event_details={"candidate_name": name, "voting_window_active": voting_active, "anchoring_active": has_anchor},
        risk_level=risk_level,
    )

    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT nextval(pg_get_serial_sequence('candidates', 'id'))")
        candidate_id = int(cur.fetchone()[0])
    finally:
        cur.close()
        release_connection(conn)

    try:
        chain_result = submit_candidate_app_call(b"add_candidate", candidate_id, timeout=10)
    except Exception as exc:
        anchor_audit_event(
            "candidate_add_chain_failure",
            "CRITICAL",
            {"candidate_id": candidate_id, "name": name, "error": str(exc)},
        )
        return jsonify({"error": "Blockchain transaction failed; candidate not added"}), 502

    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("INSERT INTO candidates (id, name) VALUES (%s, %s)", (candidate_id, name))
        conn.commit()
    finally:
        cur.close()
        release_connection(conn)

    anchor_audit_event(
        "candidate_added",
        "HIGH",
        {
            "candidate_id": candidate_id,
            "name": name,
            "tx_id": chain_result["tx_id"],
            "confirmed_round": chain_result["confirmed_round"],
        },
    )
    return jsonify(
        {
            "message": "Candidate added",
            "id": candidate_id,
            "name": name,
            "tx_id": chain_result["tx_id"],
            "confirmed_round": chain_result["confirmed_round"],
        }
    )


@app.route("/admin/candidates", methods=["GET"])
def admin_candidates():
    algo, err = _algo_or_error()
    if err:
        return jsonify(err[0]), err[1]

    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT id, name FROM candidates ORDER BY name")
        rows = cur.fetchall()
    finally:
        cur.close()
        release_connection(conn)

    counts = algo.get_candidate_counts([r[0] for r in rows])
    return jsonify([{"id": r[0], "name": r[1], "votes": int(counts.get(r[0], 0))} for r in rows])


@app.route("/admin/stats", methods=["GET"])
def admin_stats():
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT COUNT(*) FROM users")
        users = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM vote_attempts")
        vote_attempts_count = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM ai_flags")
        ai_flags = cur.fetchone()[0]
        governance_status = get_governance_status(conn)
        return jsonify(
            {
                "users": users,
                "vote_attempts": vote_attempts_count,
                "ai_flags": ai_flags,
                "governance_status": governance_status,
            }
        )
    finally:
        cur.close()
        release_connection(conn)


@app.route("/admin/fairness-index", methods=["GET", "POST"])
def admin_fairness_index():
    if request.method == "GET":
        election_id = (request.args.get("election_id") or FAIRNESS_DEFAULT_ELECTION_ID).strip()
        conn = get_connection()
        cur = conn.cursor()
        try:
            cur.execute(
                """
                SELECT fairness_payload, fairness_hash, fairness_score, algorand_tx_id, computed_at
                FROM fairness_reports
                WHERE election_id = %s
                ORDER BY computed_at DESC
                LIMIT 1
                """,
                (election_id,),
            )
            row = cur.fetchone()
        finally:
            cur.close()
            release_connection(conn)

        if not row:
            payload = _compute_fairness_index(election_id)
            return jsonify(
                {
                    "election_id": election_id,
                    "fairness_score": payload["fairness_score"],
                    "metrics": payload["metrics"],
                    "penalties": payload["penalties"],
                    "formula": payload["formula"],
                    "governance": payload.get("governance", {}),
                    "governance_risk_flag": bool(payload.get("governance_risk_flag")),
                    "fairness_hash": _deterministic_hash(payload),
                    "algorand_tx_id": None,
                    "anchored": False,
                    "computed_at": payload["computed_at"],
                }
            )

        payload, fairness_hash, fairness_score, algorand_tx_id, computed_at = row
        if isinstance(payload, str):
            payload = json.loads(payload)
        return jsonify(
            {
                "election_id": election_id,
                "fairness_score": float(fairness_score),
                "metrics": payload.get("metrics", {}),
                "penalties": payload.get("penalties", {}),
                "formula": payload.get("formula", {}),
                "governance": payload.get("governance", {}),
                "governance_risk_flag": bool(payload.get("governance_risk_flag")),
                "fairness_hash": fairness_hash,
                "algorand_tx_id": algorand_tx_id,
                "anchored": bool(algorand_tx_id),
                "computed_at": computed_at.isoformat() if computed_at else None,
            }
        )

    data = request.json or {}
    election_id = (data.get("election_id") or FAIRNESS_DEFAULT_ELECTION_ID).strip()
    should_anchor = bool(data.get("anchor", True))
    admin_id = (data.get("admin_id") or "unknown-admin").strip()
    payload = _compute_fairness_index(election_id)
    fairness_hash = _deterministic_hash(payload)
    algorand_tx_id = None

    if should_anchor:
        try:
            algorand_tx_id = anchor_decision_hash(fairness_hash, voter_ref=f"fairness:{election_id}")
        except Exception:
            algorand_tx_id = None

    log_admin_event(
        admin_id=admin_id,
        event_type="FAIRNESS_INDEX_COMPUTED",
        election_id=election_id,
        event_details={"anchoring_requested": should_anchor, "anchored": bool(algorand_tx_id), "fairness_hash": fairness_hash},
        risk_level="MEDIUM",
    )

    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            INSERT INTO fairness_reports (election_id, fairness_payload, fairness_hash, fairness_score, algorand_tx_id)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (election_id, json.dumps(payload, sort_keys=True), fairness_hash, payload["fairness_score"], algorand_tx_id),
        )
        conn.commit()
    finally:
        cur.close()
        release_connection(conn)

    return jsonify(
        {
            "election_id": election_id,
            "fairness_score": payload["fairness_score"],
            "metrics": payload["metrics"],
            "penalties": payload["penalties"],
            "formula": payload["formula"],
            "governance": payload.get("governance", {}),
            "governance_risk_flag": bool(payload.get("governance_risk_flag")),
            "fairness_hash": fairness_hash,
            "algorand_tx_id": algorand_tx_id,
            "anchored": bool(algorand_tx_id),
            "computed_at": payload["computed_at"],
        }
    )


@app.route("/admin/delete-candidate", methods=["POST"])
def delete_candidate():
    data = request.json or {}
    admin_id = (data.get("admin_id") or "unknown-admin").strip()
    candidate_id = data.get("id")
    if not candidate_id:
        return jsonify({"error": "Candidate id is required"}), 400

    voting_active = _is_voting_window_active()
    has_anchor = _has_any_anchoring_activity()
    risk_level = "MEDIUM"
    event_type = "CANDIDATE_DELETED"
    if voting_active:
        risk_level = "CRITICAL"
        event_type = "CANDIDATE_DELETED_DURING_VOTING_WINDOW"
    elif has_anchor:
        risk_level = "HIGH"
        event_type = "CANDIDATE_DELETED_AFTER_ANCHORING"
    log_admin_event(
        admin_id=admin_id,
        event_type=event_type,
        election_id=FAIRNESS_DEFAULT_ELECTION_ID,
        event_details={"candidate_id": candidate_id, "voting_window_active": voting_active, "anchoring_active": has_anchor},
        risk_level=risk_level,
    )

    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM candidates WHERE id = %s", (candidate_id,))
        if cur.rowcount == 0:
            return jsonify({"error": "Candidate not found"}), 404
        conn.commit()
        return jsonify({"message": "Candidate deleted"})
    finally:
        cur.close()
        release_connection(conn)


@app.route("/admin/results-status", methods=["GET"])
def admin_results_status():
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT published, published_at FROM results_publication WHERE id = 1")
        row = cur.fetchone()
        published = bool(row[0]) if row else False
        published_at = row[1].isoformat() if row and row[1] else None
        return jsonify({"published": published, "published_at": published_at})
    finally:
        cur.close()
        release_connection(conn)


@app.route("/admin/publish-results", methods=["POST"])
def admin_publish_results():
    data = request.json or {}
    admin_id = (data.get("admin_id") or "unknown-admin").strip()
    publish = bool(data.get("published"))
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT published FROM results_publication WHERE id = 1")
        row = cur.fetchone()
        currently_published = bool(row[0]) if row else False

        voting_active = _is_voting_window_active()
        has_anchor = _has_any_anchoring_activity()
        risk_level = "LOW"
        event_type = "ELECTION_STATE_MODIFIED"
        if voting_active:
            risk_level = "HIGH"
            event_type = "ELECTION_METADATA_CHANGED_DURING_VOTE_WINDOW"
        if has_anchor:
            risk_level = "HIGH"
            event_type = "ELECTION_STATE_MODIFIED_AFTER_ANCHORING"
        if currently_published and not publish:
            risk_level = "CRITICAL"
            event_type = "RESULTS_UNPUBLISHED_AFTER_PUBLICATION"

        log_admin_event(
            admin_id=admin_id,
            event_type=event_type,
            election_id=FAIRNESS_DEFAULT_ELECTION_ID,
            event_details={
                "from_published": currently_published,
                "to_published": publish,
                "voting_window_active": voting_active,
                "anchoring_active": has_anchor,
            },
            risk_level=risk_level,
        )

        if publish:
            cur.execute("UPDATE results_publication SET published = TRUE, published_at = NOW() WHERE id = 1")
        else:
            cur.execute("UPDATE results_publication SET published = FALSE, published_at = NULL WHERE id = 1")
        conn.commit()
        return jsonify({"published": publish})
    finally:
        cur.close()
        release_connection(conn)


@app.route("/results", methods=["GET"])
def public_results():
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT published FROM results_publication WHERE id = 1")
        row = cur.fetchone()
        if not row or not row[0]:
            return jsonify({"published": False, "results": []})

        query = """
            SELECT c.id, c.name, COUNT(v.wallet)
            FROM candidates c
            LEFT JOIN votes v ON c.id = v.candidate_id
            GROUP BY c.id
            ORDER BY COUNT(v.wallet) DESC, c.name
        """
        cur.execute(query)
        rows = cur.fetchall()
        results = [{"id": r[0], "name": r[1], "votes": r[2]} for r in rows]
        governance_summary = get_governance_audit_summary(FAIRNESS_DEFAULT_ELECTION_ID)
        governance_compromised = governance_summary.get("governance_integrity_status") == "COMPROMISED"
        cur.execute(
            """
            SELECT fairness_payload, fairness_hash, fairness_score, algorand_tx_id, computed_at
            FROM fairness_reports
            WHERE election_id = %s
            ORDER BY computed_at DESC
            LIMIT 1
            """,
            (FAIRNESS_DEFAULT_ELECTION_ID,),
        )
        fairness_row = cur.fetchone()
        fairness_public = None
        if fairness_row:
            fairness_payload, fairness_hash, fairness_score, fairness_tx_id, fairness_computed_at = fairness_row
            if isinstance(fairness_payload, str):
                fairness_payload = json.loads(fairness_payload)
            fairness_public = {
                "fairness_score": float(fairness_score),
                "formula": fairness_payload.get("formula", {}),
                "metrics": fairness_payload.get("metrics", {}),
                "governance_risk_flag": bool(fairness_payload.get("governance_risk_flag")),
                "fairness_hash": fairness_hash,
                "algorand_tx_id": fairness_tx_id,
                "computed_at": fairness_computed_at.isoformat() if fairness_computed_at else None,
            }
        return jsonify(
            {
                "published": True,
                "results": results,
                "fairness_index": fairness_public,
                "governance_integrity_audit": governance_summary,
                "governance_integrity_status": "COMPROMISED" if governance_compromised else "HEALTHY",
                "governance_warning": "Governance Integrity Compromised" if governance_compromised else None,
            }
        )
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
        return jsonify(
            [
                {
                    "email": r[0],
                    "reason": r[1],
                    "severity": r[2],
                    "created_at": r[3].isoformat(),
                }
                for r in rows
            ]
        )
    finally:
        cur.close()
        release_connection(conn)


@app.route("/admin/audit-events", methods=["GET"])
def admin_audit_events():
    limit_raw = request.args.get("limit", "100")
    try:
        limit = max(1, min(500, int(limit_raw)))
    except ValueError:
        limit = 100

    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT event_type, severity, payload_json, entry_hash, anchored_tx_id, anchored_round, created_at
            FROM audit_events
            ORDER BY created_at DESC
            LIMIT %s
            """,
            (limit,),
        )
        rows = cur.fetchall()
        events: list[dict[str, Any]] = []
        for row in rows:
            payload = None
            if row[2]:
                try:
                    payload = json.loads(row[2])
                except Exception:
                    payload = row[2]
            events.append(
                {
                    "event_type": row[0],
                    "severity": row[1],
                    "payload": payload,
                    "entry_hash": row[3],
                    "anchored_tx_id": row[4],
                    "anchored_round": row[5],
                    "created_at": row[6].isoformat(),
                }
            )
        return jsonify(events)
    finally:
        cur.close()
        release_connection(conn)


@app.route("/admin/acknowledge-flag", methods=["POST"])
def admin_acknowledge_flag():
    data = request.json or {}
    email = normalize_email(str(data.get("email", "")))
    if not email:
        return jsonify({"error": "Email is required"}), 400

    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM ai_flags WHERE wallet = %s", (email,))
        conn.commit()
        return jsonify({"message": "Flag acknowledged"})
    finally:
        cur.close()
        release_connection(conn)


@app.route("/admin/block-email", methods=["POST"])
@app.route("/admin/block-wallet", methods=["POST"])
def admin_block_email():
    data = request.json or {}
    email = normalize_email(str(data.get("email", "")))
    minutes = data.get("minutes", 30)
    try:
        minutes = int(minutes)
    except Exception:
        minutes = 30
    if not email:
        return jsonify({"error": "Email is required"}), 400
    if minutes <= 0:
        return jsonify({"error": "Minutes must be positive"}), 400

    voting_active = _is_voting_window_active()
    risk_level = "MEDIUM"
    event_type = "USER_BLOCKED_BY_ADMIN"
    if voting_active:
        risk_level = "HIGH"
        event_type = "USER_BLOCKED_DURING_VOTING_WINDOW"
    log_admin_event(
        admin_id=admin_id,
        event_type=event_type,
        election_id=FAIRNESS_DEFAULT_ELECTION_ID,
        event_details={"user_key": wallet, "minutes": minutes},
        risk_level=risk_level,
    )

    conn = get_connection()
    cur = conn.cursor()
    try:
        blocked_until = datetime.utcnow() + timedelta(minutes=minutes)
        cur.execute("UPDATE users SET blocked_until = %s WHERE email = %s", (blocked_until, email))
        if cur.rowcount == 0:
            return jsonify({"error": "Email not found"}), 404
        conn.commit()
        anchor_audit_event("email_blocked", "HIGH", {"email": email, "minutes": minutes})
        return jsonify({"message": "Email blocked", "blocked_until": blocked_until.isoformat()})
    finally:
        cur.close()
        release_connection(conn)


@app.route("/admin/reconcile", methods=["POST"])
def admin_reconcile():
    try:
        result = reconcile_audit_anchors()
        return jsonify(result)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/admin/fairness/recalculate", methods=["POST"])
def admin_recalculate_fairness():
    try:
        result = recalculate_fairness("manual_admin")
        return jsonify(result)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/health")
def health():
    return jsonify(
        {
            "status": "ok",
            "blockchain_client": "ready" if ALGO_CLIENT else "unavailable",
            "blockchain_error": ALGO_INIT_ERROR,
        }
    )


@app.route("/verify-decision", methods=["POST"])
def verify_decision():
    data = request.json or {}
    tx_id = data.get("tx_id")
    decision_hash = data.get("decision_hash")
    voter_ref = data.get("voter_ref") or data.get("wallet")
    if not tx_id or not decision_hash:
        return jsonify({"error": "tx_id and decision_hash are required"}), 400

    onchain_note = fetch_tx_note(tx_id)
    if not onchain_note:
        return jsonify({"verified": False, "reason": "No note found on transaction"}), 404

    note_voter_ref, note_hash = parse_anchor_note(onchain_note)
    if note_voter_ref and note_hash:
        verified = note_hash == decision_hash and (not voter_ref or voter_ref == note_voter_ref)
    else:
        verified = onchain_note == decision_hash

    return jsonify(
        {
            "verified": verified,
            "onchain_note": onchain_note,
            "decision_hash": decision_hash,
            "note_prefix": ANCHOR_NOTE_PREFIX,
            "voter_ref_match": (note_voter_ref == voter_ref) if voter_ref and note_voter_ref else None,
        }
    )


if __name__ == "__main__":
    ensure_schema()
    _start_governance_monitor_if_needed()
    app.run(debug=True)
