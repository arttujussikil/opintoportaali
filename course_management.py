import mysql.connector
from dotenv import load_dotenv
import os
import random
from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

load_dotenv()

_mydb = None


def get_db():
    global _mydb
    _conn_kwargs = dict(
        host=os.getenv('DB_HOST', '127.0.0.1'),
        user=os.getenv('DB_USER'),
        password=os.getenv('DB_PASSWORD'),
        database=os.getenv('DB_NAME'),
        use_pure=True,
    )
    try:
        if _mydb is None or not _mydb.is_connected():
            _mydb = mysql.connector.connect(**_conn_kwargs)
        else:
            _mydb.ping(reconnect=True, attempts=3, delay=2)
    except mysql.connector.Error:
        _mydb = mysql.connector.connect(**_conn_kwargs)
    return _mydb


class _DBProxy:
    def cursor(self, **kwargs):
        return get_db().cursor(**kwargs)
    def commit(self):
        return get_db().commit()
    def is_connected(self):
        return get_db().is_connected()

mydb = _DBProxy()


class User(UserMixin):
    def __init__(self, user_id, username, email, role_id):
        self.id = user_id
        self.name = username
        self.email = email
        self.role_id = role_id

    @property
    def is_authenticated(self):
        return True

    @property
    def is_active(self):
        return True

    @property
    def is_anonymous(self):
        return False

    @property
    def is_admin(self):
        return self.role_id == 3

    @property
    def is_teacher(self):
        return self.role_id == 2

    @property
    def is_student(self):
        return self.role_id == 1

    def get_id(self):
        return str(self.id)


# ── Auth ─────────────────────────────────────────────────────────────

def login(username, password):
    db = get_db()
    cursor = db.cursor(buffered=True)
    try:
        cursor.execute(
            "SELECT users.*, roles.name FROM users "
            "INNER JOIN roles ON users.role_id = roles.id "
            "WHERE users.email = %s OR users.name = %s",
            (username, username),
        )
        user = cursor.fetchone()
        if user and check_password_hash(user[3], password):
            return True, User(user[0], user[1], user[2], user[4])
        return False, None
    finally:
        cursor.close()


def verify_password(user_id, password):
    db = get_db()
    cursor = db.cursor(buffered=True)
    try:
        cursor.execute("SELECT password FROM users WHERE id = %s", (user_id,))
        row = cursor.fetchone()
        return check_password_hash(row[0], password) if row else False
    finally:
        cursor.close()


def update_user_profile(user_id, name, phone):
    db = get_db()
    cursor = db.cursor()
    try:
        cursor.execute(
            "UPDATE users SET name=%s, phone=%s WHERE id=%s",
            (name, phone, user_id),
        )
        cursor.execute(
            "UPDATE student SET name=%s, phone=%s WHERE id=%s",
            (name, phone, user_id),
        )
        db.commit()
        return True
    finally:
        cursor.close()


def update_user_password(user_id, new_password):
    db = get_db()
    cursor = db.cursor()
    try:
        cursor.execute(
            "UPDATE users SET password=%s WHERE id=%s",
            (generate_password_hash(new_password), user_id),
        )
        db.commit()
        return True
    finally:
        cursor.close()


def get_all_enrollments():
    db = get_db()
    cursor = db.cursor(buffered=True)
    try:
        cursor.execute("""
            SELECT c.course_code, c.title, u.name, u.email,
                   e.grade, e.status
            FROM enrollment e
            JOIN course c ON e.course_id = c.id
            JOIN users  u ON e.student_id = u.id
            ORDER BY c.title, u.name
        """)
        return [
            {
                'course_code': r[0], 'course_title': r[1],
                'student_name': r[2], 'student_email': r[3],
                'grade': r[4], 'status': r[5],
            }
            for r in cursor.fetchall()
        ]
    finally:
        cursor.close()


def user_exists(email):
    db = get_db()
    cursor = db.cursor()
    try:
        cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
        return cursor.fetchone() is not None
    finally:
        cursor.close()


def get_user_by_id(user_id):
    db = get_db()
    cursor = db.cursor(buffered=True)
    try:
        cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
        return cursor.fetchone()
    finally:
        cursor.close()


