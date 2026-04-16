from starlette.applications import Starlette
from starlette.routing import Route, Mount
from starlette.responses import JSONResponse
import uvicorn
import threading
from fastmcp import FastMCP
import httpx
import os
from typing import Optional, Any

mcp = FastMCP("ESPN Sports Data Service")

ESPN_SITE_API = "https://site.api.espn.com"
ESPN_CORE_API = "https://sports.core.api.espn.com"
ESPN_WEB_V3_API = "https://site.web.api.espn.com"
ESPN_CDN_API = "https://cdn.espn.com"
ESPN_NOW_API = "https://now.core.api.espn.com"

DEFAULT_HEADERS = {
    "User-Agent": "ESPN-Service/1.0",
    "Accept": "application/json",
}


async def espn_get(url: str, params: Optional[dict] = None) -> Any:
    """Helper to perform a GET request against ESPN APIs."""
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.get(url, params=params, headers=DEFAULT_HEADERS)
        response.raise_for_status()
        return response.json()


# ─── Scoreboard ────────────────────────────────────────────────────────────────

@mcp.tool()
async def get_scoreboard(
    sport: str,
    league: str,
    dates: Optional[str] = None,
    week: Optional[int] = None,
    seasontype: Optional[int] = None,
    limit: Optional[int] = None,
) -> dict:
    """
    Fetch the live or historical scoreboard for a sport/league.

    Args:
        sport: Sport slug, e.g. 'football', 'basketball', 'baseball', 'hockey', 'soccer'.
        league: League slug, e.g. 'nfl', 'nba', 'mlb', 'nhl', 'eng.1' (Premier League).
        dates: Optional date filter in YYYYMMDD or YYYYMMDD-YYYYMMDD format.
        week: Optional NFL/NCAAF week number.
        seasontype: Optional season type (1=pre, 2=regular, 3=post).
        limit: Optional max number of events returned.

    Returns:
        Scoreboard JSON with events, scores, and game statuses.
    """
    url = f"{ESPN_SITE_API}/apis/site/v2/sports/{sport}/{league}/scoreboard"
    params: dict = {}
    if dates:
        params["dates"] = dates
    if week is not None:
        params["week"] = week
    if seasontype is not None:
        params["seasontype"] = seasontype
    if limit is not None:
        params["limit"] = limit
    return await espn_get(url, params or None)


# ─── Teams ─────────────────────────────────────────────────────────────────────

@mcp.tool()
async def get_teams(sport: str, league: str, limit: Optional[int] = 1000) -> dict:
    """
    List all teams for a given sport and league.

    Args:
        sport: Sport slug, e.g. 'football', 'basketball'.
        league: League slug, e.g. 'nfl', 'nba'.
        limit: Max number of teams to return (default 1000).

    Returns:
        JSON with a list of teams including IDs, names, abbreviations, and logos.
    """
    url = f"{ESPN_SITE_API}/apis/site/v2/sports/{sport}/{league}/teams"
    return await espn_get(url, {"limit": limit})


@mcp.tool()
async def get_team(
    sport: str,
    league: str,
    team_id_or_slug: str,
    enable: Optional[str] = None,
) -> dict:
    """
    Fetch detailed information for a specific team.

    Args:
        sport: Sport slug.
        league: League slug.
        team_id_or_slug: Numeric team ID or team abbreviation/slug (e.g. '12' or 'ne').
        enable: Comma-separated extras to include, e.g. 'roster,schedule,record,injuries'.

    Returns:
        Team detail JSON including roster, stats, record, and schedule links.
    """
    url = f"{ESPN_SITE_API}/apis/site/v2/sports/{sport}/{league}/teams/{team_id_or_slug}"
    params: dict = {}
    if enable:
        params["enable"] = enable
    return await espn_get(url, params or None)


# ─── Standings ─────────────────────────────────────────────────────────────────

