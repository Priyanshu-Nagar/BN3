"""
Banking Management System - Database Models
Defines all database tables and relationships using SQLAlchemy
"""
from app import db
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
# from datetime import datetime
from datetime import datetime, timedelta


def get_ist_now():
    return datetime.utcnow() + timedelta(hours=5, minutes=30)


class User(UserMixin, db.Model):
    """
    User model - represents regular banking customers
    """
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    full_name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20), nullable=True)
    is_admin = db.Column(db.Boolean, default=False, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=get_ist_now, nullable=False)
    
    # Relationships
    accounts = db.relationship('Account', backref='owner', lazy='dynamic', cascade='all, delete-orphan')
    
    def set_password(self, password):
        """
        Hash and set the user's password
        
        Args:
            password (str): Plain text password
        """
        self.password_hash = generate_password_hash(password, method='pbkdf2:sha256')
    
    def verify_password(self, password):
        """
        Verify if the provided password matches the stored hash
        
        Args:
            password (str): Plain text password to verify
            
        Returns:
            bool: True if password matches, False otherwise
        """
        return check_password_hash(self.password_hash, password)
    
    def get_id(self):
        """
        Override get_id for Flask-Login to differentiate from Admin
        
        Returns:
            str: User ID as string
        """
        return str(self.id)
    
    def get_total_balance(self):
        """
        Calculate total balance across all user accounts
        
        Returns:
            float: Total balance in dollars
        """
        total_cents = sum(account.balance for account in self.accounts)
        return total_cents / 100.0
    
    def __repr__(self):
        return f'<User {self.email}>'


class Admin(UserMixin, db.Model):
    """
    Admin model - represents system administrators
    Separate from User to maintain clear role separation
    """
    __tablename__ = 'admins'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=get_ist_now, nullable=False)
    
    def get_id(self):
        """
        Override get_id for Flask-Login to differentiate from User
        Uses 'admin_' prefix to distinguish admin sessions
        
        Returns:
            str: Admin ID with prefix
        """
        return f'admin_{self.id}'
    
    def verify_password(self, password):
        """
        Verify admin password
        
        Args:
            password (str): Plain text password to verify
            
        Returns:
            bool: True if password matches, False otherwise
        """
        return check_password_hash(self.password, password)
    
    def set_password(self, password):
        """
        Hash and set the admin's password
        
        Args:
            password (str): Plain text password
        """
        self.password = generate_password_hash(password, method='pbkdf2:sha256')
    
    def __repr__(self):
        return f'<Admin {self.username}>'


class Account(db.Model):
    """
    Account model - represents bank accounts owned by users
    """
    __tablename__ = 'accounts'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    account_number = db.Column(db.String(20), unique=True, nullable=False, index=True)
    account_type = db.Column(db.String(20), nullable=False)  # 'checking' or 'savings'
    balance = db.Column(db.Integer, default=0, nullable=False)  # Stored in cents
    is_frozen = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=get_ist_now, nullable=False)
    
    # Relationships
    transactions_sent = db.relationship(
        'Transaction',
        foreign_keys='Transaction.from_account_id',
        backref='source_account',
        lazy='dynamic'
    )
    transactions_received = db.relationship(
        'Transaction',
        foreign_keys='Transaction.to_account_id',
        backref='destination_account',
        lazy='dynamic'
    )
    
    def get_balance(self):
        """
        Get account balance in dollars
        
        Returns:
            float: Balance in dollars
        """
        return self.balance / 100.0
    
    def deposit(self, amount_cents):
        """
        Deposit money into account
        
        Args:
            amount_cents (int): Amount to deposit in cents
        """
        self.balance += amount_cents
    
    def withdraw(self, amount_cents):
        """
        Withdraw money from account
        
        Args:
            amount_cents (int): Amount to withdraw in cents
            
        Returns:
            bool: True if successful, False if insufficient funds
        """
        if self.balance >= amount_cents:
            self.balance -= amount_cents
            return True
        return False
    
    def get_all_transactions(self):
        """
        Get all transactions (sent and received) for this account
        
        Returns:
            list: Combined list of transactions, sorted by timestamp
        """
        sent = self.transactions_sent.all()
        received = self.transactions_received.all()
        all_transactions = sent + received
        return sorted(all_transactions, key=lambda x: x.timestamp, reverse=True)
    
    def __repr__(self):
        return f'<Account {self.account_number}>'


class Transaction(db.Model):
    """
    Transaction model - represents money transfers between accounts
    """
    __tablename__ = 'transactions'
    
    id = db.Column(db.Integer, primary_key=True)
    from_account_id = db.Column(db.Integer, db.ForeignKey('accounts.id'), nullable=True, index=True)
    to_account_id = db.Column(db.Integer, db.ForeignKey('accounts.id'), nullable=True, index=True)
    amount = db.Column(db.Integer, nullable=False)  # Stored in cents
    transaction_type = db.Column(db.String(20), nullable=False)  # 'transfer', 'deposit', 'withdrawal'
    description = db.Column(db.String(255), nullable=True)
    timestamp = db.Column(db.DateTime, default=get_ist_now, nullable=False, index=True)
    
    def get_amount(self):
        """
        Get transaction amount in dollars
        
        Returns:
            float: Amount in dollars
        """
        return self.amount / 100.0
    
    def __repr__(self):
        return f'<Transaction {self.id} - {self.transaction_type} ₹{self.get_amount():.2f}>'


# Helper function to generate unique account numbers
def generate_account_number():
    """
    Generate a unique 10-digit account number
    
    Returns:
        str: Unique account number
    """
    import random
    while True:
        # Generate 10-digit number
        account_num = ''.join([str(random.randint(0, 9)) for _ in range(10)])
        # Check if it already exists
        existing = Account.query.filter_by(account_number=account_num).first()
        if not existing:
            return account_num