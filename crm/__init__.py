from flask import Flask, jsonify
from .config import Config
from .extensions import db, migrate

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)
    migrate.init_app(app, db)

    from .routes.health import health_bp
    app.register_blueprint(health_bp)

    @app.errorhandler(400)
    def bad_request(error):
        return jsonify({"error": "Bad request"}), 400

    @app.errorhandler(404)
    def not_found(error):
        return jsonify({"error": "Not found"}), 404

    @app.errorhandler(409)
    def conflict(error):
        return jsonify({"error": "Conflict"}), 409

    @app.errorhandler(500)
    def server_error(error):
        return jsonify({"error": "Internal server error"}), 500

    return app