@mcp.tool()
async def get_standings(
    sport: str,
    league: str,
    season: Optional[int] = None,
    seasontype: Optional[int] = None,
    group: Optional[str] = None,
) -> dict:
    """
    Fetch current or historical standings for a league.

    Args:
        sport: Sport slug.
        league: League slug.
        season: Optional 4-digit year (e.g. 2024).
        seasontype: Optional season type (2=regular season).
        group: Optional group/division filter.

    Returns:
        Standings JSON with win/loss records, points, and rankings.
    """
    url = f"{ESPN_SITE_API}/apis/v2/sports/{sport}/{league}/standings"
    params: dict = {}
    if season is not None:
        params["season"] = season
    if seasontype is not None:
        params["seasontype"] = seasontype
    if group:
        params["group"] = group
    return await espn_get(url, params or None)


# ─── News ──────────────────────────────────────────────────────────────────────

@mcp.tool()
async def get_news(
    sport: str,
    league: str,
    team_id: Optional[str] = None,
    athlete_id: Optional[str] = None,
    limit: Optional[int] = 10,
) -> dict:
    """
    Retrieve the latest news articles for a sport/league, optionally filtered by team or athlete.

    Args:
        sport: Sport slug.
        league: League slug.
        team_id: Optional team ID to filter news.
        athlete_id: Optional athlete ID to filter news.
        limit: Max number of articles to return (default 10).

    Returns:
        News JSON with headlines, descriptions, links, and publish dates.
    """
    url = f"{ESPN_SITE_API}/apis/site/v2/sports/{sport}/{league}/news"
    params: dict = {"limit": limit}
    if team_id:
        params["team"] = team_id
    if athlete_id:
        params["athlete"] = athlete_id
    return await espn_get(url, params)


# ─── Game Summary ──────────────────────────────────────────────────────────────

@mcp.tool()
async def get_game_summary(sport: str, league: str, event_id: str) -> dict:
    """
    Get the full summary for a specific game/event including box score, play-by-play links,
    scoring summary, and game info.

    Args:
        sport: Sport slug.
        league: League slug.
        event_id: ESPN event/game ID (found in scoreboard results).

    Returns:
        Game summary JSON with teams, scores, leaders, and game details.
    """
    url = f"{ESPN_SITE_API}/apis/site/v2/sports/{sport}/{league}/summary"
    return await espn_get(url, {"event": event_id})


# ─── Injuries ──────────────────────────────────────────────────────────────────

@mcp.tool()
async def get_injuries(sport: str, league: str, team_id: Optional[str] = None) -> dict:
    """
    Retrieve the current injury report for a league or a specific team.

    Args:
        sport: Sport slug.
        league: League slug.
        team_id: Optional team ID to filter injuries to one team.

    Returns:
        Injury report JSON with player names, statuses, and descriptions.
    """
    url = f"{ESPN_SITE_API}/apis/v2/sports/{sport}/{league}/injuries"
    params: dict = {}
    if team_id:
        params["team"] = team_id
    return await espn_get(url, params or None)


# ─── Athletes ──────────────────────────────────────────────────────────────────

@mcp.tool()
async def get_athlete(sport: str, league: str, athlete_id: str) -> dict:
    """
    Fetch detailed profile information for a specific athlete.

    Args:
        sport: Sport slug.
        league: League slug.
        athlete_id: ESPN athlete ID.

    Returns:
        Athlete profile JSON including bio, position, team, and college.
    """
    url = f"{ESPN_SITE_API}/apis/site/v2/sports/{sport}/{league}/athletes/{athlete_id}"
    return await espn_get(url)


@mcp.tool()
async def search_athletes(
    sport: str,
    league: str,
    query: str,
    limit: Optional[int] = 10,
) -> dict:
    """
    Search for athletes by name within a sport and league.

    Args:
        sport: Sport slug.
        league: League slug.
        query: Player name search string.
        limit: Max results to return.

    Returns:
        JSON list of matching athletes with IDs, names, and team info.
    """
    url = f"{ESPN_CORE_API}/v2/sports/{sport}/{league}/athletes"
    return await espn_get(url, {"limit": limit, "search": query})


