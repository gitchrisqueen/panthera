from . import db

class Alert(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    condition = db.Column(db.String(200), nullable=False)
    is_active = db.Column(db.Boolean, default=True)