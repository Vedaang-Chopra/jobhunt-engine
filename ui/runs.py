"""Layer 3 run registry — kept as a compatibility shim.

The canonical execution layer now lives in ``engine.run_manager`` +
``engine.workflows``. This module re-exports ``RunRegistry``/``RUNS`` (the
UI-facing facade) so historical imports keep working.
"""

from ui.triggers import RUNS, RunRegistry  # noqa: F401
