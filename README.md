# EduPortal

A full-featured Learning Management System (LMS) built with Flask and MySQL, modelled on real Finnish school workflows. Supports bilingual UI (Finnish / English), role-based access for admins, teachers and students, and deploys to production with a single `docker compose up`.

---

## Features

### For Students
- Browse and enrol in courses with ECTS credit information
- Automatic waiting list when a course is full — promoted automatically when a spot opens
- Personal transcript with earned ECTS total and Finnish grade history
- View sessions you're enrolled in

### For Teachers
- Dashboard scoped to own courses only
- Enter grades (1–5, HYV, HYL) per student per course
- Mark session attendance with a checkbox form
- View all students in your courses

### For Admins
- Full course management — course code, ECTS credits, category, enrolment window, assigned teacher
- Create and manage users (admin / teacher / student roles)
- Student group and enrolment year tracking
- Export student list and enrolment data as Excel-compatible CSV (UTF-8 BOM)
- System statistics: total courses, students, enrolments, open sessions, waiting list count

### Platform
- **Modern split-screen login page** — brand panel on left, clean form on right
- Bilingual UI — Finnish and English, switchable per session
- Finnish grading system (1–5, HYV, HYL) and ECTS credits
- Profile editing and password change for all users
- Custom 404 / 500 error pages
- Production-ready — served by Gunicorn 21 with 2 workers
- Comprehensive role-based dashboards

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.12 · Flask 3.0 · Flask-Login · Flask-Mail |
| i18n | Flask-Babel 3.1 (FI / EN) |
| Database | MySQL 8.0 via mysql-connector-python |
| Auth | Werkzeug password hashing |
| Production server | Gunicorn 21 (2 workers) |
| Containerisation | Docker · Docker Compose |
| Frontend | Bootstrap 5.3, Font Awesome 6.4, Inter font |

---

## Quick Start

### Prerequisites
- Docker Desktop

### 1. Clone and configure

```bash
git clone https://github.com/arttujussikil/opintoportaali.git
cd opintoportaali
cp .env.example .env
# Edit .env if you want to change passwords or mail settings
```

### 2. Start

```bash
docker compose up --build
```

The app is available at **http://localhost:5000**

The database is initialised automatically on first boot.

---

## Demo Accounts

| Role | Email | Password |
|---|---|---|
| Admin | `admin@example.com` | `admin123` |
| Teacher | `matti.virtanen@eduportal.fi` | `teacher123` |
| Student | `emma.korhonen@eduportal.fi` | `student123` |

---

## Role-Based Access

### Admin Dashboard
- System-wide statistics (courses, students, enrolments, sessions, waiting list)
- Manage all courses (create, edit, delete, assign teacher)
- Create users and assign roles
- View student roster
- Access all enrollments and sessions
- Entry forms: grades and attendance for all courses
- CSV export: students and enrollments

### Teacher Dashboard
- Statistics for own courses only (students, enrollments, sessions, waiting list in their courses)
- View and edit own courses
- Student roster (who's enrolled in your courses)
- Access enrollments and sessions for your courses
- Grade entry form (per student per course)
- Attendance form (per session)

### Student Dashboard
- Personal statistics: my enrollments, earned ECTS, available courses, waiting list position
- Browse available courses and reserve spots
- Waiting list auto-promotion when a spot opens
- Personal transcript with grades and completion status
- View upcoming sessions
- Cancel reservations

---

## Project Structure

```
opintoportaali/
├── app.py                  # Flask application, routes, auth
├── course_management.py    # All DB logic (courses, enrolments, grades, …)
├── database2.py            # Schema creation and seed data
├── requirements.txt
├── babel.cfg               # Flask-Babel extraction config
├── Dockerfile
├── docker-compose.yml
├── entrypoint.sh           # DB init → Gunicorn startup
├── .env.example
│
├── static/
│   ├── styles.css          # App design (dark theme)
│   ├── login.css           # Login page (split-screen)
│   └── flash_messages.js
│
├── templates/
│   ├── base.html           # Sidebar layout + language switcher
│   ├── login.html          # Split-screen login
│   ├── dashboard.html
│   ├── courses.html
│   ├── course_grades.html
│   ├── course_attendance.html
│   ├── transcript.html
│   ├── profile.html
│   └── … (10+ additional pages)
│
└── translations/
    ├── fi/LC_MESSAGES/messages.po   # Finnish
    └── en/LC_MESSAGES/messages.po   # English (falls back to msgid)
```

---

## Database Schema (key tables)

```
users           id, name, email, password_hash, role_id, phone
student         user_id, student_group, enrollment_year
course          id, title, course_code, ects_credits, category,
                teacher_id, max_students, enrollment_open/close
session         id, course_id, session_date, location
enrollment      id, course_id, session_id, student_id,
                grade, status, completed_at
attendance      session_id, student_id, present
waiting_list    course_id, student_id, position, joined_at
```

---

## Adding Translations

```bash
# Extract new strings from Python and Jinja templates
pybabel extract -F babel.cfg -o translations/messages.pot .

# Update .po files
pybabel update -i translations/messages.pot -d translations

# Edit translations/fi/LC_MESSAGES/messages.po, then rebuild
docker compose up --build
```

---

## Environment Variables

See `.env.example` for all available options:

```
MYSQL_HOST, MYSQL_PORT, MYSQL_USER, MYSQL_PASSWORD, MYSQL_DATABASE
SECRET_KEY
MAIL_SERVER, MAIL_PORT, MAIL_USERNAME, MAIL_PASSWORD
```

---

## Academic Context

Built as a practical demonstration of a production-ready web application using a relational database. Covers:

- Relational schema design with live migrations
- Role-based access control (RBAC)
- Internationalisation (i18n) with compiled message catalogs
- Session management and secure password hashing
- Docker-based deployment with health checks and Gunicorn
- Finnish educational data model (ECTS, grading scale, student groups)
- Clean, modern UI/UX design principles
