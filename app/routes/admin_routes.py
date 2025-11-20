"""
Banking Management System - Admin Routes
Handles admin dashboard, user management, and transaction monitoring
"""
from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user
from functools import wraps
from app import db
from app.models import User, Admin, Account, Transaction
from datetime import datetime, timedelta
from sqlalchemy import func, desc

# Create Blueprint
bp = Blueprint('admin', __name__, url_prefix='/admin')


def admin_required(f):
    """
    Decorator to restrict routes to admin users only
    
    Usage:
        @bp.route('/admin-only')
        @login_required
        @admin_required
        def admin_only_view():
            return "Admin content"
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Check if user is logged in
        if not current_user.is_authenticated:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('auth.admin_login'))
        
        # Check if user is an admin
        if not isinstance(current_user, Admin):
            flash('Access denied. Admin privileges required.', 'danger')
            abort(403)  # Forbidden
        
        return f(*args, **kwargs)
    return decorated_function


@bp.route('/dashboard')
@login_required
@admin_required
def dashboard():
    """
    Admin dashboard - displays summary metrics and system statistics
    """
    # Total number of users
    total_users = User.query.count()
    
    # Active users (is_active = True)
    active_users = User.query.filter_by(is_active=True).count()
    
    # Inactive/frozen users
    inactive_users = User.query.filter_by(is_active=False).count()
    
    # Total number of accounts
    total_accounts = Account.query.count()
    
    # Frozen accounts
    frozen_accounts = Account.query.filter_by(is_frozen=True).count()
    
    # Total balance across all accounts (in cents, convert to dollars)
    total_balance_cents = db.session.query(func.sum(Account.balance)).scalar() or 0
    total_balance = total_balance_cents / 100.0
    
    # Total number of transactions
    total_transactions = Transaction.query.count()
    
    # Transactions today
    now_ist = datetime.utcnow() + timedelta(hours=5, minutes=30)
    today_start = now_ist.replace(hour=0, minute=0, second=0, microsecond=0)
    transactions_today = Transaction.query.filter(Transaction.timestamp >= today_start).count()
    
    # Total transaction volume today (in cents)
    today_volume_cents = db.session.query(func.sum(Transaction.amount)).filter(
        Transaction.timestamp >= today_start
    ).scalar() or 0
    today_volume = today_volume_cents / 100.0
    
    # Recent transactions (last 10)
    recent_transactions = Transaction.query.order_by(desc(Transaction.timestamp)).limit(10).all()
    
    # Recently registered users (last 5)
    recent_users = User.query.order_by(desc(User.created_at)).limit(5).all()
    
    return render_template(
        'admin/dashboard.html',
        title='Admin Dashboard',
        total_users=total_users,
        active_users=active_users,
        inactive_users=inactive_users,
        total_accounts=total_accounts,
        frozen_accounts=frozen_accounts,
        total_balance=total_balance,
        total_transactions=total_transactions,
        transactions_today=transactions_today,
        today_volume=today_volume,
        recent_transactions=recent_transactions,
        recent_users=recent_users
    )


@bp.route('/users')
@login_required
@admin_required
def users():
    """
    List all users with search and filter options
    """
    # Get filter parameters from query string
    status_filter = request.args.get('status', 'all')  # 'all', 'active', 'inactive'
    search_query = request.args.get('search', '').strip()
    page = request.args.get('page', 1, type=int)
    per_page = 20
    
    # Build query
    query = User.query
    
    # Apply status filter
    if status_filter == 'active':
        query = query.filter_by(is_active=True)
    elif status_filter == 'inactive':
        query = query.filter_by(is_active=False)
    
    # Apply search filter (search by email or name)
    if search_query:
        search_pattern = f'%{search_query}%'
        query = query.filter(
            db.or_(
                User.email.ilike(search_pattern),
                User.full_name.ilike(search_pattern)
            )
        )
    
    # Order by most recent first
    query = query.order_by(desc(User.created_at))
    
    # Paginate results
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    users_list = pagination.items
    
    return render_template(
        'admin/users.html',
        title='Manage Users',
        users=users_list,
        pagination=pagination,
        status_filter=status_filter,
        search_query=search_query
    )


@bp.route('/user/<int:user_id>')
@login_required
@admin_required
def user_details(user_id):
    """
    View detailed information about a specific user
    Shows user accounts, recent transactions, and management options
    
    Args:
        user_id (int): User ID to display
    """
    user = User.query.get_or_404(user_id)
    
    # Get all user accounts
    accounts = user.accounts.all()
    
    # Get recent transactions for this user (across all accounts)
    account_ids = [acc.id for acc in accounts]
    recent_transactions = Transaction.query.filter(
        db.or_(
            Transaction.from_account_id.in_(account_ids),
            Transaction.to_account_id.in_(account_ids)
        )
    ).order_by(desc(Transaction.timestamp)).limit(20).all()
    
    # Calculate total balance
    total_balance = user.get_total_balance()
    
    return render_template(
        'admin/user_details.html',
        title=f'User: {user.email}',
        user=user,
        accounts=accounts,
        recent_transactions=recent_transactions,
        total_balance=total_balance
    )


@bp.route('/user/<int:user_id>/toggle-status', methods=['POST'])
@login_required
@admin_required
def toggle_user_status(user_id):
    """
    Toggle user active/inactive status (freeze/unfreeze user)
    Requires POST with CSRF token for security
    
    Args:
        user_id (int): User ID to toggle
    """
    user = User.query.get_or_404(user_id)
    
    # Toggle the status
    user.is_active = not user.is_active
    
    try:
        db.session.commit()
        
        status = "activated" if user.is_active else "deactivated"
        flash(f'User {user.email} has been {status} successfully.', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash('Failed to update user status. Please try again.', 'danger')
        print(f"Toggle user status error: {e}")
    
    return redirect(url_for('admin.user_details', user_id=user_id))


@bp.route('/account/<int:account_id>/toggle-freeze', methods=['POST'])
@login_required
@admin_required
def toggle_account_freeze(account_id):
    """
    Toggle account frozen status
    Requires POST with CSRF token for security
    
    Args:
        account_id (int): Account ID to toggle
    """
    account = Account.query.get_or_404(account_id)
    
    # Toggle the frozen status
    account.is_frozen = not account.is_frozen
    
    try:
        db.session.commit()
        
        status = "unfrozen" if not account.is_frozen else "frozen"
        flash(f'Account {account.account_number} has been {status} successfully.', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash('Failed to update account status. Please try again.', 'danger')
        print(f"Toggle account freeze error: {e}")
    
    return redirect(url_for('admin.user_details', user_id=account.user_id))


@bp.route('/transactions')
@login_required
@admin_required
def transactions():
    """
    View all transactions with filtering options
    """
    # Get filter parameters
    transaction_type = request.args.get('type', 'all')  # 'all', 'transfer', 'deposit', 'withdrawal'
    date_filter = request.args.get('date', '7')  # Days to look back (7, 30, 90, 'all')
    search_query = request.args.get('search', '').strip()  # Search by account number
    page = request.args.get('page', 1, type=int)
    per_page = 50
    
    # Build query
    query = Transaction.query
    
    # Apply transaction type filter
    if transaction_type != 'all':
        query = query.filter_by(transaction_type=transaction_type)
    
    # Apply date filter
    if date_filter != 'all':
        days_back = int(date_filter)
        cutoff_date = (datetime.utcnow() + timedelta(hours=5, minutes=30)) - timedelta(days=days_back)
        query = query.filter(Transaction.timestamp >= cutoff_date)
    
    # Apply search filter (search by account number)
    if search_query:
        # Find accounts matching the search
        matching_accounts = Account.query.filter(
            Account.account_number.like(f'%{search_query}%')
        ).all()
        account_ids = [acc.id for acc in matching_accounts]
        
        if account_ids:
            query = query.filter(
                db.or_(
                    Transaction.from_account_id.in_(account_ids),
                    Transaction.to_account_id.in_(account_ids)
                )
            )
        else:
            # No matching accounts, return empty result
            query = query.filter(Transaction.id == -1)
    
    # Order by most recent first
    query = query.order_by(desc(Transaction.timestamp))
    
    # Paginate results
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    transactions_list = pagination.items
    
    # Calculate total volume for filtered transactions
    if date_filter != 'all':
        days_back = int(date_filter)
        cutoff_date = (datetime.utcnow() + timedelta(hours=5, minutes=30)) - timedelta(days=days_back)
        volume_query = db.session.query(func.sum(Transaction.amount)).filter(
            Transaction.timestamp >= cutoff_date
        )
    else:
        volume_query = db.session.query(func.sum(Transaction.amount))
    
    if transaction_type != 'all':
        volume_query = volume_query.filter_by(transaction_type=transaction_type)
    
    total_volume_cents = volume_query.scalar() or 0
    total_volume = total_volume_cents / 100.0
    
    return render_template(
        'admin/transactions.html',
        title='Transactions Monitor',
        transactions=transactions_list,
        pagination=pagination,
        transaction_type=transaction_type,
        date_filter=date_filter,
        search_query=search_query,
        total_volume=total_volume
    )


@bp.route('/statistics')
@login_required
@admin_required
def statistics():
    """
    Detailed statistics and analytics page
    """
    # Account type distribution
    checking_count = Account.query.filter_by(account_type='checking').count()
    savings_count = Account.query.filter_by(account_type='savings').count()
    
    # Transaction type distribution (last 30 days)
    thirty_days_ago = (datetime.utcnow() + timedelta(hours=5, minutes=30)) - timedelta(days=30)
    
    transfer_count = Transaction.query.filter(
        Transaction.transaction_type == 'transfer',
        Transaction.timestamp >= thirty_days_ago
    ).count()
    
    deposit_count = Transaction.query.filter(
        Transaction.transaction_type == 'deposit',
        Transaction.timestamp >= thirty_days_ago
    ).count()
    
    withdrawal_count = Transaction.query.filter(
        Transaction.transaction_type == 'withdrawal',
        Transaction.timestamp >= thirty_days_ago
    ).count()
    
    # Average account balance
    avg_balance_cents = db.session.query(func.avg(Account.balance)).scalar() or 0
    avg_balance = avg_balance_cents / 100.0
    
    # Top 5 accounts by balance
    top_accounts = Account.query.order_by(desc(Account.balance)).limit(5).all()
    
    # Users with most transactions
    # This is complex, so we'll get top 5 users by number of accounts with transactions
    users_with_transaction_counts = db.session.query(
        User.id,
        User.email,
        User.full_name,
        func.count(Transaction.id).label('transaction_count')
    ).join(Account, User.id == Account.user_id).join(
        Transaction,
        db.or_(
            Transaction.from_account_id == Account.id,
            Transaction.to_account_id == Account.id
        )
    ).group_by(User.id).order_by(desc('transaction_count')).limit(5).all()
    
    return render_template(
        'admin/statistics.html',
        title='System Statistics',
        current_count=current_count,
        savings_count=savings_count,
        transfer_count=transfer_count,
        deposit_count=deposit_count,
        withdrawal_count=withdrawal_count,
        avg_balance=avg_balance,
        top_accounts=top_accounts,
        active_users=users_with_transaction_counts
    )


@bp.route('/search')
@login_required
@admin_required
def search():
    """
    Global search across users, accounts, and transactions
    """
    query = request.args.get('q', '').strip()
    
    if not query:
        flash('Please enter a search query.', 'warning')
        return redirect(url_for('admin.dashboard'))
    
    # Search users by email or name
    users_results = User.query.filter(
        db.or_(
            User.email.ilike(f'%{query}%'),
            User.full_name.ilike(f'%{query}%')
        )
    ).limit(10).all()
    
    # Search accounts by account number
    accounts_results = Account.query.filter(
        Account.account_number.like(f'%{query}%')
    ).limit(10).all()
    
    # Search transactions by description
    transactions_results = Transaction.query.filter(
        Transaction.description.ilike(f'%{query}%')
    ).order_by(desc(Transaction.timestamp)).limit(10).all()
    
    return render_template(
        'admin/search_results.html',
        title=f'Search: {query}',
        query=query,
        users=users_results,
        accounts=accounts_results,
        transactions=transactions_results
    )