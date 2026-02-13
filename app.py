from flask import Flask, render_template, request, redirect, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, login_required, logout_user, UserMixin, current_user
from flask_bcrypt import Bcrypt
import os, random
from openai import OpenAI

# import google.generativeai as genai
import smtplib
from email.mime.text import MIMEText
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(
    api_key=os.getenv("OPENROUTER_API_KEY"),
    base_url="https://openrouter.ai/api/v1"
)

# genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
# model = genai.GenerativeModel("gemini-1.5-flash")



def send_otp_email(to_email, otp):
    sender = os.getenv("EMAIL_USER")
    password = os.getenv("EMAIL_PASS")

    msg = MIMEText(f"Your OTP is: {otp}")
    msg["Subject"] = "Your OTP Code"
    msg["From"] = sender
    msg["To"] = to_email

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender, password)
            server.send_message(msg)
        print("OTP sent to email successfully")
    except Exception as e:
        print("Email error:", e)





app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "secret123")

# MySQL configuration
db_user = os.getenv("DB_USER")
db_pass = os.getenv("DB_PASS")
db_host = os.getenv("DB_HOST")
db_name = os.getenv("DB_NAME")

app.config["SQLALCHEMY_DATABASE_URI"] = f"mysql+pymysql://{db_user}:{db_pass}@{db_host}/{db_name}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False





db = SQLAlchemy(app)
bcrypt = Bcrypt(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

# genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
# model = genai.GenerativeModel("gemini-1.5-flash")


# ================= USER MODEL =================
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    phone = db.Column(db.String(15), nullable=False)
    password = db.Column(db.String(200), nullable=False)
    otp = db.Column(db.String(6))
    is_verified = db.Column(db.Boolean, default=False)


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# ================= LOAD EMAIL KNOWLEDGE =================
if os.path.exists("emails.txt"):
    with open("emails.txt", "r") as f:
        email_knowledge = f.read()
else:
    email_knowledge = ""

# ================= ROUTES =================
@app.route("/")
def home():
    return redirect("/login")

# ---------- REGISTER ----------
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form["name"]
        email = request.form["email"]
        phone = request.form["phone"]
        password = bcrypt.generate_password_hash(
            request.form["password"]
        ).decode("utf-8")

        otp = str(random.randint(100000, 999999))

        user = User(
            name=name,
            email=email,
            phone=phone,
            password=password,
            otp=otp
        )

        db.session.add(user)
        db.session.commit()

        send_otp_email(email, otp)

        session["email"] = email
        return redirect("/verify")

    return render_template("register.html")


# ---------- OTP VERIFY ----------
@app.route("/verify", methods=["GET", "POST"])
def verify():
    if request.method == "POST":
        otp = request.form["otp"]
        user = User.query.filter_by(email=session.get("email")).first()

        if user and user.otp == otp:
            user.is_verified = True
            db.session.commit()
            return redirect("/login")

    return render_template("otp.html")

# ---------- LOGIN ----------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        user = User.query.filter_by(email=email).first()

        if user and bcrypt.check_password_hash(user.password, password):
            if user.is_verified:
                login_user(user)
                return redirect("/dashboard")

    return render_template("login.html")

# ---------- DASHBOARD ----------
@app.route("/dashboard")
@login_required
def dashboard():
    return render_template(
        "dashboard.html",
        user_name=current_user.name
    )


# ---------- AI EMAIL GENERATION ----------
@app.route("/generate", methods=["POST"])
@login_required
def generate():
    try:
        data = request.json
        prompt = data.get("prompt", "").strip()
        tone = data.get("tone", "formal")

        if not prompt:
            return jsonify({"email": "Please enter a prompt."})

        final_prompt = f"""
Write a {tone} professional email.

Rules:
- Return only the email text.
- Do not use placeholders like [Your Name], Recipient, Date, etc.
- Use the sender name: {current_user.name}
- Keep it natural and realistic.
- Start with "Subject:" on the first line.

Request:
{prompt}
"""


        response = client.chat.completions.create(
            model="mistralai/mistral-7b-instruct",
            messages=[
                {"role": "user", "content": final_prompt}
            ]
        )

        email_text = response.choices[0].message.content

        # Clean formatting
        email_text = email_text.replace("Recipient's Name", "Sir/Madam")
        email_text = email_text.replace("Your Name", current_user.name)
        email_text = email_text.replace("[Your Name]", current_user.name)
        email_text = email_text.replace("Date", "")

        return jsonify({"email": email_text})

    except Exception as e:
        print("AI Error:", e)
        return jsonify({"email": "Server error while generating email."})


# ---------- LOGOUT ----------

@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect("/login")


# ================= RUN =================
if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)

import smtplib
from email.mime.text import MIMEText

def send_otp_email(to_email, otp):
    sender = os.getenv("EMAIL_USER")
    password = os.getenv("EMAIL_PASS")

    msg = MIMEText(f"Your OTP is: {otp}")
    msg["Subject"] = "Your OTP Code"
    msg["From"] = sender
    msg["To"] = to_email

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(sender, password)
        server.send_message(msg)

print("API KEY:", os.getenv("GOOGLE_API_KEY"))

