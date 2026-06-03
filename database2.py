"""
Run this script once to initialize the database schema and seed data.
Usage: python database2.py
"""
import mysql.connector
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash
import os

load_dotenv()

cnx = mysql.connector.connect(
    host=os.getenv('DB_HOST', '127.0.0.1'),
    user=os.getenv('DB_USER'),
    password=os.getenv('DB_PASSWORD'),
    use_pure=True,
)

cursor = cnx.cursor()

db_name = os.getenv('DB_NAME', 'testi5')
cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{db_name}`")
cursor.execute(f"USE `{db_name}`")


def add_column_if_missing(table, col_def):
    col_name = col_def.split()[0]
    try:
        cursor.execute(f"ALTER TABLE {table} ADD COLUMN {col_def}")
    except mysql.connector.Error:
        pass


# ── Roles ────────────────────────────────────────────────────────────
cursor.execute("""
CREATE TABLE IF NOT EXISTS roles (
    id INT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(255)
)
""")
cursor.execute("INSERT IGNORE INTO roles (id, name) VALUES (1,'student'),(2,'teacher'),(3,'admin')")

# ── Users ────────────────────────────────────────────────────────────
cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    id   INT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(255),
    email VARCHAR(255) UNIQUE,
    password VARCHAR(255),
    role_id INT,
    phone VARCHAR(50),
    FOREIGN KEY (role_id) REFERENCES roles(id)
)
""")
add_column_if_missing('users', 'phone VARCHAR(50)')

admin_password = os.getenv('ADMIN_PASSWORD', 'admin123')
cursor.execute("""
INSERT IGNORE INTO users (id, name, email, password, role_id) VALUES
(1, 'Admin', 'admin@example.com', %s, 3)
""", (generate_password_hash(admin_password),))

cursor.execute("""
INSERT IGNORE INTO users (id, name, email, password, role_id) VALUES
(2, 'Matti Virtanen', 'matti.virtanen@eduportal.fi', %s, 2)
""", (generate_password_hash('teacher123'),))

# ── Course ───────────────────────────────────────────────────────────
cursor.execute("""
CREATE TABLE IF NOT EXISTS course (
    id           INT PRIMARY KEY AUTO_INCREMENT,
    title        VARCHAR(255),
    description  TEXT,
    start_date   DATE,
    end_date     DATE,
    location     VARCHAR(255),
    instructor   VARCHAR(255),
    course_code  VARCHAR(20),
    ects_credits DECIMAL(3,1) DEFAULT 5.0,
    category     VARCHAR(100),
    teacher_id   INT,
    enrollment_open  DATE,
    enrollment_close DATE,
    FOREIGN KEY (teacher_id) REFERENCES users(id)
)
""")
for col in [
    'course_code VARCHAR(20)',
    'ects_credits DECIMAL(3,1) DEFAULT 5.0',
    'category VARCHAR(100)',
    'teacher_id INT',
    'enrollment_open DATE',
    'enrollment_close DATE',
]:
    add_column_if_missing('course', col)

cursor.execute("""
INSERT IGNORE INTO course
    (id, title, description, start_date, end_date, location, instructor,
     course_code, ects_credits, category, teacher_id, enrollment_open, enrollment_close)
VALUES
(1, 'Ohjelmoinnin perusteet',
    'Python-ohjelmoinnin perusteet alusta alkaen',
    '2026-09-01','2026-11-30','Luokka A101','Matti Virtanen',
    'OHJ-101', 5.0, 'Ohjelmointi', 2, '2026-08-01','2026-08-25'),
(2, 'Tietorakenteet ja algoritmit',
    'Tietorakenteet ja algoritmit Python-kielellä',
    '2026-09-01','2026-11-30','Luokka B203','Matti Virtanen',
    'OHJ-201', 5.0, 'Ohjelmointi', 2, '2026-08-01','2026-08-25'),
(3, 'Web-kehitys Flaskilla',
    'Web-sovellusten rakentaminen Flask-kehyksellä',
    '2026-09-02','2026-11-30','Luokka C301','Matti Virtanen',
    'WEB-101', 5.0, 'Web-kehitys', 2, '2026-08-01','2026-08-25')
""")

# ── Session ──────────────────────────────────────────────────────────
cursor.execute("""
CREATE TABLE IF NOT EXISTS session (
    id              INT PRIMARY KEY AUTO_INCREMENT,
    course_id       INT,
    start_date      DATE,
    start_time      TIME,
    end_date        DATE,
    end_time        TIME,
    spots_available INT,
    FOREIGN KEY (course_id) REFERENCES course(id)
)
""")
cursor.execute("""
INSERT IGNORE INTO session (id, course_id, start_date, start_time, end_date, end_time, spots_available) VALUES
(1, 1, '2026-09-01','09:00:00','2026-11-30','12:00:00', 20),
(2, 2, '2026-09-01','13:00:00','2026-11-30','16:00:00', 15),
(3, 3, '2026-09-02','10:00:00','2026-11-30','13:00:00', 18)
""")

# ── Student ──────────────────────────────────────────────────────────
cursor.execute("""
CREATE TABLE IF NOT EXISTS student (
    id               INT PRIMARY KEY AUTO_INCREMENT,
    name             VARCHAR(255),
    email            VARCHAR(255),
    phone            VARCHAR(255),
    student_group    VARCHAR(50),
    enrollment_year  INT
)
""")
for col in ['student_group VARCHAR(50)', 'enrollment_year INT']:
    add_column_if_missing('student', col)

# ── Enrollment ───────────────────────────────────────────────────────
cursor.execute("""
CREATE TABLE IF NOT EXISTS enrollment (
    id             INT PRIMARY KEY AUTO_INCREMENT,
    student_id     INT,
    session_id     INT,
    course_id      INT,
    payment_amount FLOAT,
    payment_date   DATE,
    grade          VARCHAR(10),
    status         VARCHAR(20) DEFAULT 'active',
    completed_at   DATETIME,
    FOREIGN KEY (student_id) REFERENCES student(id),
    FOREIGN KEY (session_id) REFERENCES session(id),
    FOREIGN KEY (course_id)  REFERENCES course(id)
)
""")
for col in [
    'grade VARCHAR(10)',
    'status VARCHAR(20) DEFAULT \'active\'',
    'completed_at DATETIME',
]:
    add_column_if_missing('enrollment', col)

# ── Attendance ───────────────────────────────────────────────────────
cursor.execute("""
CREATE TABLE IF NOT EXISTS attendance (
    id         INT PRIMARY KEY AUTO_INCREMENT,
    session_id INT NOT NULL,
    student_id INT NOT NULL,
    present    BOOLEAN DEFAULT FALSE,
    marked_at  DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES session(id),
    FOREIGN KEY (student_id) REFERENCES student(id),
    UNIQUE KEY uq_attendance (session_id, student_id)
)
""")

# ── Waiting List ─────────────────────────────────────────────────────
cursor.execute("""
CREATE TABLE IF NOT EXISTS waiting_list (
    id         INT PRIMARY KEY AUTO_INCREMENT,
    course_id  INT NOT NULL,
    student_id INT NOT NULL,
    position   INT NOT NULL,
    joined_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (course_id)  REFERENCES course(id),
    FOREIGN KEY (student_id) REFERENCES student(id),
    UNIQUE KEY uq_waiting (course_id, student_id)
)
""")

cnx.commit()
cursor.close()
cnx.close()

print("Database initialized successfully.")
