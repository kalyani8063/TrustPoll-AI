from flask import Flask, request, jsonify
from db import get_connection
from ai import check_anomaly

app = Flask(__name__)

def is_valid_vit_email(email):
    return email.endswith("@vit.edu")


@app.route("/register", methods=["POST"])
def register():
    data = request.json
    email = data["email"]
    wallet = data["wallet"]

    if not is_valid_vit_email(email):
        return jsonify({"error": "Only @vit.edu emails allowed"}), 400

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO users (email, wallet)
        VALUES (%s, %s)
        ON CONFLICT (email) DO NOTHING
    """, (email, wallet))

    conn.commit()
    cur.close()
    conn.close()

    return jsonify({"message": "Registration successful"})


@app.route("/vote-attempt", methods=["POST"])
def vote_attempt():
    data = request.json
    wallet = data["wallet"]
    election_id = data.get("election_id")

    suspicious, reason = check_anomaly(wallet)

    conn = get_connection()
    cur = conn.cursor()

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
    cur.close()
    conn.close()

    return jsonify({
        "allowed": not suspicious,
        "reason": reason
    })


@app.route("/health")
def health():
    return "Backend running"


if __name__ == "__main__":
    app.run(debug=True)
