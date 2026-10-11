from flask import (
    Flask, render_template, request, redirect,
    url_for, session, flash
)
import sqlite3
from datetime import datetime
import os
from dotenv import load_dotenv
from tinyfish import TinyFish

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev-only-change-this-key")

DATABASE = "health_ai.db"

# ---------------- TINYFISH CONFIGURATION ----------------

TINYFISH_API_KEY = os.getenv("TINYFISH_API_KEY")
tinyfish_client = None

if TINYFISH_API_KEY:
    tinyfish_client = TinyFish(api_key=TINYFISH_API_KEY)

print("TinyFish API key loaded:", bool(TINYFISH_API_KEY))
print("TinyFish client initialized:", tinyfish_client is not None)


# ---------------- DATABASE CONNECTION ----------------

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


# ---------------- DATABASE INITIALIZATION ----------------

def init_db():
    conn = get_db()

    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS assessments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            symptoms TEXT,
            result TEXT,
            risk TEXT,
            created_at TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    conn.commit()
    conn.close()


# ---------------- TINYFISH HEALTH INFORMATION ----------------

def get_health_information(symptoms):
    if not tinyfish_client:
        return (
            "External health information is unavailable because "
            "the TinyFish API key is not configured."
        )

    if not symptoms:
        return "Select symptoms to request relevant health information."

    try:
        response = tinyfish_client.agent.run(
            url="https://www.cdc.gov/flu/signs-symptoms/index.html",
            goal=(
                "Read the information on this CDC webpage and provide "
                "a short, plain-language summary of general health "
                "information relevant to these user-reported symptoms: "
                + ", ".join(symptoms)
                + ". Include only information supported by the page. "
                "Do not diagnose the user, estimate their medical risk, "
                "or recommend medication. If the page does not cover "
                "the symptoms, clearly say that the source does not "
                "provide enough relevant information. Mention that "
                "the information is general and not a substitute "
                "for professional medical assessment."
            )
        )

        if response.result:
            return str(response.result)

        app.logger.warning(
            "TinyFish returned no result. Status: %s",
            response.status
        )

        return "No health information was returned by the external source."

    except Exception:
        app.logger.exception("TinyFish request failed")

        return (
            "External health information is temporarily unavailable. "
            "Please consult a qualified healthcare professional "
            "for medical advice."
        )


# ---------------- TEST TINYFISH ----------------

@app.route("/test-tinyfish")
def test_tinyfish():
    if not tinyfish_client:
        return "API key missing. Check your .env file.", 500

    try:
        response = tinyfish_client.agent.run(
            url="https://example.com",
            goal="Extract the page title and return it."
        )

        return {
            "status": str(response.status),
            "result": str(response.result)
        }

    except Exception:
        app.logger.exception("TinyFish test failed")
        return "TinyFish API request failed. Check the terminal.", 502


# ---------------- HOME ----------------

@app.route("/")
def home():
    return render_template("index.html")


# ---------------- REGISTER ----------------

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if not name or not email or not password:
            flash("Please fill in all fields.")
            return render_template("register.html")

        conn = get_db()

        try:
            conn.execute(
                """
                INSERT INTO users (name, email, password)
                VALUES (?, ?, ?)
                """,
                (name, email, password)
            )
            conn.commit()
            flash("Registration successful!")
            return redirect(url_for("login"))

        except sqlite3.IntegrityError:
            flash("Email already registered.")

        finally:
            conn.close()

    return render_template("register.html")


# ---------------- LOGIN ----------------

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        conn = get_db()

        try:
            user = conn.execute(
                """
                SELECT * FROM users
                WHERE email = ? AND password = ?
                """,
                (email, password)
            ).fetchone()
        finally:
            conn.close()

        if user:
            session["user_id"] = user["id"]
            session["user_name"] = user["name"]
            return redirect(url_for("dashboard"))

        flash("Invalid email or password.")

    return render_template("login.html")


# ---------------- LOGOUT ----------------

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))


# ---------------- DASHBOARD ----------------

@app.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = get_db()

    try:
        records = conn.execute(
            """
            SELECT * FROM assessments
            WHERE user_id = ?
            ORDER BY id DESC
            """,
            (session["user_id"],)
        ).fetchall()
    finally:
        conn.close()

    return render_template("dashboard.html", records=records)


# ---------------- HEALTH ASSESSMENT ----------------

@app.route("/diagnosis", methods=["GET", "POST"])
def diagnosis():
    if "user_id" not in session:
        return redirect(url_for("login"))

    if request.method == "POST":
        symptoms = request.form.getlist("symptoms")

        if not symptoms:
            flash("Please select at least one symptom.")
            return render_template("diagnosis.html")

        # Existing rule-based scoring
        result, risk = analyze_symptoms(symptoms)

        # TinyFish retrieves general information from the CDC page
        health_information = (
        "Health research is loading. Please check again shortly.")

        conn = get_db()

        try:
            conn.execute(
                """
                INSERT INTO assessments
                (user_id, symptoms, result, risk, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    session["user_id"],
                    ", ".join(symptoms),
                    result,
                    risk,
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                )
            )
            conn.commit()
        finally:
            conn.close()

        return render_template(
            "result.html",
            result=result,
            risk=risk,
            symptoms=symptoms,
            health_information=health_information
        )

    return render_template("diagnosis.html")


# ---------------- RULE-BASED SCORING ENGINE ----------------

def analyze_symptoms(symptoms):
    scores = {
        "Flu / Viral Infection": 0,
        "Respiratory Infection": 0,
        "Migraine": 0,
        "Gastric Problem": 0,
        "Dehydration": 0
    }

    for symptom in symptoms:
        if symptom == "fever":
            scores["Flu / Viral Infection"] += 3
        elif symptom == "cough":
            scores["Respiratory Infection"] += 3
        elif symptom == "sore_throat":
            scores["Respiratory Infection"] += 2
        elif symptom == "headache":
            scores["Migraine"] += 3
        elif symptom == "fatigue":
            scores["Flu / Viral Infection"] += 2
        elif symptom == "body_pain":
            scores["Flu / Viral Infection"] += 2
        elif symptom == "nausea":
            scores["Gastric Problem"] += 2
        elif symptom == "vomiting":
            scores["Gastric Problem"] += 3
        elif symptom == "stomach_pain":
            scores["Gastric Problem"] += 3
        elif symptom == "dizziness":
            scores["Dehydration"] += 2

    if max(scores.values()) == 0:
        return "Insufficient Information", "Undetermined"

    result = max(scores, key=scores.get)
    score = scores[result]

    # Prototype thresholds, not clinically validated
    if score >= 5:
        risk = "High"
    elif score >= 3:
        risk = "Moderate"
    else:
        risk = "Low"

    return result, risk


# ---------------- RUN APPLICATION ----------------

init_db()

if __name__ == "__main__":
    app.run(debug=True, port=8000)