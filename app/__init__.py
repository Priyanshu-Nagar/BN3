"""
Banking Management System - Application Factory
This file initializes the Flask app and its extensions
"""
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Initialize Flask extensions
db = SQLAlchemy()
login_manager = LoginManager()


class Config:
    """
    Configuration class for Flask application
    Loads settings from environment variables or uses defaults
    """
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production-2024'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///bank.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Session configuration
    PERMANENT_SESSION_LIFETIME = 1800  # 30 minutes
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    
    # WTForms configuration
    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = None  # No time limit for CSRF tokens


def create_app(config_class=Config):
    """
    Application factory function
    Creates and configures the Flask application
    
    Args:
        config_class: Configuration class to use (defaults to Config)
    
    Returns:
        Configured Flask application instance
    """
    app = Flask(__name__, instance_relative_config=True)
    
    # Load configuration
    app.config.from_object(config_class)
    
    # Ensure instance folder exists
    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass
    
    # Initialize extensions with app
    db.init_app(app)
    login_manager.init_app(app)
    
    # Configure Flask-Login
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Please log in to access this page.'
    login_manager.login_message_category = 'info'
    
    # User loader for Flask-Login
    @login_manager.user_loader
    def load_user(user_id):
        """
        Load user by ID for Flask-Login
        Checks both User and Admin tables
        """
        from app.models import User, Admin
        
        # Check if it's a user or admin based on ID format
        # Users have regular IDs, we'll use a prefix system
        if user_id.startswith('admin_'):
            admin_id = int(user_id.split('_')[1])
            return Admin.query.get(admin_id)
        else:
            return User.query.get(int(user_id))
    
    # Create database tables and default admin
    with app.app_context():
        # Import models here to avoid circular imports
        from app import models
        
        # Create all tables
        db.create_all()
        
        # Create default admin if not exists
        from app.models import Admin
        from werkzeug.security import generate_password_hash
        
        admin = Admin.query.filter_by(username='admin').first()
        if not admin:
            default_admin = Admin(
                username='admin',
                email='admin@banking.com',
                password=generate_password_hash('admin123', method='pbkdf2:sha256')
            )
            db.session.add(default_admin)
            db.session.commit()
            print("=" * 60)
            print("✓ Default admin account created successfully!")
            print("  Username: admin")
            print("  Password: admin123")
            print("  ⚠️  IMPORTANT: Change this password after first login!")
            print("=" * 60)
    
    # Register blueprints
    from app.routes import auth, user_routes, admin_routes
    # from app.routes import auth,
    
    app.register_blueprint(auth.bp)
    app.register_blueprint(user_routes.bp)
    app.register_blueprint(admin_routes.bp)
    
    # Root route
    @app.route('/')
    def index():
        """Landing page - choose login type"""
        from flask import redirect, url_for
        return redirect(url_for('auth.choose'))
    
    # Error handlers
    @app.errorhandler(404)
    def not_found_error(error):
        """Handle 404 errors"""
        from flask import render_template
        return render_template('errors/404.html'), 404
    
    @app.errorhandler(500)
    def internal_error(error):
        """Handle 500 errors"""
        from flask import render_template
        db.session.rollback()
        return render_template('errors/500.html'), 500
    
    return app