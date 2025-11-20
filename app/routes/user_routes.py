"""
Banking Management System - User Routes
Handles user dashboard, accounts, transfers, and statements
"""
from flask import Blueprint, render_template, redirect, url_for, flash, request, abort, make_response
from flask_login import login_required, current_user
from app import db
from app.models import User, Admin, Account, Transaction
from app.forms import TransferForm, CreateAccountForm, ChangePasswordForm, DepositForm, WithdrawForm
from datetime import datetime, timedelta
import csv
from io import StringIO

# Create Blueprint
bp = Blueprint('user', __name__, url_prefix='/user')


def check_account_ownership(account_id):
    """
    Helper function to verify user owns the account
    
    Args:
        account_id (int): Account ID to check
        
    Returns:
        Account: Account object if owned by current user
        
    Raises:
        404: If account doesn't exist or doesn't belong to user
    """
    account = Account.query.get_or_404(account_id)
    if account.user_id != current_user.id:
        abort(403)  # Forbidden
    return account


@bp.route('/dashboard')
@login_required
def dashboard():
    """
    User dashboard - shows all accounts and recent transactions
    """
    # Redirect admins to their dashboard
    if isinstance(current_user, Admin):
        return redirect(url_for('admin.dashboard'))
    
    # Get all user accounts
    accounts = current_user.accounts.all()
    
    # Get recent transactions across all accounts (last 10)
    transactions_map = {}
    for account in accounts:
        transactions = account.get_all_transactions()
        for tx in transactions:
            transactions_map[tx.id] = tx
            
    # Convert back to a list
    recent_transactions = list(transactions_map.values())
    
    # Sort by timestamp and limit to 10
    recent_transactions = sorted(recent_transactions, key=lambda x: x.timestamp, reverse=True)[:10]
    
    # Calculate total balance
    total_balance = current_user.get_total_balance()
    
    return render_template(
        'user/dashboard.html',
        title='Dashboard',
        accounts=accounts,
        recent_transactions=recent_transactions,
        total_balance=total_balance
    )


@bp.route('/account/<int:account_id>')
@login_required
def account_details(account_id):
    """
    Account details page - shows specific account info and all transactions
    
    Args:
        account_id (int): Account ID to display
    """
    # Redirect admins
    if isinstance(current_user, Admin):
        return redirect(url_for('admin.dashboard'))
    
    # Verify ownership
    account = check_account_ownership(account_id)
    
    # Get all transactions for this account
    transactions = account.get_all_transactions()
    
    return render_template(
        'user/account_details.html',
        title=f'Account {account.account_number}',
        account=account,
        transactions=transactions
    )


@bp.route('/transfer', methods=['GET', 'POST'])
@login_required
def transfer():
    """
    Money transfer page
    GET: Display transfer form
    POST: Process transfer between accounts
    """
    # Redirect admins
    if isinstance(current_user, Admin):
        flash('Admins cannot perform transfers.', 'warning')
        return redirect(url_for('admin.dashboard'))
    
    form = TransferForm()
    
    # Populate account choices with user's active accounts
    user_accounts = Account.query.filter_by(
        user_id=current_user.id,
        is_frozen=False
    ).all()
    
    if not user_accounts:
        flash('You need at least one active account to make transfers.', 'warning')
        return redirect(url_for('user.dashboard'))
    
    form.from_account.choices = [(acc.id, f'{acc.account_number} - {acc.account_type.title()} (₹{acc.get_balance():.2f})') 
                                   for acc in user_accounts]
    
    if form.validate_on_submit():
        try:
            # Get source account
            from_account = Account.query.get(form.from_account.data)
            
            # Verify ownership (security check)
            if from_account.user_id != current_user.id:
                flash('Invalid source account.', 'danger')
                return redirect(url_for('user.transfer'))
            
            # Check if account is frozen
            if from_account.is_frozen:
                flash('Your account is frozen. Please contact support.', 'danger')
                return redirect(url_for('user.dashboard'))
            
            # Get destination account
            to_account = Account.query.filter_by(account_number=form.to_account_id.data).first()
            
            if not to_account:
                flash('Destination account not found.', 'danger')
                return redirect(url_for('user.transfer'))
            
            # Check if destination account is frozen
            if to_account.is_frozen:
                flash('Destination account is frozen and cannot receive transfers.', 'danger')
                return redirect(url_for('user.transfer'))
            
            # Prevent self-transfer
            if from_account.id == to_account.id:
                flash('Cannot transfer to the same account.', 'warning')
                return redirect(url_for('user.transfer'))
            
            # Convert amount to cents
            amount_cents = int(form.amount.data * 100)
            
            # Check sufficient balance
            if from_account.balance < amount_cents:
                flash(f'Insufficient balance. Available: ₹{from_account.get_balance():.2f}', 'danger')
                return redirect(url_for('user.transfer'))
            
            # Perform atomic transaction
            try:
                # Deduct from source account
                from_account.balance -= amount_cents
                
                # Add to destination account
                to_account.balance += amount_cents
                
                # Create transaction record
                transaction = Transaction(
                    from_account_id=from_account.id,
                    to_account_id=to_account.id,
                    amount=amount_cents,
                    transaction_type='transfer',
                    description=form.description.data or f'Transfer to {to_account.account_number}',
                    timestamp=datetime.utcnow() + timedelta(hours=5, minutes=30)
                )
                
                db.session.add(transaction)
                db.session.commit()
                
                flash(f'Successfully transferred ₹{form.amount.data:.2f} to account {to_account.account_number}!', 'success')
                return redirect(url_for('user.dashboard'))
                
            except Exception as e:
                db.session.rollback()
                flash('Transfer failed. Please try again.', 'danger')
                print(f"Transfer error: {e}")
                return redirect(url_for('user.transfer'))
                
        except Exception as e:
            flash('An error occurred. Please try again.', 'danger')
            print(f"Transfer validation error: {e}")
            return redirect(url_for('user.transfer'))
    
    return render_template('user/transfer.html', title='Transfer Money', form=form)


