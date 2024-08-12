from flask import Blueprint, request, jsonify
from services.alert_service import AlertService

alert_bp = Blueprint('alert_bp', __name__)

@alert_bp.route('/', methods=['POST'])
def create_alert():
    data = request.get_json()
    alert = AlertService.create_alert(data)
    return jsonify(alert), 201