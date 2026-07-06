from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


# Import ALL models here so SQLAlchemy metadata is populated for Alembic
# and for create_all() on startup.
import app.db.models_legacy  # noqa: F401 E402  — registers legacy tables
import app.db.models.opportunity  # noqa: F401 E402  — registers opportunity tables
import app.db.models.event   # noqa: F401 E402  — registers event detail tables
import app.db.models.ripple  # noqa: F401 E402  — registers ripple_graphs table
