import unittest
from app import app, db
from models.user import User

class UserTestCase(unittest.TestCase):
    def setUp(self):
        self.app = app.test_client()
        db.create_all()

    def tearDown(self):
        db.session.remove()
        db.drop_all()

    def test_create_user(self):
        response = self.app.post('/users/', json={
            'username': 'testuser',
            'email': 'test@example.com',
            'password': 'password'
        })
        self.assertEqual(response.status_code, 201)