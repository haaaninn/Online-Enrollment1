import os
import re
from datetime import datetime

from dotenv import load_dotenv
from flask import (
    Flask, render_template, redirect, url_for, flash, request, abort
)
from flask_login import (
    LoginManager, login_user, logout_user, login_required, current_user
)
from flask_wtf import FlaskForm
from flask_wtf.csrf import CSRFProtect
from wtforms import (
    StringField, PasswordField, SelectField, TextAreaField, BooleanField, FloatField, IntegerField
)
from wtforms.validators import (
    DataRequired, Email, Length, EqualTo, Optional, NumberRange, ValidationError
)

from models import db, User, Course, Enrollment

load_dotenv()

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY") or "local-development-only-change-this-secret"
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", "sqlite:///enrollment.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db.init_app(app)
CSRFProtect(app)

login_manager = LoginManager(app)
login_manager.login_view = "login"
login_manager.login_message = "Please sign in to continue."
login_manager.login_message_category = "warning"


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


# --------------------------------------------------------------------------
# Forms
# --------------------------------------------------------------------------

class RegisterForm(FlaskForm):
    name = StringField("Full name", validators=[DataRequired(), Length(min=2, max=120)])
    email = StringField("Email address", validators=[DataRequired(), Email(), Length(max=255)])
    password = PasswordField("Password", validators=[DataRequired(), Length(min=8, message="Use at least 8 characters.")])
    confirm = PasswordField("Confirm password", validators=[DataRequired(), EqualTo("password", message="Passwords do not match.")])

    def validate_email(self, field):
        if User.query.filter_by(email=field.data.lower().strip()).first():
            raise ValidationError("That email is already registered.")


class LoginForm(FlaskForm):
    email = StringField("Email address", validators=[DataRequired(), Email()])
    password = PasswordField("Password", validators=[DataRequired()])


class CourseForm(FlaskForm):
    code = StringField("Course code", validators=[DataRequired(), Length(max=20)])
    title = StringField("Title", validators=[DataRequired(), Length(max=150)])
    description = TextAreaField("Description", validators=[Optional(), Length(max=2000)])
    fee = FloatField("Fee (PHP)", validators=[DataRequired(), NumberRange(min=0, message="Fee cannot be negative.")])
    slots = IntegerField("Slots", validators=[DataRequired(), NumberRange(min=1, message="At least 1 slot.")])
    is_open = BooleanField("Accepting enrollments", default=True)


class EnrollmentForm(FlaskForm):
    student_name = StringField("Student name", validators=[DataRequired(), Length(min=2, max=120)])
    student_email = StringField("Email address", validators=[DataRequired(), Email(), Length(max=255)])
    contact_no = StringField("Contact number", validators=[DataRequired(), Length(min=7, max=30)])
    schedule = SelectField("Preferred schedule", choices=[
        ("Weekday 8:00-10:00 AM", "Weekday 8:00-10:00 AM"),
        ("Weekday 1:00-3:00 PM", "Weekday 1:00-3:00 PM"),
        ("Saturday 9:00 AM-12:00 NN", "Saturday 9:00 AM-12:00 NN"),
    ])
    payment_mode = SelectField("Payment mode", choices=[
        ("full", "Full payment"),
        ("installment", "Two installments"),
    ])
    notes = TextAreaField("Notes", validators=[Optional(), Length(max=500)])

    def validate_contact_no(self, field):
        if not re.fullmatch(r"[\d\s\-\+\(\)]{7,30}", field.data.strip()):
            raise ValidationError("Enter a valid contact number (digits, spaces, + - only).")


# --------------------------------------------------------------------------
# Public routes
# --------------------------------------------------------------------------

@app.route("/")
def landing():
    courses = Course.query.filter_by(is_open=True).order_by(Course.code).limit(6).all()
    return render_template("landing.html", courses=courses)


@app.route("/courses")
def courses():
    return render_template("courses.html", courses=Course.query.order_by(Course.code).all())


# --------------------------------------------------------------------------
# Auth routes
# --------------------------------------------------------------------------

@app.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))

    form = RegisterForm()
    if form.validate_on_submit():
        user = User(
            name=form.name.data.strip(),
            email=form.email.data.lower().strip(),
            role="student",
        )
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        flash("Account created. You can sign in now.", "success")
        return redirect(url_for("login"))
    return render_template("register.html", form=form)


@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))

    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data.lower().strip()).first()
        if user and user.check_password(form.password.data):
            login_user(user)
            flash(f"Welcome back, {user.name}.", "success")
            nxt = request.args.get("next")
            if nxt and nxt.startswith("/"):
                return redirect(nxt)
            return redirect(url_for("dashboard"))
        flash("Incorrect email or password.", "danger")
    return render_template("login.html", form=form)


@app.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    flash("You have been signed out.", "success")
    return redirect(url_for("landing"))


# --------------------------------------------------------------------------
# Dashboard
# --------------------------------------------------------------------------

@app.route("/dashboard")
@login_required
def dashboard():
    if current_user.is_admin:
        enrollments = Enrollment.query.order_by(Enrollment.created_at.desc()).all()
    else:
        enrollments = Enrollment.query.filter_by(user_id=current_user.id).order_by(Enrollment.created_at.desc()).all()
    return render_template(
        "dashboard.html",
        enrollments=enrollments,
        course_count=Course.query.count(),
        user_count=User.query.count() if current_user.is_admin else None,
    )


