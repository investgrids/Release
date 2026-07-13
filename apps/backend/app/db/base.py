from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


# Import ALL models here so SQLAlchemy metadata is populated for Alembic
# and for create_all() on startup.
import app.db.models_legacy  # noqa: F401 E402  — registers legacy tables
import app.db.models.opportunity  # noqa: F401 E402  — registers opportunity tables
import app.db.models.event   # noqa: F401 E402  — registers event detail tables
import app.db.models.ripple  # noqa: F401 E402  — registers ripple_graphs table
import app.db.models.intelligence  # noqa: F401 E402  — registers intelligence tables
import app.db.models.historical_memory  # noqa: F401 E402  — registers historical market memory table
import app.db.models.intelligence_graph  # noqa: F401 E402  — registers market intelligence graph tables
import app.db.models.predictions        # noqa: F401 E402  — registers prediction learning engine tables
import app.db.models.company_announcements  # noqa: F401 E402  — registers company announcements table
import app.db.models.intelligence_article   # noqa: F401 E402  — registers AIPE intelligence articles table
