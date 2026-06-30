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


# ---------------------------------------------------------------------------
# Tradução de placeholders de mata-mata (times ainda indefinidos)
# ---------------------------------------------------------------------------
# Aplicadas sobre o displayName da ESPN quando o nome NÃO está no TEAM_MAP.
# Exemplos que aparecem na Copa 2026:
#   "Group J 2nd Place"      -> "2º Grupo J"
#   "Group A Winner"         -> "1º Grupo A"
#   "Third Place Group E/.." -> "3º Grupos E/.."
#   "Round of 32 1 Winner"   -> "Vencedor Fase-32 #1"
#   "Round of 16 5 Winner"   -> "Vencedor Oitavas #5"
#   "Quarterfinal 2 Winner"  -> "Vencedor Quartas #2"
#   "Semifinal 1 Winner"     -> "Vencedor Semifinal #1"
#   "Semifinal 1 Loser"      -> "Perdedor Semifinal #1"
import re as _re
_PLACEHOLDER_RULES = [
    (_re.compile(r"^Group\s+([A-Z])\s+Winner$", _re.I),          lambda m: f"1º Grupo {m.group(1)}"),
    (_re.compile(r"^Group\s+([A-Z])\s+2nd\s+Place$", _re.I),     lambda m: f"2º Grupo {m.group(1)}"),
    (_re.compile(r"^Group\s+([A-Z])\s+(\d)(?:st|nd|rd|th)\s+Place$", _re.I), lambda m: f"{m.group(2)}º Grupo {m.group(1)}"),
    (_re.compile(r"^Third\s+Place\s+Group\s+(.+)$", _re.I),      lambda m: f"3º Grupos {m.group(1)}"),
    (_re.compile(r"^Round\s+of\s+32\s+(\d+)\s+Winner$", _re.I),  lambda m: f"Vencedor Fase-32 #{m.group(1)}"),
    (_re.compile(r"^Round\s+of\s+16\s+(\d+)\s+Winner$", _re.I),  lambda m: f"Vencedor Oitavas #{m.group(1)}"),
    (_re.compile(r"^Quarterfinal\s+(\d+)\s+Winner$", _re.I),     lambda m: f"Vencedor Quartas #{m.group(1)}"),
    (_re.compile(r"^Semifinal\s+(\d+)\s+Winner$", _re.I),        lambda m: f"Vencedor Semifinal #{m.group(1)}"),
    (_re.compile(r"^Semifinal\s+(\d+)\s+Loser$", _re.I),         lambda m: f"Perdedor Semifinal #{m.group(1)}"),
]


def translate_team(name_en: str) -> str:
    """Traduz um nome de time/placeholder da ESPN para português.
    Primeiro tenta o TEAM_MAP (times reais); depois regras de placeholder."""
    if not name_en:
        return name_en
    if name_en in TEAM_MAP:
        return TEAM_MAP[name_en]
    for pattern, repl in _PLACEHOLDER_RULES:
        m = pattern.match(name_en.strip())
        if m:
            return repl(m)
    return name_en

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
            "name_pt": translate_team(c["team"]["displayName"]),
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
        # detail: 'FT' (90min), 'AET' (prorrogação, placar c/ vencedor),
        # 'FT-Pens' (pênaltis, placar do EMPATE — ESPN não soma o shoot-out).
        # Obs: a ESPN usa 'FT-Pens' e não 'PEN' (mantido por compat/segurança).
        "is_full_time": state == "post" and completed and detail in ("FT", "AET", "PEN", "FT-Pens"),
        "display_clock": display_clock,
        "detail": detail,
        "date": event.get("date", ""),
        "name": event.get("name", ""),
        "espn_id": str(event.get("id", "")),
    }

# ---------------------------------------------------------------------------
# Bolão API
# ---------------------------------------------------------------------------

def fetch_bolao_games() -> list[dict]:
    """Busca todos os jogos do bolão."""
    return _http_get(f"{BOLAO_API}/games")


def find_bolao_match_by_espn(bolao_games: list[dict], espn_id: str | None):
    """Encontra um jogo no bolão pelo espn_id (chave estável do mata-mata)."""
    if not espn_id:
        return None
    for g in bolao_games:
        if str(g.get("espn_id") or "") == str(espn_id):
            return g
    return None


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
# Criação de jogos (mata-mata, inclusive placeholders) e renomeação
# ---------------------------------------------------------------------------