# ─── Athlete Stats ─────────────────────────────────────────────────────────────

@mcp.tool()
async def get_athlete_stats(
    sport: str,
    league: str,
    athlete_id: str,
    season: Optional[int] = None,
    seasontype: Optional[int] = None,
) -> dict:
    """
    Retrieve season statistics for a specific athlete.

    Args:
        sport: Sport slug.
        league: League slug.
        athlete_id: ESPN athlete ID.
        season: Optional 4-digit year.
        seasontype: Optional season type (2=regular).

    Returns:
        Athlete stats JSON with per-game and total statistics.
    """
    url = f"{ESPN_WEB_V3_API}/apis/common/v3/sports/{sport}/{league}/athletes/{athlete_id}/stats"
    params: dict = {}
    if season is not None:
        params["season"] = season
    if seasontype is not None:
        params["seasontype"] = seasontype
    return await espn_get(url, params or None)


@mcp.tool()
async def get_athlete_gamelog(
    sport: str,
    league: str,
    athlete_id: str,
    season: Optional[int] = None,
    seasontype: Optional[int] = None,
) -> dict:
    """
    Retrieve the game-by-game log for a specific athlete.

    Args:
        sport: Sport slug.
        league: League slug.
        athlete_id: ESPN athlete ID.
        season: Optional 4-digit year.
        seasontype: Optional season type (2=regular).

    Returns:
        Gamelog JSON with stats for each game played.
    """
    url = f"{ESPN_WEB_V3_API}/apis/common/v3/sports/{sport}/{league}/athletes/{athlete_id}/gamelog"
    params: dict = {}
    if season is not None:
        params["season"] = season
    if seasontype is not None:
        params["seasontype"] = seasontype
    return await espn_get(url, params or None)


# ─── Schedule ──────────────────────────────────────────────────────────────────

@mcp.tool()
async def get_schedule(
    sport: str,
    league: str,
    team_id: Optional[str] = None,
    dates: Optional[str] = None,
    season: Optional[int] = None,
    seasontype: Optional[int] = None,
    week: Optional[int] = None,
    limit: Optional[int] = 50,
) -> dict:
    """
    Retrieve the game schedule for a league or a specific team.

    Args:
        sport: Sport slug.
        league: League slug.
        team_id: Optional team ID to get only that team's schedule.
        dates: Optional date or range in YYYYMMDD or YYYYMMDD-YYYYMMDD format.
        season: Optional 4-digit year.
        seasontype: Optional season type.
        week: Optional week number (NFL/NCAAF).
        limit: Max number of games to return.

    Returns:
        Schedule JSON with upcoming and past game information.
    """
    url = f"{ESPN_SITE_API}/apis/site/v2/sports/{sport}/{league}/scoreboard"
    params: dict = {"limit": limit}
    if team_id:
        # ESPN scoreboard filtered by team
        url = f"{ESPN_SITE_API}/apis/site/v2/sports/{sport}/{league}/teams/{team_id}/schedule"
        params = {}
    if dates:
        params["dates"] = dates
    if season is not None:
        params["season"] = season
    if seasontype is not None:
        params["seasontype"] = seasontype
    if week is not None:
        params["week"] = week
    return await espn_get(url, params or None)


# ─── Leaders / Stats Leaders ───────────────────────────────────────────────────

@mcp.tool()
async def get_leaders(
    sport: str,
    league: str,
    season: Optional[int] = None,
    seasontype: Optional[int] = None,
    limit: Optional[int] = 10,
) -> dict:
    """
    Fetch statistical leaders (top performers) for a league.

    Args:
        sport: Sport slug.
        league: League slug.
        season: Optional 4-digit year.
        seasontype: Optional season type.
        limit: Max number of leaders per category.

    Returns:
        Leaders JSON with categories and top athletes and their stats.
    """
    url = f"{ESPN_SITE_API}/apis/site/v2/sports/{sport}/{league}/leaders"
    params: dict = {"limit": limit}
    if season is not None:
        params["season"] = season
    if seasontype is not None:
        params["seasontype"] = seasontype
    return await espn_get(url, params)


