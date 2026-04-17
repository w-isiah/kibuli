from apps import create_app
from apps.config import Config

# Create the Flask application
application = create_app(Config)
