import csv
import io
import flask.helpers
# Flask-Babel 3.x uses locked_cached_property which Flask 3.x removed — shim it
if not hasattr(flask.helpers, 'locked_cached_property'):
    from functools import cached_property
    flask.helpers.locked_cached_property = cached_property
from flask import Flask, render_template, redirect, url_for, flash, request, session, Response
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask_babel import Babel, gettext as _
from course_management import (
    User, login, create_user, view_courses, create_course, edit_course,
    reserve_spot, cancel_reservation, get_enrollments, delete_course,
    delete_user, get_user_by_id, get_sessions, get_students, user_exists,
    get_course_by_id, get_user_enrollments, get_stats, get_student_stats,
    get_teachers, get_teacher_courses, get_waiting_list, get_waiting_list_position,
    set_grade, get_course_enrollments_with_grades, get_student_transcript,
    get_session_attendance, mark_attendance,
    verify_password, update_user_profile, update_user_password, get_all_enrollments,
)
from functools import wraps
from urllib.parse import urlparse, urljoin
from dotenv import load_dotenv
from email_service import EmailService
from datetime import datetime
import os

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET')

# ── i18n ─────────────────────────────────────────────────────────────

def get_locale():
    try:
        return session.get('lang', 'fi')
    except RuntimeError:
        return 'fi'

babel = Babel(app, locale_selector=get_locale)

# ── Auth / Mail ───────────────────────────────────────────────────────

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login_page"  # type: ignore

app.config['MAIL_SERVER'] = 'smtp.elasticemail.com'
app.config['MAIL_PORT'] = 2525
app.config['MAIL_USE_TLS'] = False
app.config['MAIL_USERNAME'] = os.getenv('EMAIL_USER')
app.config['MAIL_PASSWORD'] = os.getenv('EMAIL_PASSWORD')

email_service = EmailService(app)
EMAIL_SENDER = os.getenv('EMAIL_SENDER', os.getenv('EMAIL_USER', ''))


# ── Decorators ────────────────────────────────────────────────────────

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:  # type: ignore
            flash(_('You do not have permission to access this page.'), 'danger')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated


def admin_or_teacher_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or not (current_user.is_admin or current_user.is_teacher):  # type: ignore
            flash(_('You do not have permission to access this page.'), 'danger')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated


@login_manager.user_loader
def load_user(user_id):
    user_data = get_user_by_id(user_id)
    if user_data is not None:
        return User(user_data[0], user_data[1], user_data[2], user_data[4])
    return None


def is_safe_url(target):
    ref_url = urlparse(request.host_url)
    test_url = urlparse(urljoin(request.host_url, target))
    return test_url.scheme in ('http', 'https') and ref_url.netloc == test_url.netloc


# ── Language switcher ─────────────────────────────────────────────────

@app.route('/set_lang/<lang>')
def set_lang(lang):
    if lang in ('fi', 'en'):
        session['lang'] = lang
    return redirect(request.referrer or url_for('dashboard'))


# ── Auth ──────────────────────────────────────────────────────────────

@app.route("/", methods=["GET", "POST"])
def login_page():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        success, user_data = login(username, password)
        if success:
            login_user(user_data)
            session['user_id'] = user_data.id
            flash(_('You are now logged in.'), 'success')
            next_url = request.args.get("next")
            if next_url and is_safe_url(next_url):
                return redirect(next_url)
            return redirect(url_for("dashboard"))
        flash(_('Login failed. Check your username and password.'), 'danger')
    return render_template("login.html")


@app.route('/logout')
@login_required
def logout():
    logout_user()
    session.pop('user_id', None)
    flash(_('You have been logged out.'), 'success')
    return redirect(url_for('login_page'))


# ── Profile ───────────────────────────────────────────────────────────

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    user_data = get_user_by_id(current_user.id)  # type: ignore
    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'update_info':
            name = request.form.get('name', '').strip()
            phone = request.form.get('phone', '').strip()
            if name:
                update_user_profile(current_user.id, name, phone)  # type: ignore
                flash(_('Profile updated successfully.'), 'success')
            return redirect(url_for('profile'))

        if action == 'change_password':
            current_pw = request.form.get('current_password', '')
            new_pw = request.form.get('new_password', '')
            confirm_pw = request.form.get('confirm_password', '')
            if not verify_password(current_user.id, current_pw):  # type: ignore
                flash(_('Current password is incorrect.'), 'danger')
            elif new_pw != confirm_pw:
                flash(_('Passwords do not match.'), 'danger')
            elif len(new_pw) < 6:
                flash('Salasanan täytyy olla vähintään 6 merkkiä.', 'danger')
            else:
                update_user_password(current_user.id, new_pw)  # type: ignore
                flash(_('Profile updated successfully.'), 'success')
            return redirect(url_for('profile'))

    return render_template('profile.html', user_data=user_data)


