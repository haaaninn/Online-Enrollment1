import pytest

from app import app
from models import db, User, Course


@pytest.fixture()
def client(tmp_path):
    database = tmp_path / "test.sqlite"
    app.config.update(
        TESTING=True,
        SECRET_KEY="test-secret-key",
        WTF_CSRF_ENABLED=False,
        SQLALCHEMY_DATABASE_URI=f"sqlite:///{database}",
    )
    with app.app_context():
        # app.py initializes the default database on import; discard that engine
        # so this test fixture uses a temporary database instead.
        db.session.remove()
        db.engines[app].dispose()
        db.engines.pop(app, None)
        db.create_all()
        admin = User(name="Test Admin", email="admin@test.local", role="admin")
        admin.set_password("StrongAdmin123")
        db.session.add(admin)
        db.session.add(Course(code="TEST1", title="Test Course", fee=10, slots=5))
        db.session.commit()
    with app.test_client() as test_client:
        yield test_client
    with app.app_context():
        db.session.remove()
        db.drop_all()
        db.engines[app].dispose()
        db.engines.pop(app, None)


def test_public_pages_load(client):
    assert client.get("/").status_code == 200
    assert client.get("/courses").status_code == 200


def test_register_and_password_is_hashed(client):
    response = client.post("/register", data={
        "name": "Sample Student",
        "email": "student@example.com",
        "password": "StrongPass123",
        "confirm": "StrongPass123",
    }, follow_redirects=True)
    assert response.status_code == 200
    with app.app_context():
        user = User.query.filter_by(email="student@example.com").first()
        assert user is not None
        assert user.password_hash != "StrongPass123"
        assert user.check_password("StrongPass123")


def test_admin_page_requires_admin(client):
    response = client.get("/admin/courses")
    assert response.status_code in (302, 401)