# ─── Odds ──────────────────────────────────────────────────────────────────────

@mcp.tool()
async def get_event_odds(sport: str, league: str, event_id: str) -> dict:
    """
    Fetch betting odds for a specific event/game.

    Args:
        sport: Sport slug.
        league: League slug.
        event_id: ESPN event/game ID.

    Returns:
        Odds JSON with spread, money line, and over/under from multiple providers.
    """
    url = f"{ESPN_CORE_API}/v2/sports/{sport}/{league}/events/{event_id}/competitions/{event_id}/odds"
    return await espn_get(url)


# ─── Play-by-Play ──────────────────────────────────────────────────────────────

@mcp.tool()
async def get_play_by_play(sport: str, league: str, event_id: str) -> dict:
    """
    Retrieve play-by-play data for a specific game/event.

    Args:
        sport: Sport slug.
        league: League slug.
        event_id: ESPN event/game ID.

    Returns:
        Play-by-play JSON with individual plays, clock, scores, and participants.
    """
    url = f"{ESPN_CDN_API}/core/{sport}/{league}/playbyplay"
    return await espn_get(url, {"event": event_id, "enable": "plays,homeAway"})


# ─── Transactions ──────────────────────────────────────────────────────────────

@mcp.tool()
async def get_transactions(
    sport: str,
    league: str,
    team_id: Optional[str] = None,
    dates: Optional[str] = None,
    limit: Optional[int] = 25,
) -> dict:
    """
    Fetch recent transactions (trades, signings, waivers) for a league.

    Args:
        sport: Sport slug.
        league: League slug.
        team_id: Optional team ID to filter transactions.
        dates: Optional date filter in YYYYMMDD format.
        limit: Max number of transactions to return.

    Returns:
        Transactions JSON with player movements and descriptions.
    """
    url = f"{ESPN_SITE_API}/apis/site/v2/sports/{sport}/{league}/transactions"
    params: dict = {"limit": limit}
    if team_id:
        params["team"] = team_id
    if dates:
        params["dates"] = dates
    return await espn_get(url, params)


# ─── Roster ────────────────────────────────────────────────────────────────────

@mcp.tool()
async def get_team_roster(
    sport: str,
    league: str,
    team_id: str,
    season: Optional[int] = None,
) -> dict:
    """
    Retrieve the full roster for a specific team.

    Args:
        sport: Sport slug.
        league: League slug.
        team_id: ESPN team ID or abbreviation.
        season: Optional 4-digit year.

    Returns:
        Roster JSON with athlete names, numbers, positions, and status.
    """
    url = f"{ESPN_SITE_API}/apis/site/v2/sports/{sport}/{league}/teams/{team_id}/roster"
    params: dict = {}
    if season is not None:
        params["season"] = season
    return await espn_get(url, params or None)


# ─── Events (Core API) ─────────────────────────────────────────────────────────

@mcp.tool()
async def get_events(
    sport: str,
    league: str,
    dates: Optional[str] = None,
    week: Optional[int] = None,
    season: Optional[int] = None,
    seasontype: Optional[int] = None,
    limit: Optional[int] = 100,
) -> dict:
    """
    List events (games) via the ESPN Core API with richer metadata.

    Args:
        sport: Sport slug.
        league: League slug.
        dates: Optional date or date range in YYYYMMDD or YYYYMMDD-YYYYMMDD.
        week: Optional week number.
        season: Optional 4-digit year.
        seasontype: Optional season type.
        limit: Max number of events to return.

    Returns:
        Events JSON from the Core API with full game metadata.
    """
    url = f"{ESPN_CORE_API}/v2/sports/{sport}/{league}/events"
    params: dict = {"limit": limit}
    if dates:
        params["dates"] = dates
    if week is not None:
        params["week"] = week
    if season is not None:
        params["season"] = season
    if seasontype is not None:
        params["seasontype"] = seasontype
    return await espn_get(url, params)


# ─── Now (Real-time News Feed) ─────────────────────────────────────────────────

