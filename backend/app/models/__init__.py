"""All 90 tables in 14 domains. Importing this package registers every model on Base.metadata."""

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
