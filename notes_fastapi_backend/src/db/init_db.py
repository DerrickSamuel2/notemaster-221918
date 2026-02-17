from sqlalchemy.engine import Engine

from src.db.models import Base


# PUBLIC_INTERFACE
def init_db(engine: Engine) -> None:
    """Create database tables if they do not exist.

    This is a lightweight alternative to migrations for early-stage projects.
    """
    Base.metadata.create_all(bind=engine)
