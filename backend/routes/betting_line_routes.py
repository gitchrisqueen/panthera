from flask import Blueprint, request, jsonify
from services.betting_line_service import BettingLineService

betting_line_bp = Blueprint('betting_line_bp', __name__)

@betting_line_bp.route('/', methods=['GET'])
def get_betting_lines():
    lines = BettingLineService.get_all_lines()
    return jsonify(lines)