# --------------------------------------------------------------------------
# CRUD: Enrollments
# --------------------------------------------------------------------------

def _owns(record: Enrollment) -> bool:
    return current_user.is_admin or record.user_id == current_user.id


@app.route("/enroll/<int:course_id>", methods=["GET", "POST"])
@login_required
def enroll(course_id):
    course = db.session.get(Course, course_id) or abort(404)
    if not course.is_open or course.slots_left <= 0:
        flash("That course is not accepting enrollments right now.", "warning")
        return redirect(url_for("courses"))

    form = EnrollmentForm()
    if request.method == "GET":
        form.student_name.data = current_user.name
        form.student_email.data = current_user.email

    if form.validate_on_submit():
        record = Enrollment(
            reference_no=Enrollment.make_reference(),
            user_id=current_user.id,
            course_id=course.id,
            student_name=form.student_name.data.strip(),
            student_email=form.student_email.data.lower().strip(),
            contact_no=form.contact_no.data.strip(),
            schedule=form.schedule.data,
            payment_mode=form.payment_mode.data,
            notes=(form.notes.data or "").strip(),
            status="pending",
        )
        db.session.add(record)
        db.session.commit()
        flash(f"Enrollment submitted. Your reference number is {record.reference_no}.", "success")
        return redirect(url_for("dashboard"))
    return render_template("enroll.html", form=form, course=course)


@app.route("/enrollments/<int:enrollment_id>/edit", methods=["GET", "POST"])
@login_required
def edit_enrollment(enrollment_id):
    record = db.session.get(Enrollment, enrollment_id) or abort(404)
    if not _owns(record):
        abort(403)

    form = EnrollmentForm(obj=record)
    if form.validate_on_submit():
        form.populate_obj(record)  # writes validated values back onto the row
        record.student_email = record.student_email.lower().strip()
        if current_user.is_admin:
            new_status = request.form.get("status")
            if new_status in {"pending", "confirmed", "cancelled"}:
                record.status = new_status
        db.session.commit()
        flash("Enrollment updated.", "success")
        return redirect(url_for("dashboard"))
    return render_template("edit_enrollment.html", form=form, record=record)


@app.route("/enrollments/<int:enrollment_id>/delete", methods=["POST"])
@login_required
def delete_enrollment(enrollment_id):
    record = db.session.get(Enrollment, enrollment_id) or abort(404)
    if not _owns(record):
        abort(403)
    db.session.delete(record)
    db.session.commit()
    flash(f"Enrollment {record.reference_no} deleted.", "success")
    return redirect(url_for("dashboard"))


# --------------------------------------------------------------------------
# Admin: courses (second entity, managed by admins only)
# --------------------------------------------------------------------------

@app.route("/admin/courses", methods=["GET", "POST"])
@login_required
def admin_courses():
    if not current_user.is_admin:
        abort(403)
    form = CourseForm()
    if form.validate_on_submit():
        if Course.query.filter_by(code=form.code.data.strip().upper()).first():
            flash("That course code already exists.", "danger")
        else:
            db.session.add(Course(
                code=form.code.data.strip().upper(),
                title=form.title.data.strip(),
                description=(form.description.data or "").strip(),
                fee=form.fee.data,
                slots=form.slots.data,
                is_open=form.is_open.data,
            ))
            db.session.commit()
            flash("Course added.", "success")
            return redirect(url_for("admin_courses"))
    return render_template("admin_courses.html", form=form, courses=Course.query.order_by(Course.code).all())


@app.route("/admin/courses/<int:course_id>/delete", methods=["POST"])
@login_required
def delete_course(course_id):
    if not current_user.is_admin:
        abort(403)
    course = db.session.get(Course, course_id) or abort(404)
    if course.enrollments:
        flash("Cannot delete a course that already has enrollments.", "danger")
    else:
        db.session.delete(course)
        db.session.commit()
        flash("Course deleted.", "success")
    return redirect(url_for("admin_courses"))


# --------------------------------------------------------------------------
# First-run setup: tables + a default admin + starter courses
# --------------------------------------------------------------------------

def bootstrap():
    db.create_all()

    admin_password = os.environ.get("ADMIN_PASSWORD")
    if admin_password and not User.query.filter_by(email="admin@enroll.local").first():
        admin = User(name="System Admin", email="admin@enroll.local", role="admin")
        admin.set_password(admin_password)
        db.session.add(admin)

    if Course.query.count() == 0:
        db.session.add_all([
            Course(code="IT101", title="Computer Basics", fee=2500, slots=25,
                   description="Hardware, operating systems, and file management."),
            Course(code="ENG201", title="Business English", fee=3200, slots=20,
                   description="Workplace writing and conversation practice."),
            Course(code="TLE301", title="Bread & Pastry Production", fee=4500, slots=15,
                   description="Hands-on baking with TESDA-aligned modules."),
        ])

    db.session.commit()


# Initialize tables and starter courses for both local runs and WSGI hosts (e.g. Render).
# Set ADMIN_PASSWORD in the environment to create the initial administrator safely.
with app.app_context():
    bootstrap()

if __name__ == "__main__":
    app.run(debug=os.environ.get("FLASK_DEBUG") == "1")
