from .user_routes import user_bp
from .game_routes import game_bp
from .betting_line_routes import betting_line_bp
from .alert_routes import alert_bp

def register_routes(app):
    app.register_blueprint(user_bp, url_prefix='/users')
    app.register_blueprint(game_bp, url_prefix='/games')
    app.register_blueprint(betting_line_bp, url_prefix='/betting_lines')
    app.register_blueprint(alert_bp, url_prefix='/alerts')