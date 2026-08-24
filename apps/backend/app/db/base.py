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
import app.db.models.score_history   # noqa: F401 E402  — registers score history table
import app.db.models.feedback        # noqa: F401 E402  — registers feedback_submissions table
import app.db.models.event_coverage  # noqa: F401 E402  — registers event_coverage table
import app.db.models.fact  # noqa: F401 E402  — registers facts table
import app.db.models.generated_media # noqa: F401 E402  — registers generated_media table
import app.db.models.macro_release   # noqa: F401 E402  — registers macro_releases table
import app.db.models.returning_user_feedback  # noqa: F401 E402  — registers returning_user_feedback table
import app.db.models.company_signal  # noqa: F401 E402  — registers ai_company_signals table (previously only
                                       # registered as a side effect of app.api.company_scores' import chain
                                       # running before create_all(); see WEEKEND_INTELLIGENCE_PHASE1_ARCHITECTURE.md §27.J)
import app.db.models.weekend_intelligence  # noqa: F401 E402  — registers weekend_intelligence_snapshots table
import app.db.models.development     # noqa: F401 E402  — registers developments/development_evidence tables (Phase 6A)
import app.db.models.opportunity_v2  # noqa: F401 E402  — registers opportunities_v2/opportunity_v2_developments tables (Opportunity Engine V2, shadow mode)
import app.db.models.company_entity  # noqa: F401 E402  — registers company_entities/company_aliases tables (Company Identity C2)
