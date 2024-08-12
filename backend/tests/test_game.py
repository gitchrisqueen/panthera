import unittest
from app import app, db
from models.game import Game

class GameTestCase(unittest.TestCase):
    def setUp(self):
        self.app = app.test_client()
        db.create_all()

    def tearDown(self):
        db.session.remove()
        db.drop_all()

    def test_get_games(self):
        response = self.app.get('/games/')
        self.assertEqual(response.status_code, 200)