
# TODO: Implement user-related routes. [Milestone: API Endpoints]

from flask import Blueprint, request, jsonify
from services.user_service import UserService

user_bp = Blueprint('user_bp', __name__)

@user_bp.route('/', methods=['POST'])
def create_user():
    data = request.get_json()
    user = UserService.create_user(data)
    return jsonify(user), 201