# ── Dashboard ─────────────────────────────────────────────────────────

@app.route('/dashboard')
@login_required
def dashboard():
    if current_user.is_admin or current_user.is_teacher:  # type: ignore
        stats = get_stats()
    else:
        stats = get_student_stats(current_user.id)  # type: ignore
    return render_template('dashboard.html', user_name=current_user.name, stats=stats)  # type: ignore


# ── Courses ───────────────────────────────────────────────────────────

@app.route('/courses')
@login_required
def courses():
    if current_user.is_teacher and not current_user.is_admin:  # type: ignore
        courses_list = get_teacher_courses(current_user.id)  # type: ignore
    else:
        courses_list = view_courses()
    return render_template('courses.html', courses=courses_list)


@app.route('/create_course', methods=['GET', 'POST'])
@login_required
@admin_required
def create_course_page():
    teachers = get_teachers()
    if request.method == 'POST':
        create_course(
            title=request.form['course_name'],
            description=request.form['course_description'],
            start_date=request.form['start_date'],
            end_date=request.form['end_date'],
            location=request.form['location'],
            instructor=request.form.get('instructor', ''),
            spots_available=request.form['spots_available'],
            start_time=request.form['start_time'],
            end_time=request.form['end_time'],
            course_code=request.form.get('course_code') or None,
            ects_credits=request.form.get('ects_credits') or 5.0,
            category=request.form.get('category') or None,
            teacher_id=request.form.get('teacher_id') or None,
            enrollment_open=request.form.get('enrollment_open') or None,
            enrollment_close=request.form.get('enrollment_close') or None,
        )
        flash(_('Course created successfully.'), 'success')
        return redirect(url_for('courses'))
    return render_template('create_course.html', teachers=teachers)