# Fuso do bolão: America/Sao_Paulo (UTC-3). A ESPN devolve horários em UTC (Z).
BRT_TZ = timezone(timedelta(hours=-3))


def fetch_espn_events_raw(dates_param: str) -> list[dict]:
    """Busca eventos da ESPN aceitando data única (20260628) ou
    range (20260628-20260720)."""
    url = f"{ESPN_SCOREBOARD}?dates={dates_param}"
    log.info(f"Buscando ESPN: {url}")
    data = _http_get(url)
    return data.get("events", [])


def _espn_date_to_brt_iso(date_str: str) -> str | None:
    """Converte '2026-07-02T19:00Z' (UTC) para ISO em horário de Brasília,
    sem timezone (formato esperado pelo banco)."""
    if not date_str:
        return None
    try:
        dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        return dt.astimezone(BRT_TZ).strftime("%Y-%m-%dT%H:%M:%S")
    except Exception:
        return None


def _auth_headers() -> dict:
    return {"Authorization": f"Bearer {ADMIN_TOKEN}"} if ADMIN_TOKEN else {}


def import_bolao_games(games: list[dict]) -> dict:
    """POST /games/import com auth. Cada item: kickoff, team_a, team_b, espn_id?"""
    body = json.dumps(games).encode()
    req = urllib.request.Request(
        f"{BOLAO_API}/games/import",
        data=body,
        headers={"Content-Type": "application/json", "User-Agent": "BolaoSync/1.0", **_auth_headers()},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode())


def update_bolao_teams(game_id: int, team_a: str, team_b: str) -> dict:
    """PUT /games/<id> renomeando os times (placeholder -> time real)."""
    body = json.dumps({"team_a": team_a, "team_b": team_b}).encode()
    req = urllib.request.Request(
        f"{BOLAO_API}/games/{game_id}",
        data=body,
        headers={"Content-Type": "application/json", "User-Agent": "BolaoSync/1.0", **_auth_headers()},
        method="PUT",
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode())


def create_games_from_espn(dates_param: str, dry_run: bool = False, allow_past: bool = False) -> list[dict]:
    """Importa TODOS os eventos da ESPN no período como jogos no bolão,
    inclusive aqueles cujos times ainda são placeholders.
    Usa espn_id como chave de dedupe (o próprio endpoint já dedupe por espn_id).

    Proteção: por padrão NÃO cria jogos passados (kickoff < agora) para evitar
    duplicar/partilhar jogos de produção já com placar. Use allow_past=True
    (CLI --allow-past) só em casos excepcionais."""
    events = fetch_espn_events_raw(dates_param)
    results = []
    to_import = []
    now = datetime.now(BRT_TZ)
    skipped_past = 0

    for event in events:
        parsed = parse_espn_event(event)
        if not parsed:
            continue
        home_pt = parsed["home"]["name_pt"]
        away_pt = parsed["away"]["name_pt"]
        kickoff = _espn_date_to_brt_iso(parsed.get("date"))
        espn_id = parsed.get("espn_id") or None
        if not kickoff:
            continue
        # 🔒 Proteção de produção: ignora jogos passados a menos que allow_past.
        try:
            ko_dt = datetime.fromisoformat(kickoff).replace(tzinfo=BRT_TZ)
        except Exception:
            ko_dt = None
        if ko_dt and ko_dt < now and not allow_past:
            skipped_past += 1
            continue
        is_placeholder = home_pt == parsed["home"]["name_en"] or away_pt == parsed["away"]["name_en"]
        tag = " (placeholder)" if is_placeholder else ""
        log.info(f"➕ {home_pt} x {away_pt}{tag} — {kickoff} (espn_id={espn_id})")
        to_import.append({
            "kickoff": kickoff,
            "team_a": home_pt,
            "team_b": away_pt,
            "espn_id": espn_id,
        })
        results.append({"home": home_pt, "away": away_pt, "kickoff": kickoff, "espn_id": espn_id, "action": "queued"})

    if dry_run:
        log.info(f"🔧 [DRY-RUN] Importaria {len(to_import)} jogo(s)." +
                 (f" ({skipped_past} passado(s) ignorado(s))." if skipped_past else ""))
        return results

    if not to_import:
        log.info("Nenhum evento para importar." +
                 (f" ({skipped_past} passado(s) ignorado(s))." if skipped_past else ""))
        return results

    summary = import_bolao_games(to_import)
    log.info(f"💾 Importação: {summary}")
    for r in results:
        r["action"] = "imported"
        r["summary"] = summary
    return results


