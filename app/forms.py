"""
Banking Management System - WTForms
Defines all forms used in the application
"""
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField, SelectField, DecimalField, TextAreaField, IntegerField
from wtforms.validators import DataRequired, Email, EqualTo, ValidationError, Length, Optional, NumberRange
from app.models import User, Account


class RegisterForm(FlaskForm):
    """
    User registration form
    """
    email = StringField('Email', validators=[
        DataRequired(message='Email is required'),
        Email(message='Invalid email address'),
        Length(max=120, message='Email must be less than 120 characters')
    ])
    
    password = PasswordField('Password', validators=[
        DataRequired(message='Password is required'),
        Length(min=6, max=128, message='Password must be between 6 and 128 characters')
    ])
    
    confirm = PasswordField('Confirm Password', validators=[
        DataRequired(message='Please confirm your password'),
        EqualTo('password', message='Passwords must match')
    ])
    
    submit = SubmitField('Register')
    
    def validate_email(self, email):
        """
        Custom validator to check if email already exists
        """
        user = User.query.filter_by(email=email.data.lower().strip()).first()
        if user:
            raise ValidationError('Email already registered. Please use a different email or login.')


class LoginForm(FlaskForm):
    """
    User and Admin login form
    """
    email = StringField('Email', validators=[
        DataRequired(message='Email is required'),
        Email(message='Invalid email address')
    ])
    
    password = PasswordField('Password', validators=[
        DataRequired(message='Password is required')
    ])
    
    remember = BooleanField('Remember Me')
    
    submit = SubmitField('Login')


class TransferForm(FlaskForm):
    """
    Money transfer form
    """
    from_account = SelectField('From Account', coerce=int, validators=[
        DataRequired(message='Please select source account')
    ])
    
    to_account_id = StringField('To Account Number', validators=[
        DataRequired(message='Recipient account number is required'),
        Length(min=10, max=10, message='Account number must be exactly 10 digits')
    ])
    
    amount = DecimalField('Amount (₹)', validators=[
        DataRequired(message='Amount is required'),
        NumberRange(min=0.01, max=1000000, message='Amount must be between ₹0.01 and ₹1,000,000')
    ], places=2)
    
    description = TextAreaField('Description (Optional)', validators=[
        Optional(),
        Length(max=255, message='Description must be less than 255 characters')
    ])
    
    submit = SubmitField('Transfer Money')
    
    def validate_to_account_id(self, to_account_id):
        """
        Validate that destination account exists and is not frozen
        """
        if not to_account_id.data.isdigit():
            raise ValidationError('Account number must contain only digits.')
        
        account = Account.query.filter_by(account_number=to_account_id.data).first()
        if not account:
            raise ValidationError('Account number does not exist.')
        
        if account.is_frozen:
            raise ValidationError('Destination account is frozen and cannot receive transfers.')


class AdminLoginForm(FlaskForm):
    """
    Admin-specific login form (uses username instead of email)
    """
    username = StringField('Username', validators=[
        DataRequired(message='Username is required'),
        Length(min=3, max=80, message='Username must be between 3 and 80 characters')
    ])
    
    password = PasswordField('Password', validators=[
        DataRequired(message='Password is required')
    ])
    
    remember = BooleanField('Remember Me')
    
    submit = SubmitField('Login as Admin')


class CreateAccountForm(FlaskForm):
    """
    Create new bank account form
    """
    account_type = SelectField('Account Type', choices=[
        ('current', 'Current Account'),
        ('savings', 'Savings Account')
    ], validators=[DataRequired(message='Please select account type')])
    
    initial_deposit = DecimalField('Initial Deposit (₹)', validators=[
        DataRequired(message='Initial deposit is required'),
        NumberRange(min=10.00, max=100000.00, message='Initial deposit must be between ₹10.00 and ₹100,000')
    ], places=2, default=10.00)
    
    submit = SubmitField('Create Account')


class ChangePasswordForm(FlaskForm):
    """
    Change password form for logged-in users
    """
    current_password = PasswordField('Current Password', validators=[
        DataRequired(message='Current password is required')
    ])
    
    new_password = PasswordField('New Password', validators=[
        DataRequired(message='New password is required'),
        Length(min=6, max=128, message='Password must be between 6 and 128 characters')
    ])
    
    confirm_new_password = PasswordField('Confirm New Password', validators=[
        DataRequired(message='Please confirm your new password'),
        EqualTo('new_password', message='Passwords must match')
    ])
    
    submit = SubmitField('Change Password')


class DepositForm(FlaskForm):
    """
    Deposit money form (for admin or self-deposit simulation)
    """
    account = SelectField('Account', coerce=int, validators=[
        DataRequired(message='Please select account')
    ])
    
    amount = DecimalField('Deposit Amount (₹)', validators=[
        DataRequired(message='Amount is required'),
        NumberRange(min=0.01, max=100000.00, message='Amount must be between ₹0.01 and ₹100,000')
    ], places=2)
    
    description = TextAreaField('Description (Optional)', validators=[
        Optional(),
        Length(max=255, message='Description must be less than 255 characters')
    ])
    
    submit = SubmitField('Deposit')


class WithdrawForm(FlaskForm):
    """
    Withdraw money form
    """
    account = SelectField('Account', coerce=int, validators=[
        DataRequired(message='Please select account')
    ])
    
    amount = DecimalField('Withdrawal Amount (₹)', validators=[
        DataRequired(message='Amount is required'),
        NumberRange(min=0.01, max=100000.00, message='Amount must be between ₹0.01 and ₹100,000')
    ], places=2)
    
    description = TextAreaField('Description (Optional)', validators=[
        Optional(),
        Length(max=255, message='Description must be less than 255 characters')
    ])
    
    submit = SubmitField('Withdraw')