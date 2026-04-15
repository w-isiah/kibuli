import os
from datetime import timedelta
from flask import Flask, session, g
from flask_wtf.csrf import CSRFProtect
from importlib import import_module
from datetime import datetime # Added for date formatting

from apps.config import Config
from apps.db import get_db_connection

# Initialize Flask extensions
csrf = CSRFProtect()

def register_extensions(app):
    """Initialize Flask extensions."""
    csrf.init_app(app)



import locale

# Set the locale for currency formatting (e.g., US currency)
# This setting is required for Python's locale.currency function
# Replace 'en_US.UTF-8' with your desired locale (e.g., 'en_GB.UTF-8' for GBP)
try:
    locale.setlocale(locale.LC_ALL, 'en_US.UTF-8')
except locale.Error:
    # Fallback for systems where 'en_US.UTF-8' is not available (e.g., Windows)
    try:
        locale.setlocale(locale.LC_ALL, 'C') 
    except locale.Error:
        pass


def format_currency(value, symbol='UGX', grouping=True):
    """Formats a number as a currency string."""
    try:
        # If locale is set correctly, use locale.currency (best option)
        return locale.currency(value, symbol=symbol, grouping=grouping)
    except:
        # Simple fallback format if locale fails (e.g., $1,234.56)
        if isinstance(value, (int, float)):
            return f"{symbol}{value:,.2f}"
        return value

def format_date(date_data, format_string='%Y-%m-%d'):
    """
    Custom Jinja filter function to format datetime/date objects. 
    Defaults to 'YYYY-MM-DD' which is required for HTML date inputs.
    """
    if date_data is None:
        return ''
        
    # If the data is already a string, return it.
    if isinstance(date_data, str):
        return date_data
        
    try:
        # If it's a date or datetime object, format it.
        return date_data.strftime(format_string)
    except Exception:
        # Fallback if the object is an unexpected type
        return str(date_data)


    
def register_blueprints(app):
    """Register all blueprints dynamically from the apps module."""
    modules = [
        'authentication', 'home', 'pupils', 'classes', 'fathers', 'mothers',
        'guardians', 'subjects', 'teachers', 'gen_ids', 'study_years',
        'results', 'reports', 'grades', 'dorms', 'register', 'promote',
        'streams', 'rooms', 'stream_assign', 'categories', 'products',
        'p_restock', 'dorm_reg', 'sub_categories', 'sales', 'customers',
        'other_products', 'department_h_products', 'dep_restock', 'division',
        'subject_assign', 'results_update', 'add_marks','assessment','term',
        'classteacher_assign','grade_analysis','eot_reports','past_reports',
        'subject_comments','headmaster_comments','classteacher_comments',
        'admissions','locations','suppliers','fixed_assets','asset_inventory','password_reset','finance','report_1'
    ]

    for module_name in modules:
        module = import_module(f'apps.{module_name}.routes')
        app.register_blueprint(module.blueprint)

def create_app(config_class=Config):
    """Create and configure the Flask application."""
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Set session lifetime
    app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=7)

    # Register app components
    register_extensions(app)

    # FIX: Register the custom Jinja filter for currency formatting
    app.jinja_env.filters['format_currency'] = format_currency
    # ADD: Register the custom Jinja filter for date formatting
    app.jinja_env.filters['date_format'] = format_date
    
    register_blueprints(app)

    @app.before_request
    def before_request():
        """Store user ID from session in the application context."""
        g.user_id = session.get('id')

    return app
