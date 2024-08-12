from models import db
from models.user import User

class UserService:
    @staticmethod
    def create_user(data):
        user = User(username=data['username'], email=data['email'], password_hash=data['password'])
        db.session.add(user)
        db.session.commit()
        return user