@bp.route('/statement/<int:account_id>')
@login_required
def statement(account_id):
    """
    Download CSV statement for an account
    
    Args:
        account_id (int): Account ID to generate statement for
        
    Returns:
        CSV file as attachment
    """
    # Redirect admins
    if isinstance(current_user, Admin):
        flash('Admins cannot download user statements.', 'warning')
        return redirect(url_for('admin.dashboard'))
    
    # Verify ownership
    account = check_account_ownership(account_id)
    
    # Get all transactions
    transactions = account.get_all_transactions()
    
    # Create CSV in memory
    output = StringIO()
    output.write('\ufeff')
    writer = csv.writer(output)
    
    # Write header
    writer.writerow([
        'Date',
        'Type',
        'From Account',
        'To Account',
        'Amount',
        'Balance After',
        'Description'
    ])
    
    # Calculate running balance
    running_balance = account.balance
    
    # Write transactions (most recent first, so we need to reverse for balance calculation)
    for transaction in reversed(transactions):
        # Determine if money came in or went out
        if transaction.to_account_id == account.id:
            # Money received
            amount_str = f'+₹{transaction.get_amount():.2f}'
            from_acc = transaction.source_account.account_number if transaction.source_account else 'External'
            to_acc = account.account_number
        elif transaction.from_account_id == account.id:
            # Money sent
            amount_str = f'-₹{transaction.get_amount():.2f}'
            from_acc = account.account_number
            to_acc = transaction.destination_account.account_number if transaction.destination_account else 'External'
        else:
            continue  # Skip if transaction doesn't involve this account
        
        writer.writerow([
            transaction.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
            transaction.transaction_type.title(),
            from_acc,
            to_acc,
            amount_str,
            f'₹{running_balance / 100:.2f}',
            transaction.description or 'N/A'
        ])
    
    # Create response
    output.seek(0)
    response = make_response(output.getvalue())
    response.headers['Content-Type'] = 'text/csv'
    response.headers['Content-Disposition'] = f'attachment; filename=statement_{account.account_number}_{datetime.now().strftime("%Y%m%d")}.csv'
    
    return response


@bp.route('/create-account', methods=['GET', 'POST'])
@login_required
def create_account():
    """
    Create new bank account for current user
    GET: Display account creation form
    POST: Create new account
    """
    # Redirect admins
    if isinstance(current_user, Admin):
        flash('Admins cannot create accounts for themselves.', 'warning')
        return redirect(url_for('admin.dashboard'))
    
    form = CreateAccountForm()
    
    if form.validate_on_submit():
        try:
            from app.models import generate_account_number
            
            # Convert initial deposit to cents
            initial_balance = int(form.initial_deposit.data * 100)
            
            # Create new account
            new_account = Account(
                user_id=current_user.id,
                account_number=generate_account_number(),
                account_type=form.account_type.data,
                balance=initial_balance
            )
            
            db.session.add(new_account)
            db.session.commit()
            
            flash(f'New {form.account_type.data} account created successfully! Account number: {new_account.account_number}', 'success')
            return redirect(url_for('user.dashboard'))
            
        except Exception as e:
            db.session.rollback()
            flash('Failed to create account. Please try again.', 'danger')
            print(f"Account creation error: {e}")
    
    return render_template('user/create_account.html', title='Create Account', form=form)


