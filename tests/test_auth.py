import unittest

from app import create_app
from app.extensions import db
from app.models import Language, LoginAttempt, User, UserLanguageAssignment


class TestConfig:
    TESTING = True
    SECRET_KEY = "test-secret"
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    WTF_CSRF_ENABLED = False
    UPLOAD_FOLDER = "instance/test_uploads"
    EXPORT_FOLDER = "instance/test_exports"


class AuthTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestConfig)
        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def create_user(self, username, email, role, password="password123"):
        user = User(username=username, email=email, role=role, is_active=True)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        return user

    def test_password_hashing(self):
        user = User(username="user", email="user@example.com", role=User.ROLE_REVIEWER)
        user.set_password("secret-password")

        self.assertNotEqual(user.password_hash, "secret-password")
        self.assertTrue(user.check_password("secret-password"))
        self.assertFalse(user.check_password("wrong-password"))

    def test_login_with_username_redirects_admin(self):
        self.create_user("admin", "admin@example.com", User.ROLE_ADMIN)
        response = self.client.post(
            "/login",
            data={"username_or_email": "admin", "password": "password123"},
            follow_redirects=False,
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.headers["Location"].endswith("/admin/"))

    def test_login_with_email_redirects_reviewer(self):
        self.create_user("reviewer", "reviewer@example.com", User.ROLE_REVIEWER)
        response = self.client.post(
            "/login",
            data={"username_or_email": "reviewer@example.com", "password": "password123"},
            follow_redirects=False,
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.headers["Location"].endswith("/reviewer/"))

    def test_repeated_login_failures_are_temporarily_blocked(self):
        self.create_user("reviewer", "reviewer@example.com", User.ROLE_REVIEWER)

        for _ in range(4):
            response = self.client.post(
                "/login",
                data={"username_or_email": "reviewer", "password": "wrong"},
            )
            self.assertEqual(response.status_code, 401)

        response = self.client.post(
            "/login",
            data={"username_or_email": "reviewer", "password": "wrong"},
        )
        self.assertEqual(response.status_code, 429)
        self.assertIn(b"Too many unsuccessful login attempts", response.data)
        self.assertTrue(LoginAttempt.query.filter_by(identifier="reviewer").one().is_locked())

    def test_successful_login_clears_previous_failures(self):
        self.create_user("reviewer", "reviewer@example.com", User.ROLE_REVIEWER)
        self.client.post(
            "/login",
            data={"username_or_email": "reviewer", "password": "wrong"},
        )

        response = self.client.post(
            "/login",
            data={"username_or_email": "reviewer", "password": "password123"},
        )

        self.assertEqual(response.status_code, 302)
        self.assertIsNone(LoginAttempt.query.filter_by(identifier="reviewer").first())

    def test_logout(self):
        self.create_user("reviewer", "reviewer@example.com", User.ROLE_REVIEWER)
        self.client.post(
            "/login",
            data={"username_or_email": "reviewer", "password": "password123"},
        )
        response = self.client.post("/logout", follow_redirects=False)

        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.headers["Location"].endswith("/login"))

    def test_admin_route_requires_login(self):
        response = self.client.get("/admin/")

        self.assertEqual(response.status_code, 302)
        self.assertIn("/login", response.headers["Location"])

    def test_admin_users_page_shows_assigned_language(self):
        admin = self.create_user("admin", "admin@example.com", User.ROLE_ADMIN)
        reviewer = self.create_user("reviewer", "reviewer@example.com", User.ROLE_REVIEWER)
        language = Language(
            display_name="Hindi",
            language_code="hi",
            excel_header="label::Hindi (hi)",
        )
        db.session.add(language)
        db.session.flush()
        db.session.add(UserLanguageAssignment(user_id=reviewer.id, language_id=language.id))
        db.session.commit()
        self.client.post(
            "/login",
            data={"username_or_email": admin.username, "password": "password123"},
        )

        response = self.client.get("/admin/users")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Assigned Language", response.data)
        self.assertIn(b"Hindi (hi)", response.data)

    def test_root_redirects_logged_out_users_to_login(self):
        response = self.client.get("/", follow_redirects=False)

        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.headers["Location"].endswith("/login"))

    def test_root_redirects_admin_to_admin_dashboard(self):
        self.create_user("admin", "admin@example.com", User.ROLE_ADMIN)
        self.client.post(
            "/login",
            data={"username_or_email": "admin", "password": "password123"},
        )

        response = self.client.get("/", follow_redirects=False)

        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.headers["Location"].endswith("/admin/"))

    def test_root_redirects_reviewer_to_reviewer_dashboard(self):
        self.create_user("reviewer", "reviewer@example.com", User.ROLE_REVIEWER)
        self.client.post(
            "/login",
            data={"username_or_email": "reviewer", "password": "password123"},
        )

        response = self.client.get("/", follow_redirects=False)

        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.headers["Location"].endswith("/reviewer/"))

    def test_reviewer_blocked_from_admin(self):
        self.create_user("reviewer", "reviewer@example.com", User.ROLE_REVIEWER)
        self.client.post(
            "/login",
            data={"username_or_email": "reviewer", "password": "password123"},
        )
        response = self.client.get("/admin/")

        self.assertEqual(response.status_code, 403)

    def test_reviewer_dashboard(self):
        self.create_user("reviewer", "reviewer@example.com", User.ROLE_REVIEWER)
        self.client.post(
            "/login",
            data={"username_or_email": "reviewer", "password": "password123"},
        )
        response = self.client.get("/reviewer/")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Welcome, reviewer", response.data)
        self.assertIn(b"No language has been assigned to your account.", response.data)


if __name__ == "__main__":
    unittest.main()
