#!/usr/bin/env python3
"""
sync_results.py — Sincroniza resultados da Copa 2026 via ESPN Core API.

Fonte: https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world/scoreboard
Grátis, sem autenticação, com placar ao vivo.

Uso:
    python sync_results.py                    # sincroniza jogos do dia
    python sync_results.py --date 2026-06-11  # sincroniza data específica
    python sync_results.py --all              # sincroniza todos os jogos sem placar
    python sync_results.py --live             # mostra placares ao vivo sem atualizar
    python sync_results.py --dry-run          # simula sem gravar

Cron (a cada 15 min nos dias de jogo):
    */15 * * * * cd /app && python backend/sync_results.py --all >> /var/log/bolao_sync.log 2>&1
"""

import argparse
import json
import logging
import os
import sys
import urllib.request
import urllib.error
from datetime import datetime, timedelta, timezone

# ---------------------------------------------------------------------------
# Configuração
# ---------------------------------------------------------------------------

ESPN_SCOREBOARD = (
    "https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world/scoreboard"
)

# URL do backend do bolão (dentro do container: localhost:5000)
BOLAO_API = os.environ.get("BOLAO_API_URL", "http://localhost:5000")

# Token de admin (obtido via POST /login ou env var)
ADMIN_TOKEN = os.environ.get("BOLAO_ADMIN_TOKEN", "")

# Mapeamento ESPN displayName → Nome em português (usado no bolão)
TEAM_MAP = {
    "Mexico":            "México",
    "South Africa":      "África do Sul",
    "South Korea":       "Coreia do Sul",
    "Czechia":           "República Tcheca",
    "Canada":            "Canadá",
    "Bosnia-Herzegovina": "Bósnia",
    "United States":     "Estados Unidos",
    "Paraguay":          "Paraguai",
    "Brazil":            "Brasil",
    "Morocco":           "Marrocos",
    "Qatar":             "Catar",
    "Switzerland":       "Suíça",
    "Haiti":             "Haiti",
    "Scotland":          "Escócia",
    "Australia":         "Austrália",
    "Türkiye":           "Turquia",
    "Turkey":            "Turquia",  # fallback
    "Germany":           "Alemanha",
    "Curaçao":           "Curaçao",
    "Curacao":           "Curaçao",  # fallback
    "Netherlands":       "Holanda",
    "Japan":             "Japão",
    "Ivory Coast":       "Costa do Marfim",
    "Ecuador":           "Equador",
    "Sweden":            "Suécia",
    "Tunisia":           "Tunísia",
    "Spain":             "Espanha",
    "Cape Verde":        "Cabo Verde",
    "Belgium":           "Bélgica",
    "Egypt":             "Egito",
    "Saudi Arabia":      "Arábia Saudita",
    "Uruguay":           "Uruguai",
    "Iran":              "Irã",
    "New Zealand":       "Nova Zelândia",
    "France":            "França",
    "Senegal":           "Senegal",
    "Iraq":              "Iraque",
    "Norway":            "Noruega",
    "Argentina":         "Argentina",
    "Algeria":           "Argélia",
    "Austria":           "Áustria",
    "Jordan":            "Jordânia",
    "Portugal":          "Portugal",
    "Congo DR":          "RD Congo",
    "England":           "Inglaterra",
    "Croatia":           "Croácia",
    "Ghana":              "Gana",
    "Panama":            "Panamá",
    "Uzbekistan":        "Uzbequistão",
    "Colombia":          "Colômbia",
    # Mapeamento reverso (português → inglês) não necessário, mas incluímos
    # para o caso de a API usar nomes alternativos
}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("sync_results")