@mcp.tool()
async def get_now_feed(
    sport: Optional[str] = None,
    league: Optional[str] = None,
    limit: Optional[int] = 20,
    page: Optional[int] = 1,
) -> dict:
    """
    Fetch the ESPN 'Now' real-time news and headlines feed.

    Args:
        sport: Optional sport slug to filter feed.
        league: Optional league slug to filter feed.
        limit: Max number of items per page.
        page: Page number for pagination.

    Returns:
        Real-time feed JSON with breaking news, scores updates, and alerts.
    """
    url = f"{ESPN_NOW_API}/v1/now"
    params: dict = {"limit": limit, "page": page}
    if sport:
        params["sport"] = sport
    if league:
        params["league"] = league
    return await espn_get(url, params)


# ─── Athlete Overview ──────────────────────────────────────────────────────────

@mcp.tool()
async def get_athlete_overview(sport: str, league: str, athlete_id: str) -> dict:
    """
    Get a comprehensive overview for an athlete including recent stats, news, and bio.

    Args:
        sport: Sport slug.
        league: League slug.
        athlete_id: ESPN athlete ID.

    Returns:
        Athlete overview JSON combining stats, news, and game log summaries.
    """
    url = f"{ESPN_WEB_V3_API}/apis/common/v3/sports/{sport}/{league}/athletes/{athlete_id}/overview"
    return await espn_get(url)


# ─── Leagues ───────────────────────────────────────────────────────────────────

@mcp.tool()
async def list_supported_leagues() -> dict:
    """
    Return a reference list of commonly supported ESPN sport/league slug pairs.
    No network request is made — this is a static reference.

    Returns:
        Dictionary mapping sport slugs to lists of supported league slugs.
    """
    return {
        "football": ["nfl", "college-football"],
        "basketball": ["nba", "mens-college-basketball", "womens-college-basketball", "wnba"],
        "baseball": ["mlb", "college-baseball"],
        "hockey": ["nhl"],
        "soccer": [
            "eng.1",  # Premier League
            "esp.1",  # La Liga
            "ger.1",  # Bundesliga
            "ita.1",  # Serie A
            "fra.1",  # Ligue 1
            "usa.1",  # MLS
            "uefa.champions",
            "fifa.world",
        ],
        "tennis": ["atp", "wta"],
        "golf": ["pga", "lpga", "european.1"],
        "mma": ["ufc"],
        "racing": ["f1", "nascar"],
    }




_SERVER_SLUG = "public-espn-api"

def _track(tool_name: str, ua: str = ""):
    try:
        import urllib.request, json as _json
        data = _json.dumps({"slug": _SERVER_SLUG, "event": "tool_call", "tool": tool_name, "user_agent": ua}).encode()
        req = urllib.request.Request("https://www.volspan.dev/api/analytics/event", data=data, headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=1)
    except Exception:
        pass

async def health(request):
    return JSONResponse({"status": "ok", "server": mcp.name})

async def tools(request):
    registered = await mcp.list_tools()
    tool_list = [{"name": t.name, "description": t.description or ""} for t in registered]
    return JSONResponse({"tools": tool_list, "count": len(tool_list)})

mcp_app = mcp.http_app(transport="streamable-http", stateless_http=True)

class _FixAcceptHeader:
    """Ensure Accept header includes both types FastMCP requires."""
    def __init__(self, app):
        self.app = app
    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            headers = dict(scope.get("headers", []))
            accept = headers.get(b"accept", b"").decode()
            if "text/event-stream" not in accept:
                new_headers = [(k, v) for k, v in scope["headers"] if k != b"accept"]
                new_headers.append((b"accept", b"application/json, text/event-stream"))
                scope = dict(scope, headers=new_headers)
        await self.app(scope, receive, send)

app = _FixAcceptHeader(Starlette(
    routes=[
        Route("/health", health),
        Route("/tools", tools),
        Mount("/", mcp_app),
    ],
    lifespan=mcp_app.lifespan,
))

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
