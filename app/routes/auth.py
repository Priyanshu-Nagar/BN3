"""
Banking Management System - Authentication Routes
Handles user registration, login, and logout
"""
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, current_user
from app import db
from app.models import User, Admin, Account, generate_account_number
from app.forms import RegisterForm, LoginForm, AdminLoginForm

# Create Blueprint
bp = Blueprint('auth', __name__, url_prefix='/auth')


@bp.route('/register', methods=['GET', 'POST'])
def register():
    """
    User registration route
    GET: Display registration form
    POST: Process registration and create new user
    """
    # Redirect if already logged in
    if current_user.is_authenticated:
        if isinstance(current_user, Admin):
            return redirect(url_for('admin.dashboard'))
        return redirect(url_for('user.dashboard'))
    
    form = RegisterForm()
    
    if form.validate_on_submit():
        # Create new user
        user = User(
            email=form.email.data.lower().strip(),
            full_name=form.email.data.split('@')[0],  # Use email username as name
            phone=None
        )
        user.set_password(form.password.data)
        
        try:
            # Add user to database
            db.session.add(user)
            db.session.flush()  # Get user.id without committing
            
            # Create default checking account with ₹100 initial balance
            account = Account(
                user_id=user.id,
                account_number=generate_account_number(),
                account_type='current',
                balance=10000  # ₹100.00 in cents
            )
            db.session.add(account)
            db.session.commit()
            
            flash(f'Registration successful! Your account number is {account.account_number}. You can now login.', 'success')
            return redirect(url_for('auth.login'))
            
        except Exception as e:
            db.session.rollback()
            flash('An error occurred during registration. Please try again.', 'danger')
            print(f"Registration error: {e}")
    
    return render_template('auth/register.html', form=form, title='Register')


@bp.route('/login', methods=['GET', 'POST'])
def login():
    """
    User login route
    GET: Display login form
    POST: Authenticate user and create session
    """
    # Redirect if already logged in
    if current_user.is_authenticated:
        if isinstance(current_user, Admin):
            return redirect(url_for('admin.dashboard'))
        return redirect(url_for('user.dashboard'))
    
    form = LoginForm()
    
    if form.validate_on_submit():
        # Find user by email
        user = User.query.filter_by(email=form.email.data.lower().strip()).first()
        
        # Validate credentials
        if user is None or not user.verify_password(form.password.data):
            flash('Invalid email or password. Please try again.', 'danger')
            return redirect(url_for('auth.login'))
        
        # Check if account is active
        if not user.is_active:
            flash('Your account has been deactivated. Please contact support.', 'warning')
            return redirect(url_for('auth.login'))
        
        # Log in user
        login_user(user, remember=form.remember.data)
        flash(f'Welcome back, {user.full_name}!', 'success')
        
        # Redirect to next page or dashboard
        next_page = request.args.get('next')
        if next_page:
            return redirect(next_page)
        return redirect(url_for('user.dashboard'))
    
    return render_template('auth/login.html', form=form, title='Login')


@bp.route('/admin-login', methods=['GET', 'POST'])
def admin_login():
    """
    Admin login route
    GET: Display admin login form
    POST: Authenticate admin and create session
    """
    # Redirect if already logged in
    if current_user.is_authenticated:
        if isinstance(current_user, Admin):
            return redirect(url_for('admin.dashboard'))
        return redirect(url_for('user.dashboard'))
    
    form = AdminLoginForm()
    
    if form.validate_on_submit():
        # Find admin by username
        admin = Admin.query.filter_by(username=form.username.data.strip()).first()
        
        # Validate credentials
        if admin is None or not admin.verify_password(form.password.data):
            flash('Invalid username or password. Please try again.', 'danger')
            return redirect(url_for('auth.admin_login'))
        
        # Log in admin
        login_user(admin, remember=form.remember.data)
        flash(f'Welcome, Admin {admin.username}!', 'success')
        
        # Redirect to admin dashboard
        return redirect(url_for('admin.dashboard'))
    
    return render_template('auth/admin_login.html', form=form, title='Admin Login')


@bp.route('/logout')
def logout():
    """
    Logout route
    Logs out current user and redirects to login page
    """
    # Check if user was admin or regular user
    was_admin = isinstance(current_user, Admin) if current_user.is_authenticated else False
    
    logout_user()
    flash('You have been logged out successfully.', 'info')
    
    # Redirect to appropriate login page
    if was_admin:
        return redirect(url_for('auth.admin_login'))
    return redirect(url_for('auth.login'))


@bp.route('/choose')
def choose():
    """
    Landing page to choose between user and admin login
    """
    if current_user.is_authenticated:
        if isinstance(current_user, Admin):
            return redirect(url_for('admin.dashboard'))
        return redirect(url_for('user.dashboard'))
    
    return render_template('auth/choose.html', title='Welcome')