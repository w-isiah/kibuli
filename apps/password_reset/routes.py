from flask import Blueprint, render_template, request, redirect, url_for, flash
from datetime import datetime, timedelta
import random
import os
import json
import requests
import smtplib
from email.message import EmailMessage

from apps import get_db_connection
from apps.password_reset import blueprint

# ----------------------
# Helper Functions
# ----------------------

def generate_otp() -> str:
    """Generate a 6-digit OTP as string."""
    return str(random.randint(100000, 999999))

def otp_expiry() -> datetime:
    """Return OTP expiration datetime (5 minutes from now)."""
    return datetime.now() + timedelta(minutes=5)

def send_otp_email(email: str, otp: str):
    """Send OTP via email (simulation / debug)."""
    msg = EmailMessage()
    msg['Subject'] = "Password Reset OTP"
    msg['From'] = "kimulidone@gmail.com"
    msg['To'] = email
    msg.set_content(f"Your OTP is {otp}. It expires in 5 minutes.")

    with smtplib.SMTP('localhost') as smtp:
        smtp.send_message(msg)

def send_sms_infobip(phone: str, otp: str):
    """Send OTP SMS via Infobip API."""
    INFOBIP_BASE_URL = "https://vy6ml1.api.infobip.com"
    INFOBIP_API_KEY = os.getenv("INFOBIP_API_KEY")
    url = f"{INFOBIP_BASE_URL}/sms/2/text/advanced"
    headers = {
        "Authorization": f"App {INFOBIP_API_KEY}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    payload = {
        "messages": [
            {
                "from": "SchoolApp",
                "destinations": [{"to": phone}],
                "text": f"Your OTP code is {otp}. It expires in 5 minutes."
            }
        ]
    }
    response = requests.post(url, headers=headers, data=json.dumps(payload))
    if response.status_code == 200:
        print(f"✅ OTP sent to {phone}")
    else:
        print(f"❌ Failed to send OTP to {phone}: {response.text}")

# ----------------------
# Forgot Password
# ----------------------
@blueprint.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        identifier = request.form.get('identifier', '').strip()

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT id, email, phone_number
            FROM users
            WHERE email=%s OR phone_number=%s
        """, (identifier, identifier))
        user = cursor.fetchone()

        if not user:
            flash("Account not found", "danger")
            return redirect(url_for('password_reset_blueprint.forgot_password'))

        otp = generate_otp()
        expires = otp_expiry()
        channel = 'email' if identifier == user['email'] else 'phone'

        cursor.execute("""
            INSERT INTO password_reset_otp (user_id, otp_code, channel, expires_at, attempts)
            VALUES (%s, %s, %s, %s, %s)
        """, (user['id'], otp, channel, expires, 0))
        conn.commit()

        if channel == 'phone':
            send_sms_infobip(user['phone_number'], otp)
        else:
            send_otp_email(user['email'], otp)

        flash(f"OTP sent via {channel}", "success")
        return redirect(url_for('password_reset_blueprint.verify_otp', id=user['id']))

    return render_template('password_reset/forgot_password.html')

# ----------------------
# Verify OTP
# ----------------------
@blueprint.route('/verify-otp/<int:id>', methods=['GET', 'POST'])
def verify_otp(id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    if request.method == 'POST':
        otp_input = request.form.get('otp')

        cursor.execute("""
            SELECT * FROM password_reset_otp
            WHERE user_id=%s
            ORDER BY created_at DESC
            LIMIT 1
        """, (id,))
        record = cursor.fetchone()

        if not record:
            flash("OTP not found.", "danger")
            return redirect(request.url)

        if record['attempts'] >= 5:
            flash("Too many failed attempts.", "danger")
            return redirect(url_for('password_reset_blueprint.forgot_password'))

        if record['expires_at'] < datetime.now():
            flash("OTP expired.", "danger")
            return redirect(url_for('password_reset_blueprint.forgot_password'))

        if otp_input != record['otp_code']:
            cursor.execute("""
                UPDATE password_reset_otp
                SET attempts = attempts + 1
                WHERE id = %s
            """, (record['id'],))
            conn.commit()
            flash("Invalid OTP.", "danger")
            return redirect(request.url)

        flash("OTP verified.", "success")
        return redirect(url_for('password_reset_blueprint.reset_password', id=id))

    return render_template('password_reset/verify_otp.html')

# ----------------------
# Reset Password
# ----------------------
@blueprint.route('/reset-password/<int:id>', methods=['GET', 'POST'])
def reset_password(id):
    if request.method == 'POST':
        password = request.form.get('password')
        confirm = request.form.get('confirm')

        if password != confirm:
            flash("Passwords do not match", "danger")
            return redirect(request.url)

        conn = get_db_connection()
        cursor = conn.cursor()

        # ❗ Plain-text password (per your request)
        cursor.execute("""
            UPDATE users
            SET password=%s
            WHERE id=%s
        """, (password, id))

        cursor.execute("""
            DELETE FROM password_reset_otp
            WHERE user_id=%s
        """, (id,))

        conn.commit()
        flash("Password reset successful.", "success")
        return redirect(url_for('authentication_blueprint.login'))

    return render_template('password_reset/reset_password.html')
