from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate

db = SQLAlchemy(engine_options={"pool_pre_ping": True})
migrate = Migrate()