@bp.route('/deposit', methods=['GET', 'POST'])
@login_required
def deposit():
    """
    Deposit money into account (simulation)
    GET: Display deposit form
    POST: Process deposit
    """
    # Redirect admins
    if isinstance(current_user, Admin):
        flash('Admins cannot deposit money.', 'warning')
        return redirect(url_for('admin.dashboard'))
    
    form = DepositForm()
    
    # Populate account choices
    user_accounts = Account.query.filter_by(
        user_id=current_user.id,
        is_frozen=False
    ).all()
    
    if not user_accounts:
        flash('You need at least one active account to make deposits.', 'warning')
        return redirect(url_for('user.dashboard'))
    
    form.account.choices = [(acc.id, f'{acc.account_number} - {acc.account_type.title()}') 
                            for acc in user_accounts]
    
    if form.validate_on_submit():
        try:
            account = Account.query.get(form.account.data)
            
            # Verify ownership
            if account.user_id != current_user.id:
                flash('Invalid account.', 'danger')
                return redirect(url_for('user.deposit'))
            
            # Convert amount to cents
            amount_cents = int(form.amount.data * 100)
            
            # Perform deposit
            account.balance += amount_cents
            
            # Create transaction record
            transaction = Transaction(
                to_account_id=account.id,
                amount=amount_cents,
                transaction_type='deposit',
                description=form.description.data or 'Cash deposit',
                timestamp=datetime.utcnow() + timedelta(hours=5, minutes=30)
            )
            
            db.session.add(transaction)
            db.session.commit()
            
            flash(f'Successfully deposited ₹{form.amount.data:.2f} into account {account.account_number}!', 'success')
            return redirect(url_for('user.dashboard'))
            
        except Exception as e:
            db.session.rollback()
            flash('Deposit failed. Please try again.', 'danger')
            print(f"Deposit error: {e}")
    
    return render_template('user/deposit.html', title='Deposit Money', form=form)


@bp.route('/withdraw', methods=['GET', 'POST'])
@login_required
def withdraw():
    """
    Withdraw money from account
    GET: Display withdrawal form
    POST: Process withdrawal
    """
    # Redirect admins
    if isinstance(current_user, Admin):
        flash('Admins cannot withdraw money.', 'warning')
        return redirect(url_for('admin.dashboard'))
    
    form = WithdrawForm()
    
    # Populate account choices
    user_accounts = Account.query.filter_by(
        user_id=current_user.id,
        is_frozen=False
    ).all()
    
    if not user_accounts:
        flash('You need at least one active account to make withdrawals.', 'warning')
        return redirect(url_for('user.dashboard'))
    
    form.account.choices = [(acc.id, f'{acc.account_number} - {acc.account_type.title()} (₹{acc.get_balance():.2f})') 
                            for acc in user_accounts]
    
    if form.validate_on_submit():
        try:
            account = Account.query.get(form.account.data)
            
            # Verify ownership
            if account.user_id != current_user.id:
                flash('Invalid account.', 'danger')
                return redirect(url_for('user.withdraw'))
            
            # Convert amount to cents
            amount_cents = int(form.amount.data * 100)
            
            # Check sufficient balance
            if account.balance < amount_cents:
                flash(f'Insufficient balance. Available: ₹{account.get_balance():.2f}', 'danger')
                return redirect(url_for('user.withdraw'))
            
            # Perform withdrawal
            account.balance -= amount_cents
            
            # Create transaction record
            transaction = Transaction(
                from_account_id=account.id,
                amount=amount_cents,
                transaction_type='withdrawal',
                description=form.description.data or 'Cash withdrawal',
                timestamp=datetime.utcnow() + timedelta(hours=5, minutes=30)
            )
            
            db.session.add(transaction)
            db.session.commit()
            
            flash(f'Successfully withdrew ₹{form.amount.data:.2f} from account {account.account_number}!', 'success')
            return redirect(url_for('user.dashboard'))
            
        except Exception as e:
            db.session.rollback()
            flash('Withdrawal failed. Please try again.', 'danger')
            print(f"Withdrawal error: {e}")
    
    return render_template('user/withdraw.html', title='Withdraw Money', form=form)


@bp.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    """
    Change user password
    GET: Display password change form
    POST: Update password
    """
    # Redirect admins
    if isinstance(current_user, Admin):
        return redirect(url_for('admin.dashboard'))
    
    form = ChangePasswordForm()
    
    if form.validate_on_submit():
        # Verify current password
        if not current_user.verify_password(form.current_password.data):
            flash('Current password is incorrect.', 'danger')
            return redirect(url_for('user.change_password'))
        
        # Update password
        current_user.set_password(form.new_password.data)
        db.session.commit()
        
        flash('Password changed successfully!', 'success')
        return redirect(url_for('user.dashboard'))
    
    return render_template('user/change_password.html', title='Change Password', form=form)