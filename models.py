from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()


class User(UserMixin, db.Model):
    """A person who can log in. Admins manage courses and all enrollments;
    students only ever see their own enrollment records."""
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="student")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    enrollments = db.relationship(
        "Enrollment", backref="student", cascade="all, delete-orphan"
    )

    def set_password(self, raw_password: str) -> None:
        # werkzeug hashes with a salted, slow algorithm — never store the raw text.
        self.password_hash = generate_password_hash(raw_password)

    def check_password(self, raw_password: str) -> bool:
        return check_password_hash(self.password_hash, raw_password)

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"


class Course(db.Model):
    __tablename__ = "courses"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(20), unique=True, nullable=False)
    title = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text, default="")
    fee = db.Column(db.Float, nullable=False, default=0.0)
    slots = db.Column(db.Integer, nullable=False, default=20)
    is_open = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    enrollments = db.relationship("Enrollment", backref="course")

    @property
    def slots_taken(self) -> int:
        return sum(1 for e in self.enrollments if e.status != "cancelled")

    @property
    def slots_left(self) -> int:
        return max(self.slots - self.slots_taken, 0)


class Enrollment(db.Model):
    """The core CRUD entity: one student enrolled in one course offering."""
    __tablename__ = "enrollments"

    id = db.Column(db.Integer, primary_key=True)
    reference_no = db.Column(db.String(20), unique=True, nullable=False)

    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey("courses.id"), nullable=False)

    student_name = db.Column(db.String(120), nullable=False)
    student_email = db.Column(db.String(255), nullable=False)
    contact_no = db.Column(db.String(30), nullable=False)
    schedule = db.Column(db.String(80), nullable=False)
    payment_mode = db.Column(db.String(30), nullable=False, default="full")
    notes = db.Column(db.Text, default="")
    status = db.Column(db.String(20), nullable=False, default="pending")

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @staticmethod
    def make_reference():
        year = datetime.utcnow().year
        seq = Enrollment.query.count() + 1
        return f"ENR-{year}-{seq:04d}"
