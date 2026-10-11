from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3
from datetime import datetime

app = Flask(__name__)

app.secret_key = "health_ai_secret_key"

DATABASE = "health_ai.db"




def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn




@app.route("/")
def home():
    return render_template("index.html")




@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        name = request.form["name"]
        email = request.form["email"]
        password = request.form["password"]

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




@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        email = request.form["email"]
        password = request.form["password"]

        conn = get_db()

        user = conn.execute(
            """
            SELECT * FROM users
            WHERE email = ? AND password = ?
            """,
            (email, password)
        ).fetchone()

        conn.close()

        if user:

            session["user_id"] = user["id"]
            session["user_name"] = user["name"]

            return redirect(url_for("dashboard"))

        else:

            flash("Invalid email or password.")

    return render_template("login.html")




@app.route("/logout")
def logout():

    session.clear()

    return redirect(url_for("home"))


@app.route("/dashboard")
def dashboard():

    if "user_id" not in session:

        return redirect(url_for("login"))

    conn = get_db()

    records = conn.execute(
        """
        SELECT * FROM assessments
        WHERE user_id = ?
        ORDER BY id DESC
        """,
        (session["user_id"],)
    ).fetchall()

    conn.close()

    return render_template(
        "dashboard.html",
        records=records
    )




@app.route("/diagnosis", methods=["GET", "POST"])
def diagnosis():

    if "user_id" not in session:

        return redirect(url_for("login"))

    if request.method == "POST":

        symptoms = request.form.getlist("symptoms")

        result, risk = analyze_symptoms(symptoms)

        conn = get_db()

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
        conn.close()

        return render_template(
            "result.html",
            result=result,
            risk=risk,
            symptoms=symptoms
        )

    return render_template("diagnosis.html")




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

        return "Insufficient Information", "Low"

    result = max(scores, key=scores.get)

    score = scores[result]

    if score >= 5:

        risk = "High"

    elif score >= 3:

        risk = "Moderate"

    else:

        risk = "Low"

    return result, risk




if __name__ == "__main__":

    app.run(
        debug=True,
        port=8000
    )