from models import db
from models.alert import Alert

class AlertService:
    @staticmethod
    def create_alert(data):
        alert = Alert(user_id=data['user_id'], condition=data['condition'])
        db.session.add(alert)
        db.session.commit()
        return alert