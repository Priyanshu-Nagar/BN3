# Banking Management System

A Flask-based web application for managing virtual banking operations. Built for college project demonstration purposes.

## Features

- **User Portal**: Register, login, check balance, transfer money, download statements
- **Admin Portal**: Manage users, view transactions, freeze/unfreeze accounts
- **Database**: SQLite (no external setup required)
- **Security**: Password hashing, session management, role-based access

## Tech Stack

- Python 3.11+
- Flask 3.0+
- SQLAlchemy (ORM)
- Flask-Login (Authentication)
- Flask-WTF (Forms)
- Bootstrap 5 (Frontend)
- SQLite (Database)

## Local Development Setup

### 1. Create Virtual Environment

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# macOS/Linux
python3 -m venv venv
source venv/bin/activate
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Run the Application

```bash
python run.py
```

The app will be available at: `http://localhost:5000`

### 4. Default Admin Credentials

After first run, an admin account will be created:
- **Username**: admin
- **Password**: admin123

**⚠️ Change this password immediately after first login!**

## Project Structure

```
banking_app/
├── run.py                 # Application entry point
├── requirements.txt       # Python dependencies
├── README.md             # This file
├── app/                  # Main application package
│   ├── __init__.py       # App factory
│   ├── models.py         # Database models
│   ├── routes/           # Route blueprints
│   ├── templates/        # HTML templates
│   └── static/           # CSS, JS, images
└── instance/             # Instance-specific files (created on first run)
    └── banking.db        # SQLite database
```

## Notes

- This is a **demo application** for educational purposes only
- Not intended for production use with real money
- SQLite database is stored in `instance/banking.db`
- All passwords are hashed using Werkzeug security

## Troubleshooting

**Port already in use:**
```bash
# Change port in run.py or use:
python run.py --port 5001
```

**Dependencies not installing:**
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

## License

Educational use only - College Project Demo