@app.route('/course/edit/<int:course_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_course_page(course_id):
    course = get_course_by_id(course_id)
    if course is None:
        flash('Kurssia ei löydy.', 'danger')
        return redirect(url_for('courses'))
    teachers = get_teachers()
    if request.method == 'POST':
        edit_course(
            course_id,
            title=request.form['course_name'],
            description=request.form['course_description'],
            start_date=request.form['start_date'],
            end_date=request.form['end_date'],
            location=request.form['location'],
            instructor=request.form.get('instructor', ''),
            course_code=request.form.get('course_code') or None,
            ects_credits=request.form.get('ects_credits') or None,
            category=request.form.get('category') or None,
            teacher_id=request.form.get('teacher_id') or None,
            enrollment_open=request.form.get('enrollment_open') or None,
            enrollment_close=request.form.get('enrollment_close') or None,
        )
        flash(_('Course updated successfully.'), 'success')
        return redirect(url_for('courses'))
    return render_template('edit_course.html', course=course, teachers=teachers)


@app.route('/delete_course', methods=['GET', 'POST'])
@login_required
@admin_required
def delete_course_page():
    courses_list = view_courses()
    if request.method == 'POST':
        course_id = request.form['course_id']
        delete_course(course_id)
        flash(_('Course deleted.'), 'success')
        return redirect(url_for('delete_course_page'))
    return render_template('delete_course.html', courses=courses_list)


# ── Enrollments ───────────────────────────────────────────────────────

@app.route('/reserve_spot', methods=['GET', 'POST'])
@login_required
def reserve_spot_page():
    if request.method == 'POST':
        course_id = request.form['course_id']
        student_id = session.get('user_id')
        success, value, student_email, status = reserve_spot(course_id, student_id)

        if status == 'enrolled':
            course = get_course_by_id(course_id)
            course_title = course['title'] if course else 'Unknown'
            flash(_('Spot reserved successfully!'), 'success')
            sessions_data = get_sessions()
            session_data = next((s for s in sessions_data if s[1] == int(course_id)), None)
            if session_data and student_email and EMAIL_SENDER:
                try:
                    start_dt = datetime.strptime(
                        session_data[2].strftime('%Y-%m-%d') + ' ' + str(session_data[3]),
                        '%Y-%m-%d %H:%M:%S',
                    )
                    end_dt = datetime.strptime(
                        session_data[4].strftime('%Y-%m-%d') + ' ' + str(session_data[5]),
                        '%Y-%m-%d %H:%M:%S',
                    )
                    body = render_template(
                        'reservation_confirmation.html',
                        course_title=course_title,
                        start_date_time=start_dt,
                        end_date_time=end_dt,
                        invoice_number=value,
                    )
                    email_service.send_email(EMAIL_SENDER, [student_email], 'Vahvistus kurssivarauksesta', body)
                except Exception:
                    pass
        elif status == 'waitlisted':
            flash(f'Kurssi on täynnä. Sinut on lisätty jonotuslistalle sijalle {value}.', 'warning')
        elif status == 'already_enrolled':
            flash('Olet jo ilmoittautunut tälle kurssille tai jonotuslistalla.', 'danger')
        else:
            flash('Varaus epäonnistui. Kurssia ei löydy.', 'danger')

        return redirect(url_for('reserve_spot_page'))

    courses_list = view_courses()
    student_id = session.get('user_id')
    for c in courses_list:
        c['waiting_position'] = get_waiting_list_position(c['id'], student_id)
    return render_template('reserve_spot.html', courses=courses_list)


@app.route('/cancel_reservation', methods=['GET', 'POST'])
@login_required
def cancel_reservation_page():
    student_id = session.get('user_id')
    if request.method == 'POST':
        enrollment_id = request.form['enrollment_id']
        if cancel_reservation(enrollment_id, student_id):
            flash(_('Reservation cancelled.'), 'success')
        else:
            flash('Varausta ei löydy tai sinulla ei ole oikeutta peruuttaa sitä.', 'danger')
        return redirect(url_for('cancel_reservation_page'))
    enrollments = get_user_enrollments(student_id)
    return render_template('cancel_reservation.html', enrollments=enrollments)


@app.route('/get_enrollments', methods=['GET', 'POST'])
@login_required
@admin_or_teacher_required
def get_enrollments_page():
    if current_user.is_teacher and not current_user.is_admin:  # type: ignore
        courses_list = get_teacher_courses(current_user.id)  # type: ignore
    else:
        courses_list = view_courses()
    enrollments_list = []
    selected_course_id = None
    if request.method == 'POST':
        selected_course_id = request.form['course_id']
        enrollments_list = get_enrollments(selected_course_id)
    return render_template(
        'get_enrollments.html',
        courses=courses_list,
        enrollments=enrollments_list,
        selected_course_id=selected_course_id,
    )


# ── Grades ────────────────────────────────────────────────────────────

@app.route('/course/<int:course_id>/grades', methods=['GET', 'POST'])
@login_required
@admin_or_teacher_required
def course_grades(course_id):
    course = get_course_by_id(course_id)
    if course is None:
        flash('Kurssia ei löydy.', 'danger')
        return redirect(url_for('courses'))
    if current_user.is_teacher and not current_user.is_admin:  # type: ignore
        if course['teacher_id'] != current_user.id:  # type: ignore
            flash('Sinulla ei ole oikeutta arvostella tätä kurssia.', 'danger')
            return redirect(url_for('courses'))
    if request.method == 'POST':
        for key, value in request.form.items():
            if key.startswith('grade_'):
                enrollment_id = key.split('_', 1)[1]
                set_grade(enrollment_id, value or None)
        flash(_('Grades saved.'), 'success')
        return redirect(url_for('course_grades', course_id=course_id))
    enrollments = get_course_enrollments_with_grades(course_id)
    return render_template('course_grades.html', course=course, enrollments=enrollments)


# ── Attendance ────────────────────────────────────────────────────────

@app.route('/course/<int:course_id>/attendance', methods=['GET', 'POST'])
@login_required
@admin_or_teacher_required
def course_attendance(course_id):
    course = get_course_by_id(course_id)
    if course is None:
        flash('Kurssia ei löydy.', 'danger')
        return redirect(url_for('courses'))
    if current_user.is_teacher and not current_user.is_admin:  # type: ignore
        if course['teacher_id'] != current_user.id:  # type: ignore
            flash('Sinulla ei ole oikeutta merkitä läsnäoloja tälle kurssille.', 'danger')
            return redirect(url_for('courses'))

    sessions_data = get_sessions()
    course_session = next((s for s in sessions_data if s[1] == course_id), None)
    if course_session is None:
        flash('Kurssille ei löydy sessiota.', 'danger')
        return redirect(url_for('courses'))

    session_id = course_session[0]

    if request.method == 'POST':
        attendance_data = []
        for key in request.form:
            if key.startswith('present_'):
                student_id = int(key.split('_', 1)[1])
                attendance_data.append((student_id, True))
        all_students = get_session_attendance(session_id)
        submitted_ids = {sid for sid, _ in attendance_data}
        for s in all_students:
            if s['student_id'] not in submitted_ids:
                attendance_data.append((s['student_id'], False))
        mark_attendance(session_id, attendance_data)
        flash(_('Attendance saved.'), 'success')
        return redirect(url_for('course_attendance', course_id=course_id))

    students = get_session_attendance(session_id)
    return render_template('course_attendance.html', course=course, students=students)


# ── Transcript ────────────────────────────────────────────────────────

@app.route('/my_transcript')
@login_required
def my_transcript():
    transcript, earned_ects = get_student_transcript(current_user.id)  # type: ignore
    return render_template('transcript.html', transcript=transcript, earned_ects=earned_ects)


# ── Sessions ──────────────────────────────────────────────────────────

@app.route('/view_sessions')
@login_required
def view_sessions_page():
    sessions = get_sessions()
    courses_list = view_courses()
    course_map = {c['id']: c['title'] for c in courses_list}
    return render_template('view_sessions.html', sessions=sessions, course_map=course_map)


# ── Students ──────────────────────────────────────────────────────────

@app.route('/add_student', methods=['GET', 'POST'])
@login_required
@admin_or_teacher_required
def add_student():
    if request.method == 'POST':
        student_name = request.form['student_name']
        student_email = request.form['student_email']
        student_password = request.form['student_password']
        student_phone = request.form.get('student_phone') or ''
        student_group = request.form.get('student_group') or None
        enrollment_year = request.form.get('enrollment_year') or None
        if user_exists(student_email):
            flash('Tällä sähköpostiosoitteella on jo käyttäjä.', 'danger')
            return redirect(url_for('add_student'))
        create_user(student_name, student_email, student_password, 'student',
                    student_phone, student_group, enrollment_year)
        flash('Opiskelija lisätty onnistuneesti.', 'success')
        return redirect(url_for('add_student'))
    return render_template('add_student.html')


@app.route('/students_list', methods=['GET'])
@login_required
@admin_or_teacher_required
def students_list():
    students, students_count = get_students()
    return render_template('students_list.html', students=students, students_count=students_count)


@app.route("/create_user", methods=["GET", "POST"])
@login_required
@admin_required
def create_user_page():
    if request.method == "POST":
        name = request.form["name"]
        email = request.form["email"]
        password = request.form["password"]
        confirm_password = request.form["confirm_password"]
        role = request.form["role"]
        phone = request.form.get("phone") or ''
        student_group = request.form.get("student_group") or None
        enrollment_year = request.form.get("enrollment_year") or None

        if password != confirm_password:
            flash(_('Passwords do not match.'), "danger")
            return redirect(request.url)
        if user_exists(email):
            flash("Tällä sähköpostiosoitteella on jo käyttäjä.", "danger")
            return redirect(request.url)

        success, _ = create_user(name, email, password, role, phone, student_group, enrollment_year)
        if success:
            flash(f"Käyttäjä '{name}' luotu onnistuneesti.", "success")
            return redirect(url_for("dashboard"))
        flash("Käyttäjän luonti epäonnistui.", "danger")
        return redirect(request.url)

    return render_template("create_user.html")


# ── CSV Exports ───────────────────────────────────────────────────────

@app.route('/export/students.csv')
@login_required
@admin_required
def export_students_csv():
    students, _ = get_students()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['ID', 'Nimi', 'Sähköposti', 'Puhelin', 'Ryhmä', 'Aloitusvuosi'])
    for s in students:
        writer.writerow([
            s['id'], s['name'], s['email'],
            s['phone'] or '', s['student_group'] or '', s['enrollment_year'] or '',
        ])
    return Response(
        '﻿' + output.getvalue(),  # BOM for Excel UTF-8 compatibility
        mimetype='text/csv; charset=utf-8',
        headers={'Content-Disposition': 'attachment; filename=opiskelijat.csv'},
    )


@app.route('/export/enrollments.csv')
@login_required
@admin_required
def export_enrollments_csv():
    rows = get_all_enrollments()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Kurssikoodi', 'Kurssi', 'Opiskelija', 'Sähköposti', 'Arvosana', 'Tila'])
    for r in rows:
        writer.writerow([
            r['course_code'] or '', r['course_title'],
            r['student_name'], r['student_email'],
            r['grade'] or '', r['status'] or '',
        ])
    return Response(
        '﻿' + output.getvalue(),
        mimetype='text/csv; charset=utf-8',
        headers={'Content-Disposition': 'attachment; filename=ilmoittautumiset.csv'},
    )


# ── Error handlers ────────────────────────────────────────────────────

@app.errorhandler(404)
def not_found(e):
    return render_template('404.html'), 404


@app.errorhandler(500)
def server_error(e):
    return render_template('500.html'), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True)
