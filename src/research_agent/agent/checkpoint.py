from __future__ import annotations

import logging

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

from research_agent.core.config import get_settings

logger = logging.getLogger(__name__)

_pool: AsyncConnectionPool | None = None
_checkpointer: AsyncPostgresSaver | None = None
_setup_done = False


def checkpoint_conninfo() -> str:
    """psycopg connection string."""
    url = get_settings().database_url
    return url.replace("postgresql+psycopg://", "postgresql://")


async def get_checkpointer() -> AsyncPostgresSaver:
    global _pool, _checkpointer, _setup_done

    if _checkpointer is not None:
        return _checkpointer

    conninfo = checkpoint_conninfo()
    _pool = AsyncConnectionPool(
        conninfo=conninfo,
        kwargs={"autocommit": True, "row_factory": dict_row},
        open=False,
        min_size=1,
        max_size=10,
    )
    await _pool.open()
    _checkpointer = AsyncPostgresSaver(_pool)
    if not _setup_done:
        await _checkpointer.setup()
        _setup_done = True
        logger.info("LangGraph Postgres checkpointer ready")
    return _checkpointer


async def close_checkpointer() -> None:
    global _pool, _checkpointer, _setup_done
    if _pool is not None:
        await _pool.close()
    _pool = None
    _checkpointer = None
    _setup_done = False