def _expand_espn_dates(dates_param: str) -> list[str]:
    """Expande dates_param (data única ou range INICIO-FIM) em lista de datas
    ESPN (8 dígitos) INCLUINDO o dia anterior de cada data.

    A ESPN classifica cada evento pelo dia em timezone *Eastern* (EDT/EST),
    que pode ser UM DIA ATRÁS do dia em Brasília para jogos nas primeiras
    horas do dia BRT (ex.: 03/07 00:00 BRT = 02/07 23:00 EDT -> a ESPN
    lista no dia 02/07). Como o casamento é por espn_id (chave estável),
    buscar datas a mais é seguro (nunca renomeia o jogo errado).
    """
    dates_param = dates_param.strip()
    out: set[str] = set()

    def _add_with_prev(d0):
        out.add(d0.strftime("%Y%m%d"))
        out.add((d0 - timedelta(days=1)).strftime("%Y%m%d"))

    if "-" in dates_param:
        parts = dates_param.split("-")
        # Range "20260628-20260720" (2 partes de 8 dígitos) vs
        # data ISO "2026-07-03" (3 partes).
        if len(parts) == 2 and len(parts[0]) == 8 and len(parts[1]) == 8:
            try:
                d0 = datetime.strptime(parts[0], "%Y%m%d").date()
                d1 = datetime.strptime(parts[1], "%Y%m%d").date()
                cur = d0
                while cur <= d1:
                    _add_with_prev(cur)
                    cur += timedelta(days=1)
            except ValueError:
                out.add(parts[0])
        else:
            single = dates_param.replace("-", "")
            try:
                _add_with_prev(datetime.strptime(single, "%Y%m%d").date())
            except ValueError:
                out.add(single)
    else:
        try:
            _add_with_prev(datetime.strptime(dates_param, "%Y%m%d").date())
        except ValueError:
            out.add(dates_param)
    return sorted(out)


