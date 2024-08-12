import unittest
from app import app, db
from models.betting_line import BettingLine

class BettingLineTestCase(unittest.TestCase):
    def setUp(self):
        self.app = app.test_client()
        db.create_all()

    def tearDown(self):
        db.session.remove()
        db.drop_all()

    def test_get_betting_lines(self):
        response = self.app.get('/betting_lines/')
        self.assertEqual(response.status_code, 200)