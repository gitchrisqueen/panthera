import unittest
from app import app, db
from models.alert import Alert

class AlertTestCase(unittest.TestCase):
    def setUp(self):
        self.app = app.test_client()
        db.create_all()

    def tearDown(self):
        db.session.remove()
        db.drop_all()

    def test_create_alert(self):
        response = self.app.post('/alerts/', json={
            'user_id': 1,
            'condition': 'line_movement > 5'
        })
        self.assertEqual(response.status_code, 201)