def create_user(name, email, password, role, phone, student_group=None, enrollment_year=None):
    db = get_db()
    cursor = db.cursor()
    try:
        hashed = generate_password_hash(password)
        cursor.execute(
            "INSERT INTO users (name, email, password, role_id, phone) "
            "VALUES (%s, %s, %s, (SELECT id FROM roles WHERE name=%s), %s)",
            (name, email, hashed, role, phone),
        )
        db.commit()
        user_id = cursor.lastrowid
        if role.lower() == 'student':
            cursor.execute(
                "INSERT INTO student (id, name, email, phone, student_group, enrollment_year) "
                "VALUES (%s, %s, %s, %s, %s, %s)",
                (user_id, name, email, phone, student_group, enrollment_year),
            )
            db.commit()
        return True, {'id': user_id, 'name': name, 'email': email}
    finally:
        cursor.close()


def delete_user(user_id):
    db = get_db()
    cursor = db.cursor(buffered=True)
    try:
        cursor.execute("DELETE FROM enrollment WHERE student_id = %s", (user_id,))
        cursor.execute("DELETE FROM waiting_list WHERE student_id = %s", (user_id,))
        cursor.execute("DELETE FROM attendance WHERE student_id = %s", (user_id,))
        cursor.execute("DELETE FROM student WHERE id = %s", (user_id,))
        cursor.execute("DELETE FROM users WHERE id = %s", (user_id,))
        db.commit()
    finally:
        cursor.close()


# ── Teachers ─────────────────────────────────────────────────────────

def get_teachers():
    db = get_db()
    cursor = db.cursor(buffered=True)
    try:
        cursor.execute(
            "SELECT id, name, email FROM users WHERE role_id = 2 ORDER BY name"
        )
        return [{'id': r[0], 'name': r[1], 'email': r[2]} for r in cursor.fetchall()]
    finally:
        cursor.close()


# ── Courses ───────────────────────────────────────────────────────────

def view_courses():
    db = get_db()
    cursor = db.cursor(buffered=True)
    try:
        cursor.execute("""
            SELECT c.id, c.title, c.description, c.start_date, c.end_date,
                   c.location, c.instructor, c.course_code, c.ects_credits,
                   c.category, c.teacher_id, u.name AS teacher_name,
                   c.enrollment_open, c.enrollment_close
            FROM course c
            LEFT JOIN users u ON c.teacher_id = u.id
            ORDER BY c.start_date
        """)
        return [
            {
                'id': r[0], 'title': r[1], 'description': r[2],
                'start_date': r[3], 'end_date': r[4],
                'location': r[5], 'instructor': r[6],
                'course_code': r[7], 'ects_credits': r[8],
                'category': r[9], 'teacher_id': r[10],
                'teacher_name': r[11] or r[6],
                'enrollment_open': r[12], 'enrollment_close': r[13],
            }
            for r in cursor.fetchall()
        ]
    finally:
        cursor.close()


def get_teacher_courses(teacher_id):
    db = get_db()
    cursor = db.cursor(buffered=True)
    try:
        cursor.execute("""
            SELECT c.id, c.title, c.description, c.start_date, c.end_date,
                   c.location, c.instructor, c.course_code, c.ects_credits,
                   c.category, c.teacher_id, u.name AS teacher_name,
                   c.enrollment_open, c.enrollment_close
            FROM course c
            LEFT JOIN users u ON c.teacher_id = u.id
            WHERE c.teacher_id = %s
            ORDER BY c.start_date
        """, (teacher_id,))
        return [
            {
                'id': r[0], 'title': r[1], 'description': r[2],
                'start_date': r[3], 'end_date': r[4],
                'location': r[5], 'instructor': r[6],
                'course_code': r[7], 'ects_credits': r[8],
                'category': r[9], 'teacher_id': r[10],
                'teacher_name': r[11] or r[6],
                'enrollment_open': r[12], 'enrollment_close': r[13],
            }
            for r in cursor.fetchall()
        ]
    finally:
        cursor.close()


