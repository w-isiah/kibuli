import random
from datetime import datetime, timedelta

def generate_otp():
    return str(random.randint(100000, 999999))

def otp_expiry(minutes=5):
    return datetime.now() + timedelta(minutes=minutes)
