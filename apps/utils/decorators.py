from functools import wraps
from flask import session, redirect, url_for, flash, request

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'id' not in session:
            flash('Please log in first.', 'warning')
            return redirect(url_for('authentication.login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function