def get_course_by_id(course_id):
    db = get_db()
    cursor = db.cursor(buffered=True)
    try:
        cursor.execute("""
            SELECT c.id, c.title, c.description, c.start_date, c.end_date,
                   c.location, c.instructor, c.course_code, c.ects_credits,
                   c.category, c.teacher_id, u.name AS teacher_name,
                   c.enrollment_open, c.enrollment_close
            FROM course c
            LEFT JOIN users u ON c.teacher_id = u.id
            WHERE c.id = %s
        """, (course_id,))
        r = cursor.fetchone()
        if r is None:
            return None
        return {
            'id': r[0], 'title': r[1], 'description': r[2],
            'start_date': r[3], 'end_date': r[4],
            'location': r[5], 'instructor': r[6],
            'course_code': r[7], 'ects_credits': r[8],
            'category': r[9], 'teacher_id': r[10],
            'teacher_name': r[11] or r[6],
            'enrollment_open': r[12], 'enrollment_close': r[13],
        }
    finally:
        cursor.close()


def create_course(title, description, start_date, end_date, location, instructor,
                  spots_available, start_time, end_time,
                  course_code=None, ects_credits=5.0, category=None,
                  teacher_id=None, enrollment_open=None, enrollment_close=None):
    db = get_db()
    cursor = db.cursor(buffered=True)
    try:
        cursor.execute("""
            INSERT INTO course
                (title, description, start_date, end_date, location, instructor,
                 course_code, ects_credits, category, teacher_id,
                 enrollment_open, enrollment_close)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (title, description, start_date, end_date, location, instructor,
              course_code, ects_credits, category, teacher_id or None,
              enrollment_open or None, enrollment_close or None))
        db.commit()
        course_id = cursor.lastrowid
        cursor.execute("""
            INSERT INTO session
                (course_id, start_date, start_time, end_date, end_time, spots_available)
            VALUES (%s,%s,%s,%s,%s,%s)
        """, (course_id, start_date, start_time, end_date, end_time, spots_available))
        db.commit()
    finally:
        cursor.close()


def edit_course(course_id, title=None, description=None, start_date=None, end_date=None,
                location=None, instructor=None, course_code=None, ects_credits=None,
                category=None, teacher_id=None, enrollment_open=None, enrollment_close=None):
    db = get_db()
    cursor = db.cursor(buffered=True)
    try:
        fields, vals = [], []
        pairs = [
            ('title', title), ('description', description),
            ('start_date', start_date), ('end_date', end_date),
            ('location', location), ('instructor', instructor),
            ('course_code', course_code), ('ects_credits', ects_credits),
            ('category', category), ('teacher_id', teacher_id),
            ('enrollment_open', enrollment_open), ('enrollment_close', enrollment_close),
        ]
        for col, val in pairs:
            if val is not None and val != '':
                fields.append(f"{col} = %s")
                vals.append(val)
        if not fields:
            return
        vals.append(course_id)
        cursor.execute(f"UPDATE course SET {', '.join(fields)} WHERE id = %s", tuple(vals))
        db.commit()
    finally:
        cursor.close()


def delete_course(course_id):
    db = get_db()
    cursor = db.cursor(buffered=True)
    try:
        cursor.execute("DELETE FROM waiting_list WHERE course_id = %s", (course_id,))
        cursor.execute("""
            DELETE a FROM attendance a
            JOIN session s ON a.session_id = s.id
            WHERE s.course_id = %s
        """, (course_id,))
        cursor.execute("DELETE FROM enrollment WHERE course_id = %s", (course_id,))
        cursor.execute("DELETE FROM session WHERE course_id = %s", (course_id,))
        cursor.execute("DELETE FROM course WHERE id = %s", (course_id,))
        db.commit()
    finally:
        cursor.close()


# ── Sessions ──────────────────────────────────────────────────────────

def get_sessions():
    db = get_db()
    cursor = db.cursor(buffered=True)
    try:
        cursor.execute("SELECT * FROM session")
        return cursor.fetchall()
    finally:
        cursor.close()


# ── Students ──────────────────────────────────────────────────────────

def get_students():
    db = get_db()
    cursor = db.cursor()
    try:
        cursor.execute("""
            SELECT id, name, email, phone, student_group, enrollment_year
            FROM student
            ORDER BY name
        """)
        rows = cursor.fetchall()
        students = [
            {
                'id': r[0], 'name': r[1], 'email': r[2], 'phone': r[3],
                'student_group': r[4], 'enrollment_year': r[5],
            }
            for r in rows
        ]
        return students, len(students)
    finally:
        cursor.close()


# ── Enrollments ───────────────────────────────────────────────────────

def reserve_spot(course_id, student_id):
    """
    Returns (success, invoice_or_position, email, status)
    status: 'enrolled' | 'waitlisted' | 'already_enrolled' | 'no_session'
    """
    db = get_db()
    cursor = db.cursor(buffered=True)
    try:
        cursor.execute("SELECT * FROM session WHERE course_id = %s", (course_id,))
        sess = cursor.fetchone()
        if sess is None:
            return False, None, None, 'no_session'

        cursor.execute(
            "SELECT id FROM enrollment WHERE course_id=%s AND student_id=%s",
            (course_id, student_id),
        )
        if cursor.fetchone() is not None:
            return False, None, None, 'already_enrolled'

        cursor.execute(
            "SELECT id FROM waiting_list WHERE course_id=%s AND student_id=%s",
            (course_id, student_id),
        )
        if cursor.fetchone() is not None:
            return False, None, None, 'already_enrolled'

        cursor.execute("SELECT email FROM users WHERE id = %s", (student_id,))
        row = cursor.fetchone()
        email = row[0] if row else None

        if sess[6] == 0:
            # No spots — add to waiting list
            cursor.execute(
                "SELECT COALESCE(MAX(position), 0) + 1 FROM waiting_list WHERE course_id = %s",
                (course_id,),
            )
            position = cursor.fetchone()[0]
            cursor.execute(
                "INSERT INTO waiting_list (course_id, student_id, position) VALUES (%s,%s,%s)",
                (course_id, student_id, position),
            )
            db.commit()
            return True, position, email, 'waitlisted'

        invoice_number = random.randint(10000, 99999)
        cursor.execute(
            "INSERT INTO enrollment (course_id, student_id, session_id) VALUES (%s,%s,%s)",
            (course_id, student_id, sess[0]),
        )
        cursor.execute(
            "UPDATE session SET spots_available = spots_available - 1 WHERE id = %s",
            (sess[0],),
        )
        db.commit()
        return True, invoice_number, email, 'enrolled'
    finally:
        cursor.close()


def cancel_reservation(enrollment_id, student_id=None):
    db = get_db()
    cursor = db.cursor(buffered=True)
    try:
        cursor.execute("SELECT * FROM enrollment WHERE id = %s", (enrollment_id,))
        enrollment = cursor.fetchone()
        if enrollment is None:
            return False
        if student_id is not None and str(enrollment[1]) != str(student_id):
            return False

        course_id = enrollment[3]
        session_id = enrollment[2]

        cursor.execute(
            "UPDATE session SET spots_available = spots_available + 1 WHERE id = %s",
            (session_id,),
        )
        cursor.execute("DELETE FROM enrollment WHERE id = %s", (enrollment_id,))
        db.commit()

        # Promote first person on waiting list
        cursor.execute(
            "SELECT student_id FROM waiting_list WHERE course_id = %s ORDER BY position LIMIT 1",
            (course_id,),
        )
        next_student = cursor.fetchone()
        if next_student:
            next_id = next_student[0]
            cursor.execute(
                "INSERT INTO enrollment (course_id, student_id, session_id) VALUES (%s,%s,%s)",
                (course_id, next_id, session_id),
            )
            cursor.execute(
                "UPDATE session SET spots_available = spots_available - 1 WHERE id = %s",
                (session_id,),
            )
            cursor.execute(
                "DELETE FROM waiting_list WHERE course_id = %s AND student_id = %s",
                (course_id, next_id),
            )
            cursor.execute(
                "UPDATE waiting_list SET position = position - 1 WHERE course_id = %s",
                (course_id,),
            )
            db.commit()

        return True
    finally:
        cursor.close()


def get_enrollments(course_id):
    db = get_db()
    cursor = db.cursor(buffered=True)
    try:
        cursor.execute("""
            SELECT e.id, u.name, c.title, e.grade, e.status
            FROM enrollment e
            JOIN users u ON e.student_id = u.id
            JOIN course c ON e.course_id = c.id
            WHERE e.course_id = %s
        """, (course_id,))
        return [
            {
                'id': r[0], 'student_name': r[1], 'course_title': r[2],
                'grade': r[3], 'status': r[4],
            }
            for r in cursor.fetchall()
        ]
    finally:
        cursor.close()


def get_user_enrollments(user_id):
    db = get_db()
    cursor = db.cursor(buffered=True)
    try:
        cursor.execute("""
            SELECT e.id, c.title, s.start_date, s.start_time, e.grade, e.status,
                   c.course_code, c.ects_credits
            FROM enrollment e
            JOIN course c  ON e.course_id  = c.id
            JOIN session s ON e.session_id = s.id
            WHERE e.student_id = %s
        """, (user_id,))
        return [
            {
                'id': r[0], 'course_title': r[1], 'start_date': r[2],
                'start_time': r[3], 'grade': r[4], 'status': r[5],
                'course_code': r[6], 'ects_credits': r[7],
            }
            for r in cursor.fetchall()
        ]
    finally:
        cursor.close()


def get_waiting_list_position(course_id, student_id):
    db = get_db()
    cursor = db.cursor(buffered=True)
    try:
        cursor.execute(
            "SELECT position FROM waiting_list WHERE course_id=%s AND student_id=%s",
            (course_id, student_id),
        )
        row = cursor.fetchone()
        return row[0] if row else None
    finally:
        cursor.close()


def get_waiting_list(course_id):
    db = get_db()
    cursor = db.cursor(buffered=True)
    try:
        cursor.execute("""
            SELECT wl.position, u.name, u.email, wl.joined_at
            FROM waiting_list wl
            JOIN users u ON wl.student_id = u.id
            WHERE wl.course_id = %s
            ORDER BY wl.position
        """, (course_id,))
        return [
            {'position': r[0], 'name': r[1], 'email': r[2], 'joined_at': r[3]}
            for r in cursor.fetchall()
        ]
    finally:
        cursor.close()


# ── Grades ────────────────────────────────────────────────────────────

def set_grade(enrollment_id, grade, teacher_id=None):
    """
    Valid grades: 1-5, HYV (hyväksytty), HYL (hylätty).
    Pass teacher_id to verify the teacher owns the course.
    """
    db = get_db()
    cursor = db.cursor(buffered=True)
    try:
        if teacher_id is not None:
            cursor.execute("""
                SELECT e.id FROM enrollment e
                JOIN course c ON e.course_id = c.id
                WHERE e.id = %s AND c.teacher_id = %s
            """, (enrollment_id, teacher_id))
            if cursor.fetchone() is None:
                return False

        status = 'completed' if grade and grade != 'HYL' else 'active'
        completed_at = datetime.now() if status == 'completed' else None
        cursor.execute(
            "UPDATE enrollment SET grade=%s, status=%s, completed_at=%s WHERE id=%s",
            (grade or None, status, completed_at, enrollment_id),
        )
        db.commit()
        return True
    finally:
        cursor.close()


def get_course_enrollments_with_grades(course_id):
    db = get_db()
    cursor = db.cursor(buffered=True)
    try:
        cursor.execute("""
            SELECT e.id, u.name, u.email, e.grade, e.status, e.completed_at
            FROM enrollment e
            JOIN users u ON e.student_id = u.id
            WHERE e.course_id = %s
            ORDER BY u.name
        """, (course_id,))
        return [
            {
                'enrollment_id': r[0], 'student_name': r[1], 'student_email': r[2],
                'grade': r[3], 'status': r[4], 'completed_at': r[5],
            }
            for r in cursor.fetchall()
        ]
    finally:
        cursor.close()


def get_student_transcript(user_id):
    db = get_db()
    cursor = db.cursor(buffered=True)
    try:
        cursor.execute("""
            SELECT c.course_code, c.title, c.ects_credits, c.category,
                   e.grade, e.status, e.completed_at, c.start_date, c.end_date
            FROM enrollment e
            JOIN course c ON e.course_id = c.id
            WHERE e.student_id = %s
            ORDER BY c.start_date DESC
        """, (user_id,))
        rows = cursor.fetchall()
        transcript = [
            {
                'course_code': r[0], 'title': r[1], 'ects_credits': r[2],
                'category': r[3], 'grade': r[4], 'status': r[5],
                'completed_at': r[6], 'start_date': r[7], 'end_date': r[8],
            }
            for r in rows
        ]
        earned_ects = sum(
            float(t['ects_credits'] or 0)
            for t in transcript
            if t['status'] == 'completed' and t['grade'] not in (None, 'HYL')
        )
        return transcript, earned_ects
    finally:
        cursor.close()


# ── Attendance ────────────────────────────────────────────────────────

def get_session_attendance(session_id):
    """Returns all enrolled students with their attendance status for a session."""
    db = get_db()
    cursor = db.cursor(buffered=True)
    try:
        cursor.execute("""
            SELECT u.id, u.name, COALESCE(a.present, FALSE) AS present
            FROM enrollment e
            JOIN users u ON e.student_id = u.id
            LEFT JOIN attendance a
                ON a.session_id = %s AND a.student_id = u.id
            WHERE e.session_id = %s
            ORDER BY u.name
        """, (session_id, session_id))
        return [
            {'student_id': r[0], 'student_name': r[1], 'present': bool(r[2])}
            for r in cursor.fetchall()
        ]
    finally:
        cursor.close()


def mark_attendance(session_id, attendance_data):
    """
    attendance_data: list of (student_id, present_bool)
    Uses INSERT ... ON DUPLICATE KEY UPDATE to upsert.
    """
    db = get_db()
    cursor = db.cursor(buffered=True)
    try:
        for student_id, present in attendance_data:
            cursor.execute("""
                INSERT INTO attendance (session_id, student_id, present)
                VALUES (%s, %s, %s)
                ON DUPLICATE KEY UPDATE present = VALUES(present), marked_at = NOW()
            """, (session_id, student_id, present))
        db.commit()
    finally:
        cursor.close()


# ── Stats ─────────────────────────────────────────────────────────────

def get_stats():
    db = get_db()
    cursor = db.cursor(buffered=True)
    try:
        cursor.execute("SELECT COUNT(*) FROM course")
        total_courses = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM student")
        total_students = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM enrollment WHERE status = 'active'")
        total_enrollments = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM session WHERE spots_available > 0")
        open_sessions = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM waiting_list")
        total_waiting = cursor.fetchone()[0]
        return {
            'total_courses': total_courses,
            'total_students': total_students,
            'total_enrollments': total_enrollments,
            'open_sessions': open_sessions,
            'total_waiting': total_waiting,
        }
    finally:
        cursor.close()


def get_student_stats(user_id):
    db = get_db()
    cursor = db.cursor(buffered=True)
    try:
        cursor.execute(
            "SELECT COUNT(*) FROM enrollment WHERE student_id = %s AND status = 'active'",
            (user_id,),
        )
        my_enrollments = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM course")
        total_courses = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM session WHERE spots_available > 0")
        open_sessions = cursor.fetchone()[0]
        cursor.execute(
            "SELECT COALESCE(SUM(c.ects_credits), 0) "
            "FROM enrollment e JOIN course c ON e.course_id = c.id "
            "WHERE e.student_id = %s AND e.status = 'completed' AND e.grade != 'HYL'",
            (user_id,),
        )
        earned_ects = float(cursor.fetchone()[0] or 0)
        cursor.execute(
            "SELECT COUNT(*) FROM waiting_list WHERE student_id = %s", (user_id,)
        )
        on_waitlist = cursor.fetchone()[0]
        return {
            'my_enrollments': my_enrollments,
            'total_courses': total_courses,
            'open_sessions': open_sessions,
            'earned_ects': earned_ects,
            'on_waitlist': on_waitlist,
        }
    finally:
        cursor.close()
