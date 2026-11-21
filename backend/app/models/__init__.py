"""A mapping of the designed schema: 90 tables in 14 domains.

The tables are created by the SQL in db/ (generated from docs/database/schema_spec.py), never by
SQLAlchemy. tests/test_schema_drift.py fails when this mapping and that schema disagree."""

from .assistant import *  # noqa: F403
from .base import VECTOR_DIM, Base
from .catalogue import *  # noqa: F403
from .certifications import *  # noqa: F403
from .community import *  # noqa: F403
from .feed import *  # noqa: F403
from .identity import *  # noqa: F403
from .media import *  # noqa: F403
from .platform import *  # noqa: F403
from .recalls import *  # noqa: F403
from .rewards import *  # noqa: F403
from .risk import *  # noqa: F403
from .screening import *  # noqa: F403
from .sources import *  # noqa: F403
from .wallet import *  # noqa: F403

__all__ = ["Base", "VECTOR_DIM"]
