import pytest
from app import create_app, db, Config
from app.models import User, Account, Admin

class TestConfig(Config):
    """Test configuration that uses in-memory database and disables CSRF"""
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False  # Disable CSRF forms protection for testing

@pytest.fixture
def client():
    """Fixture to configure the app and database for tests"""
    app = create_app(TestConfig)
    
    # Create a test client
    with app.test_client() as client:
        # Establish an application context
        with app.app_context():
            db.create_all()  # Create tables
            yield client     # Yield the client for the test
            db.session.remove()
            db.drop_all()    # Clean up after test

def test_register_and_login_flow(client):
    """Test that a user can register and then log in"""
    # 1. Register a new user
    register_response = client.post('/auth/register', data={
        'email': 'newuser@test.com',
        'password': 'password123',
        'confirm': 'password123'
    }, follow_redirects=True)
    
    # Check registration success
    assert register_response.status_code == 200
    assert b'Registration successful' in register_response.data
    
    # Verify user is in database
    with client.application.app_context():
        user = User.query.filter_by(email='newuser@test.com').first()
        assert user is not None
        # Verify default account creation
        assert user.accounts.count() == 1
        assert user.accounts.first().balance == 10000  # Default 100.00

    # 2. Login with the new credentials
    login_response = client.post('/auth/login', data={
        'email': 'newuser@test.com',
        'password': 'password123'
    }, follow_redirects=True)
    
    # Check login success
    assert login_response.status_code == 200
    assert b'Dashboard' in login_response.data
    assert b'newuser@test.com' in login_response.data

def test_create_transfer_and_balance_update(client):
    """Test creating a transfer between accounts and verifying balances"""
    with client.application.app_context():
        # Setup: Create two users with accounts
        # User 1 (Sender)
        u1 = User(email='sender@test.com', full_name='Sender')
        u1.set_password('pass')
        db.session.add(u1)
        db.session.flush() # Flush to get ID
        
        acc1 = Account(
            user_id=u1.id, 
            account_number='1000000001', 
            account_type='checking', 
            balance=5000 # ₹50.00
        )
        db.session.add(acc1)
        
        # User 2 (Receiver)
        u2 = User(email='receiver@test.com', full_name='Receiver')
        u2.set_password('pass')
        db.session.add(u2)
        db.session.flush()
        
        acc2 = Account(
            user_id=u2.id, 
            account_number='2000000002', 
            account_type='savings', 
            balance=1000 # ₹10.00
        )
        db.session.add(acc2)
        db.session.commit()

        # Save IDs for later verification
        acc1_id = acc1.id
        acc2_id = acc2.id

    # Login as Sender
    client.post('/auth/login', data={
        'email': 'sender@test.com', 
        'password': 'pass'
    }, follow_redirects=True)

    # Perform Transfer: ₹20.00 from acc1 to acc2
    response = client.post('/user/transfer', data={
        'from_account': acc1_id,
        'to_account_id': '2000000002',
        'amount': 20.00,
        'description': 'Test Transfer'
    }, follow_redirects=True)

    assert response.status_code == 200
    assert b'Successfully transferred' in response.data

    # Verify Balances in Database
    with client.application.app_context():
        # Reload accounts
        sender_acc = db.session.get(Account, acc1_id)
        receiver_acc = db.session.get(Account, acc2_id)

        # Sender: 50.00 - 20.00 = 30.00 (3000 cents)
        assert sender_acc.balance == 3000
        
        # Receiver: 10.00 + 20.00 = 30.00 (3000 cents)
        assert receiver_acc.balance == 3000

def test_admin_access_control(client):
    """Test that non-admins cannot access admin routes"""
    with client.application.app_context():
        # Create a Regular User
        user = User(email='regular@test.com', full_name='Regular')
        user.set_password('pass')
        db.session.add(user)
        
        # Create an Admin User
        admin = Admin(username='admin_user', email='admin@test.com')
        admin.set_password('adminpass')
        db.session.add(admin)
        db.session.commit()

    # 1. Attempt access without login
    resp_anon = client.get('/admin/dashboard', follow_redirects=True)
    # Should redirect to admin login page with a warning
    assert b'Please log in' in resp_anon.data
    assert b'Admin Login' in resp_anon.data

    # 2. Login as Regular User and attempt access
    client.post('/auth/login', data={
        'email': 'regular@test.com', 
        'password': 'pass'
    }, follow_redirects=True)
    
    resp_user = client.get('/admin/dashboard')
    # Should return 403 Forbidden (as per admin_required decorator)
    assert resp_user.status_code == 403

    # Logout
    client.get('/auth/logout', follow_redirects=True)

    # 3. Login as Admin and attempt access
    client.post('/auth/admin-login', data={
        'username': 'admin_user', 
        'password': 'adminpass'
    }, follow_redirects=True)
    
    resp_admin = client.get('/admin/dashboard')
    # Should succeed
    assert resp_admin.status_code == 200
    assert b'Admin Dashboard' in resp_admin.data