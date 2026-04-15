import os
import random
import string

class Config:
    """Base configuration class."""
    # Absolute path to the current directory
    basedir = os.path.abspath(os.path.dirname(__file__))

    # Upload folder paths
    UPLOAD_FOLDER = os.path.join(basedir, 'static', 'uploads')
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'xlsx', 'xls'}

    # Use a fixed key from environment variables or a stable fallback string
    # Generating it randomly inside the class causes session loss on every restart.
    SECRET_KEY = os.getenv('SECRET_KEY', 'a_very_secret_stable_string_12345')

    # MySQL Connection Details (Common to both databases)
    MYSQL_HOST = os.getenv('MYSQL_HOST', 'localhost')
    MYSQL_USER = os.getenv('MYSQL_USER', 'root')
    MYSQL_PASSWORD = os.getenv('MYSQL_PASSWORD', '')

    # --- TWO DATABASE CONFIGURATIONS ---
    # Database 1 (Primary)
    MYSQL_DATABASE = os.getenv('MYSQL_DATABASE', 'shpsk')

    # Database 2 (Secondary)
    MYSQL_DATABASE_TWO = os.getenv('MYSQL_DATABASE_TWO', 'shpsk_archive')
    # -----------------------------------

    @staticmethod
    def init_app(app):
        """Initialize the app with the configuration."""
        app.config.from_object(Config)
        # Ensure the upload folder exists
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)