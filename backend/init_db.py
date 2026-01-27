"""Utility script to bootstrap the SQLite database.

It loads the `jogos_copa_2026.json` file to populate the initial
list of games.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from backend.database import engine, session_scope
from backend.models import Base, Game, AdminUser
from werkzeug.security import generate_password_hash

ROOT = Path(__file__).resolve().parent.parent
JSON_FILE = ROOT / "jogos_copa_2026.json"


def load_games():
    Base.metadata.create_all(engine)
    
    # Create default admin user
    with session_scope() as session:
        admin = session.query(AdminUser).filter_by(username="admin").first()
        if not admin:
            print("Creating default admin user...")
            hashed_password = generate_password_hash("admin")
            new_admin = AdminUser(username="admin", password_hash=hashed_password)
            session.add(new_admin)
            print("Default admin user created.")

    if not JSON_FILE.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {JSON_FILE}")

    added = 0

    with session_scope() as session:
        with JSON_FILE.open("r", encoding="utf-8") as f:
            games_data = json.load(f)
            
            for game_data in games_data:
                kickoff = datetime.fromisoformat(game_data["kickoff"])
                game = Game(
                    kickoff=kickoff,
                    team_a=game_data["team_a"],
                    team_b=game_data["team_b"],
                )
                session.add(game)
                added += 1

        print(f"Jogos adicionados: {added}")


if __name__ == "__main__":
    load_games()
