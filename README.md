# BrightPath Training Center — Online Enrollment System

A Flask web application for a fictional short-course training center. Students can register, sign in, browse courses, submit enrollment applications, and manage their own applications. Administrators can manage courses and review all enrollments.

## Features
- Public landing page with clear enrollment calls to action and course listing.
- Student registration, login, and logout.
- Password hashing using Werkzeug; passwords are never stored in plain text.
- Student/admin roles with server-side access checks.
- Enrollment CRUD (create, read, update, delete) and admin course creation/deletion.
- WTForms validation for required fields, email, password length/confirmation, contact number, fee, slots, duplicate email, and duplicate course code.
- CSRF tokens on forms and confirmation prompts before deletes.
- Starter courses are created automatically when the application starts.

## Requirements
- Python 3.11 or newer
- pip

## Local setup

```bash
git clone https://github.com/haaaninn/Online-Enrollment.git
cd Online-Enrollment
python -m venv .venv
# Windows PowerShell: .venv\Scripts\Activate.ps1
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
```

Copy `.env.example` to `.env`, then set unique values for `SECRET_KEY` and `ADMIN_PASSWORD`. Do not use the example values in a real deployment. Run the app:

```bash
python app.py
```

Open http://127.0.0.1:5000. The initial admin email is `admin@enroll.local`; its password is the value you set for `ADMIN_PASSWORD` before the first startup. If the database already has an admin account, changing the environment variable does not reset that account's password.

## Render deployment
- Build command: `pip install -r requirements.txt`
- Start command: `gunicorn app:app`
- Add environment variables `SECRET_KEY` (long random secret), `ADMIN_PASSWORD` (strong unique password), and `FLASK_DEBUG=0` in Render's Environment settings.
- Configure `DATABASE_URL` to a managed PostgreSQL database for production. The default SQLite database is suitable for local demos only; ephemeral hosting storage may not persist data across deploys/restarts.

## Security and data notes
- `.env`, database files, Python virtual environments, and uploaded files are excluded by `.gitignore`.
- Use HTTPS in deployment, keep dependencies updated, and back up the production database.
- The seeded admin email is predictable for a classroom demo. Change the admin email/password strategy before public production use.
- Deleting an enrollment is permanent. Course deletion is blocked when enrollments are linked to that course.

## AI assistance disclosure
AI assistance (ChatGPT) was used to help draft, review, and improve parts of the application and documentation. The project owner should review the final code, understand it, and disclose assistance according to the instructor's rules.

## Repository
https://github.com/haaaninn/Online-Enrollment
