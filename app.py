
from flask import Flask, render_template, request, jsonify
import mysql.connector
from mysql.connector import IntegrityError
import logging
import sys
from flask_wtf.csrf import CSRFProtect
from dotenv import load_dotenv
import os

load_dotenv()

# Logging configuration
APP_ENV = os.getenv("APP_ENV", "development").lower()

if APP_ENV not in ("development", "production"):
    raise RuntimeError("APP_ENV must be development or production")

SECRET_KEY_FILE = os.getenv("SECRET_KEY_FILE")

if SECRET_KEY_FILE:
    with open(SECRET_KEY_FILE, "r") as secret_file:
        SECRET_KEY = secret_file.read().strip()
else:
    SECRET_KEY = os.getenv("SECRET_KEY")

if not SECRET_KEY:
    raise RuntimeError("SECRET_KEY is missing")

app = Flask(__name__)
app.config["SECRET_KEY"] = SECRET_KEY

csrf = CSRFProtect(app)

# Database configuration
DB_HOST = os.getenv("DB_HOST")
DB_PORT = int(os.getenv("DB_PORT", "3306"))    # added port for this mysql container in 01 project it is not there.
DB_USER = os.getenv("DB_USER")
#DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_PASSWORD_FILE = os.getenv("DB_PASSWORD_FILE")

if DB_PASSWORD_FILE:
    with open(DB_PASSWORD_FILE, "r") as secret_file:
        DB_PASSWORD = secret_file.read().strip()
else:
    DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_NAME = os.getenv("DB_NAME")

required_vars = {
    "DB_HOST": DB_HOST,
    "DB_USER": DB_USER,
    "DB_PASSWORD": DB_PASSWORD,
    "DB_NAME": DB_NAME,
}

missing_vars = [
    name for name, value in required_vars.items()
    if not value
]

if missing_vars:
    raise RuntimeError(
        "Missing database configuration: " + ", ".join(missing_vars)
    )


# Connect to MariaDB database
def get_db_connection():
    return mysql.connector.connect(
        host=DB_HOST,
        port=DB_PORT,           # added port for this mysql container in 01 project it is not there.
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        connection_timeout=5,
    )

#Liveness Endpoint: This endpoint is used to check if the application is running and responsive.
@app.route("/health/live", methods=["GET"])
def health_live():
    return jsonify({
        "status": "alive"
    }), 200

@app.route("/health/ready", methods=["GET"])
def health_ready():
    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        cursor.execute("SELECT 1")
        cursor.fetchone()

        return jsonify({
            "status": "ready",
            "database": "connected"
        }), 200

    except mysql.connector.Error:
        app.logger.exception("Readiness check failed")    # LOGGING
        return jsonify({
            "status": "not_ready"
        }), 503

    finally:
        if cursor:
            cursor.close()

        if connection and connection.is_connected():
            connection.close()


# Centralized error handling

@app.errorhandler(404)
def not_found(error):
    app.logger.warning("Page not found: %s", request.path)

    return "The requested resource was not found.", 404


@app.errorhandler(500)
def internal_server_error(error):
    app.logger.error("Internal server error: %s", error)

    return "An internal server error occurred. Please try again later.", 500


# Home page: Registration form
@app.route("/")
def home():
    return render_template("index.html")


# Save a new registration
@app.route("/register", methods=["POST"])
def register():

    app.logger.info("Registration request received")  # LOGGING

    full_name = request.form.get("full_name", "").strip()
    email = request.form.get("email", "").strip().lower()
    phone = request.form.get("phone", "").strip()
    city = request.form.get("city", "").strip()

    # Validate required fields
    if not all([full_name, email, phone, city]):
        app.logger.warning("Registration rejected: required fields missing")  # LOGGING
        return "All fields are required.", 400

    # Validate maximum database field lengths
    if (
        len(full_name) > 100
        or len(email) > 150
        or len(phone) > 20
        or len(city) > 100
    ):
        app.logger.warning("Registration rejected: field length exceeded")  # LOGGING
        return "One or more fields exceed the allowed length.", 400

    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        sql = """
            INSERT INTO people (full_name, email, phone, city)
            VALUES (%s, %s, %s, %s)
        """
        values = (full_name, email, phone, city)

        cursor.execute(sql, values)
        connection.commit()

        app.logger.info("Registration completed successfully")  # LOGGING

        return "Registration successful!", 201

    except IntegrityError:
        app.logger.warning("Registration rejected: duplicate email")  # LOGGING
        return "This email is already registered.", 409

    except mysql.connector.Error:
        app.logger.exception("Database operation failed")       # LOGGING
        return "Unable to save registration. Please try again.", 500

    finally:
        if cursor is not None:
            cursor.close()

        if connection is not None and connection.is_connected():
            connection.close()


# View all registered people
@app.route("/people")
def list_people():

    app.logger.info("Fetching registered people")  # LOGGING

    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute("""
            SELECT id, full_name, email, phone, city, created_at
            FROM people
            ORDER BY id DESC
        """)

        people = cursor.fetchall()

        app.logger.info("Registered people fetched successfully")  # LOGGING

        return render_template("people.html", people=people)

    except mysql.connector.Error:
        app.logger.exception("Could not retrieve registered people")  # LOGGING
        return "Unable to load registrations. Please try again.", 500

    finally:
        if cursor is not None:
            cursor.close()

        if connection is not None and connection.is_connected():
            connection.close()

if __name__ == "__main__":
    # Local development only. Do not use debug=True in production. As if you are using debug=True in production, it can expose sensitive information and make your application vulnerable to attacks.
    app.run()     #removed debug=True for production safety. we are going to use WSGI server Gunicorn for production deployment.