def _http_get(url: str, timeout: int = 15) -> dict:
    """GET request returning JSON."""
    req = urllib.request.Request(url, headers={"User-Agent": "BolaoSync/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode())


def _http_put(url: str, data: dict, headers: dict | None = None, timeout: int = 10) -> dict:
    """PUT request returning JSON."""
    body = json.dumps(data).encode()
    hdrs = {"Content-Type": "application/json", "User-Agent": "BolaoSync/1.0"}
    if headers:
        hdrs.update(headers)
    req = urllib.request.Request(url, data=body, headers=hdrs, method="PUT")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode())


def _http_post(url: str, data: dict, timeout: int = 10) -> dict:
    """POST request returning JSON."""
    body = json.dumps(data).encode()
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json", "User-Agent": "BolaoSync/1.0"}, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode())

# ---------------------------------------------------------------------------
# ESPN API
# ---------------------------------------------------------------------------

def fetch_espn_games(date_str: str) -> list[dict]:
    """Busca jogos da ESPN para uma data (YYYY-MM-DD)."""
    url = f"{ESPN_SCOREBOARD}?dates={date_str.replace('-', '')}"
    log.info(f"Buscando ESPN: {url}")
    data = _http_get(url)
    return data.get("events", [])


def parse_espn_event(event: dict) -> dict | None:
    """Extrai dados relevantes de um evento ESPN."""
    competitions = event.get("competitions", [])
    if not competitions:
        return None

    comp = competitions[0]
    status = comp.get("status", {})
    status_type = status.get("type", {})
    state = status_type.get("state", "")  # "pre", "in", "post"
    completed = status_type.get("completed", False)
    display_clock = status.get("displayClock", "")
    detail = status_type.get("detail", "")

    competitors = comp.get("competitors", [])
    if len(competitors) != 2:
        return None

    home = away = None
    for c in competitors:
        info = {
            "name_en": c["team"]["displayName"],
            "name_pt": TEAM_MAP.get(c["team"]["displayName"], c["team"]["displayName"]),
            "abbreviation": c["team"].get("abbreviation", ""),
            "score": int(c.get("score", 0)),
        }
        if c.get("homeAway") == "home":
            home = info
        else:
            away = info

    if not home or not away:
        return None

    return {
        "home": home,
        "away": away,
        "state": state,
        "completed": completed,
        "is_full_time": state == "post" and completed and detail in ("FT", "AET", "PEN"),
        "display_clock": display_clock,
        "detail": detail,
        "date": event.get("date", ""),
        "name": event.get("name", ""),
    }

# ---------------------------------------------------------------------------
# Bolão API
# ---------------------------------------------------------------------------

def fetch_bolao_games() -> list[dict]:
    """Busca todos os jogos do bolão."""
    return _http_get(f"{BOLAO_API}/games")


def update_bolao_score(game_id: int, score_a: int, score_b: int) -> dict:
    """Atualiza o placar de um jogo no bolão."""
    headers = {}
    if ADMIN_TOKEN:
        headers["Authorization"] = f"Bearer {ADMIN_TOKEN}"
    return _http_put(f"{BOLAO_API}/games/{game_id}", {"score_a": score_a, "score_b": score_b}, headers=headers)


def find_bolao_match(bolao_games: list[dict], home_pt: str, away_pt: str, date_iso: str | None = None, force: bool = False):
    """
    Encontra um jogo no bolão que corresponda ao matchup.
    Considera que os times podem estar em qualquer ordem (home/away).
    """
    candidates = []
    for g in bolao_games:
        if not force and g.get("score_a") is not None and g.get("score_b") is not None:
            continue  # já tem placar
        match_a = (
            (g["team_a"] == home_pt and g["team_b"] == away_pt) or
            (g["team_a"] == away_pt and g["team_b"] == home_pt)
        )
        if match_a:
            candidates.append(g)

    if not candidates:
        return None

    # Se houver data, tenta filtrar
    if date_iso and len(candidates) > 1:
        for c in candidates:
            kickoff = c.get("kickoff", "")
            if kickoff and date_iso[:10] in kickoff:
                return c

    return candidates[0]

# ---------------------------------------------------------------------------
# Sync logic
# ---------------------------------------------------------------------------

def sync_date(date_str: str, bolao_games: list[dict], dry_run: bool = False, force: bool = False) -> list[dict]:
    """Sincroniza jogos de uma data específica."""
    espn_events = fetch_espn_games(date_str)
    results = []

    for event in espn_events:
        parsed = parse_espn_event(event)
        if not parsed:
            continue

        home_pt = parsed["home"]["name_pt"]
        away_pt = parsed["away"]["name_pt"]

        # Mostra status
        if parsed["state"] == "in":
            log.info(
                f"🔴 AO VIVO {home_pt} {parsed['home']['score']} x "
                f"{parsed['away']['score']} {away_pt} ({parsed['display_clock']})"
            )
        elif parsed["is_full_time"]:
            log.info(
                f"✅ FINAL {home_pt} {parsed['home']['score']} x "
                f"{parsed['away']['score']} {away_pt}"
            )
        else:
            log.info(f"⏳ AGENDADO {home_pt} x {away_pt} — {parsed['detail']}")

        # Só atualiza se o jogo foi completamente finalizado (FT/AET/PEN)
        if not parsed["is_full_time"]:
            results.append({
                "status": parsed["state"],
                "home": home_pt,
                "away": away_pt,
                "score_a": parsed["home"]["score"],
                "score_b": parsed["away"]["score"],
                "clock": parsed["display_clock"],
                "action": "skipped_not_finished",
            })
            continue

        # Procura no bolão
        match = find_bolao_match(bolao_games, home_pt, away_pt, parsed.get("date"), force=force)
        if not match:
            log.warning(f"⚠️  Não encontrou no bolão: {home_pt} x {away_pt}")
            results.append({
                "status": "not_found",
                "home": home_pt,
                "away": away_pt,
                "action": "skipped_not_in_bolao",
            })
            continue

        if not force and match.get("score_a") is not None:
            log.info(f"⏭️  Já tem placar: {home_pt} x {away_pt} (ID {match['id']})")
            results.append({
                "status": "already_has_score",
                "game_id": match["id"],
                "home": home_pt,
                "away": away_pt,
                "action": "skipped",
            })
            continue

        # Determina placar na ordem correta do bolão
        if match["team_a"] == home_pt:
            score_a = parsed["home"]["score"]
            score_b = parsed["away"]["score"]
        else:
            score_a = parsed["away"]["score"]
            score_b = parsed["home"]["score"]

        if dry_run:
            log.info(f"🔧 [DRY-RUN] Atualizaria jogo {match['id']}: {match['team_a']} {score_a} x {score_b} {match['team_b']}")
            results.append({
                "status": "dry_run",
                "game_id": match["id"],
                "home": match["team_a"],
                "away": match["team_b"],
                "score_a": score_a,
                "score_b": score_b,
                "action": "would_update",
            })
            continue

        # Atualiza!
        try:
            updated = update_bolao_score(match["id"], score_a, score_b)
            log.info(
                f"💾 ATUALIZADO jogo {match['id']}: "
                f"{match['team_a']} {score_a} x {score_b} {match['team_b']}"
            )
            results.append({
                "status": "updated",
                "game_id": match["id"],
                "home": match["team_a"],
                "away": match["team_b"],
                "score_a": score_a,
                "score_b": score_b,
                "action": "updated",
            })
            # Atualiza a lista local para não reprocessar
            match["score_a"] = score_a
            match["score_b"] = score_b
        except Exception as e:
            log.error(f"❌ Erro ao atualizar jogo {match['id']}: {e}")
            results.append({
                "status": "error",
                "game_id": match["id"],
                "action": "error",
                "error": str(e),
            })

    return results


def sync_all(bolao_games: list[dict], dry_run: bool = False, force: bool = False) -> list[dict]:
    """Sincroniza todas as datas de jogos do bolão que ainda não têm placar."""
    # Coleta datas únicas de jogos sem placar
    dates = set()
    for g in bolao_games:
        if g.get("score_a") is None and g.get("kickoff"):
            dates.add(g["kickoff"][:10])

    if not dates:
        log.info("✅ Todos os jogos já têm placar!")
        return []

    all_results = []
    for d in sorted(dates):
        log.info(f"📅 Processando {d}")
        results = sync_date(d, bolao_games, dry_run=dry_run, force=force)
        all_results.extend(results)

    return all_results

# ---------------------------------------------------------------------------
# Live mode (display only)
# ---------------------------------------------------------------------------

def show_live():
    """Mostra placares ao vivo de hoje sem atualizar nada."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    espn_events = fetch_espn_games(today)

    if not espn_events:
        print("Nenhum jogo encontrado para hoje.")
        return

    print(f"\n{'='*60}")
    print(f"  ⚽ COPA DO MUNDO 2026 — Placares de Hoje ({today})")
    print(f"{'='*60}\n")

    for event in espn_events:
        parsed = parse_espn_event(event)
        if not parsed:
            continue

        home = parsed["home"]
        away = parsed["away"]
        state = parsed["state"]

        if state == "in":
            icon = "🔴"
            status_text = f"AO VIVO — {parsed['display_clock']}"
        elif parsed["is_full_time"]:
            icon = "✅"
            status_text = "FINALIZADO"
        else:
            icon = "⏳"
            status_text = f"{parsed['detail']}"

        print(f"  {icon} {home['name_pt']}  {home['score']} x {away['score']}  {away['name_pt']}")
        print(f"     {status_text}")
        print()

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    import os

    global BOLAO_API
    global ADMIN_TOKEN

    parser = argparse.ArgumentParser(description="Sincroniza resultados da Copa 2026 via ESPN")
    parser.add_argument("--date", help="Data específica (YYYY-MM-DD)")
    parser.add_argument("--all", action="store_true", help="Sincroniza todos os jogos sem placar")
    parser.add_argument("--live", action="store_true", help="Mostra placares ao vivo (não grava)")
    parser.add_argument("--dry-run", action="store_true", help="Simula sem gravar")
    parser.add_argument("--force", action="store_true", help="Sobrescreve placares já existentes")
    parser.add_argument("--api-url", help=f"URL do bolão API (default: {BOLAO_API})")
    parser.add_argument("--token", help="Token de admin (ou set BOLAO_ADMIN_TOKEN env)")
    parser.add_argument("--login", nargs=2, metavar=("USER", "PASS"), help="Faz login automaticamente")
    args = parser.parse_args()

    if args.api_url:
        BOLAO_API = args.api_url

    # Resolve token
    if args.token:
        ADMIN_TOKEN = args.token
    elif args.login:
        try:
            resp = _http_post(
                f"{BOLAO_API}/login",
                {"username": args.login[0], "password": args.login[1]},
            )
            ADMIN_TOKEN = resp["token"]
            log.info("🔑 Login realizado com sucesso")
        except Exception as e:
            log.error(f"❌ Falha no login: {e}")
            sys.exit(1)

    # Modo live
    if args.live:
        show_live()
        return

    # Busca jogos do bolão
    log.info(f"Conectando ao bolão: {BOLAO_API}/games")
    try:
        bolao_games = fetch_bolao_games()
    except Exception as e:
        log.error(f"Não conseguiu conectar ao bolão: {e}")
        sys.exit(1)

    log.info(f"{len(bolao_games)} jogos no bolão, {sum(1 for g in bolao_games if g.get('score_a') is None)} sem placar")

    # Determina quais datas sincronizar
    if args.date:
        results = sync_date(args.date, bolao_games, dry_run=args.dry_run, force=args.force)
    elif args.all:
        results = sync_all(bolao_games, dry_run=args.dry_run, force=args.force)
    else:
        # Default: sincroniza hoje e ontem (para pegar jogos que terminaram depois da meia-noite)
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")
        results = []
        for d in [yesterday, today]:
            r = sync_date(d, bolao_games, dry_run=args.dry_run, force=args.force)
            results.extend(r)

    # Resumo
    updated = sum(1 for r in results if r.get("action") == "updated")
    skipped = sum(1 for r in results if "skipped" in r.get("action", ""))
    not_found = sum(1 for r in results if r.get("action") == "skipped_not_in_bolao")
    errors = sum(1 for r in results if r.get("action") == "error")

    log.info(f"\n{'='*40}")
    log.info(f"Resumo: {updated} atualizados, {skipped} ignorados, {not_found} não encontrados, {errors} erros")
    log.info(f"{'='*40}")

    # Output JSON para parsing automático
    if updated > 0 or errors > 0:
        print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    import os
    main()
