"""List available match IDs."""
import asyncio
import selectors
from sqlalchemy import text
from app.core.db import session_scope
from app.core.config import Settings

async def main():
    s = Settings()
    async with session_scope(s) as ss:
        rows = (await ss.execute(text(
            "SELECT m.id, ht.name as home, at.name as away "
            "FROM matches m "
            "JOIN teams ht ON m.home_team_id = ht.id "
            "JOIN teams at ON m.away_team_id = at.id "
            "LIMIT 10"
        ))).fetchall()
        for r in rows:
            print(f"match_id={r[0]}  {r[1]} vs {r[2]}")

selector = selectors.SelectSelector()
loop = asyncio.SelectorEventLoop(selector)
asyncio.run(main(), loop_factory=lambda: loop)
