"""Event-loop policy required by psycopg's async driver on Windows.

psycopg refuses to run in async mode on Windows' default ``ProactorEventLoop`` and
raises ``InterfaceError`` the moment a connection is opened. Anything that calls
``asyncio.run(...)`` itself (the ETL CLI, ``scripts/seed.py``, pytest) therefore has to
select a selector-based loop first.

The API server is the one case this module cannot fix from inside the app: uvicorn
chooses its loop **before** importing ``app.main``, and without ``--reload`` it picks
the Proactor on Windows (uvicorn's own ``asyncio_loop_factory`` does exactly this). The
server must therefore be started with the factory below::

    uvicorn app.main:app --loop app.core.eventloop:psycopg_safe_uvicorn_loop_factory

The README's quickstart includes the flag; ``--reload`` happens to work without it only
because reloading forces a subprocess, which uvicorn serves on a selector loop.

Deployments run Linux, where all of this is a no-op.
"""

from __future__ import annotations

import asyncio
import sys


def use_psycopg_compatible_event_loop() -> None:
    """Select a selector event loop on Windows; a no-op everywhere else.

    ``WindowsSelectorEventLoopPolicy`` still exists in 3.12 (it is deprecated only in
    3.14), and is looked up dynamically so the import cannot fail on other platforms.
    """
    if sys.platform == "win32":
        policy = getattr(asyncio, "WindowsSelectorEventLoopPolicy", None)
        if policy is not None:
            asyncio.set_event_loop_policy(policy())


def psycopg_safe_uvicorn_loop_factory() -> asyncio.AbstractEventLoop:
    """A ``--loop`` factory for uvicorn that psycopg can run under on Windows.

    A custom ``--loop`` value is imported and used as the loop factory itself (unlike
    uvicorn's built-in names, which are factories-of-factories), so this returns the loop
    instance. It always chooses a selector loop, which is what uvicorn picks everywhere
    psycopg does not object to it.
    """
    return asyncio.SelectorEventLoop()
