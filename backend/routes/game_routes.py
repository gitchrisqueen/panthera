
# TODO: Implement game-related routes. [Milestone: API Endpoints]

from flask import Blueprint, request, jsonify
from services.game_service import GameService

game_bp = Blueprint('game_bp', __name__)

@game_bp.route('/', methods=['GET'])
def get_games():
    games = GameService.get_all_games()
    return jsonify(games)