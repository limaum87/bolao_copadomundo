"""Utility script to bootstrap the SQLite database.

It attempts to parse the `jogos_copa_2026.txt` file to populate the initial
list of games. Lines that cannot be parsed are skipped but reported in the
output so they can be added manually later.
"""
from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

from backend.database import engine, session_scope
from backend.models import Base, Game

ROOT = Path(__file__).resolve().parent.parent
TEXT_FILE = ROOT / "jogos_copa_2026.txt"

MONTHS = {
    "janeiro": 1,
    "fevereiro": 2,
    "março": 3,
    "marco": 3,
    "abril": 4,
    "maio": 5,
    "junho": 6,
    "julho": 7,
    "agosto": 8,
    "setembro": 9,
    "outubro": 10,
    "novembro": 11,
    "dezembro": 12,
}

GAME_PATTERN = re.compile(
    r"\*\s*(?P<time>\d{1,2})h\s*-\s*(?P<team_a>[^x]+)x\s*(?P<team_b>[^–-]+)",
    re.IGNORECASE,
)


def parse_date_line(line: str) -> datetime | None:
    clean = line.strip("* ")
    parts = clean.split(",", 1)
    if len(parts) < 2:
        return None
    _, date_part = parts
    date_part = date_part.strip()
    tokens = date_part.split()
    if len(tokens) < 4:
        return None
    try:
        day = int(tokens[0])
        month_name = tokens[2].lower().replace("ã", "a").replace("ç", "c")
        month = MONTHS.get(month_name)
        year = int(tokens[4]) if len(tokens) > 4 else int(tokens[3])
    except (ValueError, IndexError):
        return None
    if not month:
        return None
    return datetime(year=year, month=month, day=day)


def load_games():
    Base.metadata.create_all(engine)
    if not TEXT_FILE.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {TEXT_FILE}")

    current_date = None
    added = 0
    skipped: list[str] = []

    with session_scope() as session:
        with TEXT_FILE.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                if line.startswith("**") and "," in line:
                    current_date = parse_date_line(line)
                    continue
                match = GAME_PATTERN.match(line)
                if match and current_date:
                    hour = int(match.group("time"))
                    kickoff = current_date.replace(hour=hour, minute=0)
                    game = Game(
                        kickoff=kickoff,
                        team_a=match.group("team_a").strip().strip("- "),
                        team_b=match.group("team_b").strip().split("–")[0].strip(),
                    )
                    session.add(game)
                    added += 1
                elif line.startswith("*"):
                    skipped.append(line)

        print(f"Jogos adicionados: {added}")
        if skipped:
            print("Linhas não interpretadas (adicione manualmente se necessário):")
            for item in skipped:
                print(f"  {item}")


if __name__ == "__main__":
    load_games()