def resolve_team_names(bolao_games: list[dict], dates_param: str, dry_run: bool = False) -> list[dict]:
    """Renomeia placeholders no bolão quando a ESPN já definiu os times reais.
    Casa por espn_id (chave estável) e atualiza team_a/team_b via PUT."""
    # Busca datas expandidas (inclui o dia anterior — ver _expand_espn_dates)
    # porque a ESPN classifica eventos pelo dia em timezone Eastern, que pode
    # ser um dia atrás do dia em Brasília. Dedupe por espn_id para evitar
    # reprocessar o mesmo evento retornado em datas adjacentes.
    events = []
    seen_ids = set()
    for ds in _expand_espn_dates(dates_param):
        try:
            evs = fetch_espn_events_raw(ds)
        except Exception as e:
            log.error(f"ESPN {ds}: {e}")
            continue
        for ev in evs:
            eid = str(ev.get("id", ""))
            if eid and eid in seen_ids:
                continue
            if eid:
                seen_ids.add(eid)
            events.append(ev)
    results = []
    for event in events:
        parsed = parse_espn_event(event)
        if not parsed:
            continue
        espn_id = parsed.get("espn_id")
        match = find_bolao_match_by_espn(bolao_games, espn_id)
        if not match:
            continue
        home_pt = parsed["home"]["name_pt"]
        away_pt = parsed["away"]["name_pt"]
        # Só renomeia se algum lado mudou (placeholder -> real).
        if match["team_a"] == home_pt and match["team_b"] == away_pt:
            continue
        # Ignora placares já definidos (jogo real já travado).
        if match.get("score_a") is not None:
            continue
        log.info(
            f"🔁 Renomeando jogo {match['id']}: "
            f"{match['team_a']} x {match['team_b']} -> {home_pt} x {away_pt}"
        )
        action = "would_rename" if dry_run else "renamed"
        if not dry_run:
            try:
                update_bolao_teams(match["id"], home_pt, away_pt)
                match["team_a"] = home_pt
                match["team_b"] = away_pt
            except Exception as e:
                log.error(f"❌ Erro ao renomear jogo {match['id']}: {e}")
                action = "error"
        results.append({
            "game_id": match["id"],
            "from": f"{match['team_a']} x {match['team_b']}",
            "to": f"{home_pt} x {away_pt}",
            "action": action,
        })
    return results

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

        # Só atualiza se o jogo foi completamente finalizado (FT/AET/FT-Pens)
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

        # Procura no bolão: primeiro pela chave estável espn_id (mata-mata,
        # onde os nomes mudam de placeholder -> time real); depois por nome.
        match = find_bolao_match_by_espn(bolao_games, parsed.get("espn_id"))
        if not match:
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
    # Primeiro resolve nomes de placeholders (mata-mata) para essas datas.
    # A ESPN já pode ter definido os times reais; renomeia antes do placar.
    name_results = []
    for d in sorted(dates):
        name_results.extend(resolve_team_names(bolao_games, d, dry_run=dry_run))
    renamed = sum(1 for r in name_results if r.get("action") == "renamed")
    if renamed:
        log.info(f"🔁 {renamed} jogo(s) renomeado(s) (placeholder -> time real)")
    all_results.extend(name_results)

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
    parser.add_argument("--create-games", action="store_true",
                        help="Importa jogos da ESPN (inclusive placeholders de mata-mata). "
                             "Use com --date DD ou --create-range INICIO-FIM")
    parser.add_argument("--create-range", metavar="INICIO-FIM",
                        help="Range de datas ESPN (ex: 20260628-20260720) para --create-games/--update-names")
    parser.add_argument("--update-names", action="store_true",
                        help="Só renomeia placeholders -> times reais (casa por espn_id). "
                             "Use com --date DD ou --create-range INICIO-FIM")
    parser.add_argument("--allow-past", action="store_true",
                        help="Permite criar/renomear jogos passados com --create-games/--update-names "
                             "(por padrão jogos passados são protegidos). NUNCA sobrescreve placares.")
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

    # Define o parâmetro de datas ESPN para os modos create/update
    espn_dates = args.create_range or (args.date.replace("-", "") if args.date else None)

    # Modo criar jogos (importa mata-mata, inclusive placeholders)
    if args.create_games:
        if not espn_dates:
            log.error("❌ --create-games exige --date DD ou --create-range INICIO-FIM")
            sys.exit(1)
        # Importar exige token de admin
        if not ADMIN_TOKEN:
            log.error("❌ --create-games exige --token, --login USER PASS ou BOLAO_ADMIN_TOKEN")
            sys.exit(1)
        results = create_games_from_espn(espn_dates, dry_run=args.dry_run, allow_past=args.allow_past)
        imported = results and results[0].get("summary", {}).get("imported", 0)
        log.info(f"\n{'='*40}")
        log.info(f"Criação de jogos: {len(results)} evento(s) processado(s).")
        log.info(f"{'='*40}")
        if results:
            print(json.dumps(results, ensure_ascii=False, indent=2))
        return

    # Busca jogos do bolão
    log.info(f"Conectando ao bolão: {BOLAO_API}/games")
    try:
        bolao_games = fetch_bolao_games()
    except Exception as e:
        log.error(f"Não conseguiu conectar ao bolão: {e}")
        sys.exit(1)

    log.info(f"{len(bolao_games)} jogos no bolão, {sum(1 for g in bolao_games if g.get('score_a') is None)} sem placar")

    # Modo só renomear placeholders
    if args.update_names:
        if not espn_dates:
            log.error("❌ --update-names exige --date DD ou --create-range INICIO-FIM")
            sys.exit(1)
        results = resolve_team_names(bolao_games, espn_dates, dry_run=args.dry_run)
        renamed = sum(1 for r in results if r.get("action") == "renamed")
        log.info(f"\n{'='*40}")
        log.info(f"Nomes atualizados: {renamed}")
        log.info(f"{'='*40}")
        if results:
            print(json.dumps(results, ensure_ascii=False, indent=2))
        return

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
