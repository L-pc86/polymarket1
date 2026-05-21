#!/usr/bin/env python3
"""
Find Polymarket football event IDs by Chinese team names.

The script uses Polymarket's public Gamma API only:
  - GET /teams
  - GET /public-search
  - GET /events

No API key is required.
"""

from __future__ import annotations

import argparse
import json
import sys
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


GAMMA_API = "https://gamma-api.polymarket.com"
DEFAULT_LIMIT = 10


# Polymarket's team and event data is normally English. Keep this map small and
# practical, and extend aliases_zh.json for teams you query often.
BUILTIN_ALIASES: dict[str, list[str]] = {
    "阿森纳": ["Arsenal"],
    "维拉": ["Aston Villa"],
    "阿斯顿维拉": ["Aston Villa"],
    "伯恩茅斯": ["Bournemouth"],
    "布伦特福德": ["Brentford"],
    "布莱顿": ["Brighton", "Brighton & Hove Albion"],
    "切尔西": ["Chelsea"],
    "水晶宫": ["Crystal Palace"],
    "埃弗顿": ["Everton"],
    "富勒姆": ["Fulham"],
    "利物浦": ["Liverpool"],
    "曼城": ["Manchester City", "Man City"],
    "曼彻斯特城": ["Manchester City", "Man City"],
    "曼联": ["Manchester United", "Man United"],
    "曼彻斯特联": ["Manchester United", "Man United"],
    "纽卡": ["Newcastle", "Newcastle United"],
    "纽卡斯尔": ["Newcastle", "Newcastle United"],
    "诺丁汉森林": ["Nottingham Forest"],
    "热刺": ["Tottenham", "Tottenham Hotspur", "Spurs"],
    "托特纳姆热刺": ["Tottenham", "Tottenham Hotspur", "Spurs"],
    "西汉姆": ["West Ham", "West Ham United"],
    "狼队": ["Wolves", "Wolverhampton Wanderers"],
    "巴萨": ["Barcelona", "FC Barcelona"],
    "巴塞罗那": ["Barcelona", "FC Barcelona"],
    "皇马": ["Real Madrid"],
    "皇家马德里": ["Real Madrid"],
    "马竞": ["Atletico Madrid", "Atlético Madrid"],
    "马德里竞技": ["Atletico Madrid", "Atlético Madrid"],
    "拜仁": ["Bayern Munich", "FC Bayern Munich"],
    "拜仁慕尼黑": ["Bayern Munich", "FC Bayern Munich"],
    "多特": ["Borussia Dortmund", "Dortmund"],
    "多特蒙德": ["Borussia Dortmund", "Dortmund"],
    "巴黎": ["PSG", "Paris Saint-Germain", "Paris SG"],
    "巴黎圣日耳曼": ["PSG", "Paris Saint-Germain", "Paris SG"],
    "尤文": ["Juventus"],
    "尤文图斯": ["Juventus"],
    "国米": ["Inter Milan", "Internazionale"],
    "国际米兰": ["Inter Milan", "Internazionale"],
    "米兰": ["AC Milan"],
    "ac米兰": ["AC Milan"],
    "罗马": ["Roma", "AS Roma"],
    "那不勒斯": ["Napoli", "Naples"],
    "葡萄牙": ["Portugal"],
    "西班牙": ["Spain"],
    "法国": ["France"],
    "德国": ["Germany"],
    "英格兰": ["England"],
    "阿根廷": ["Argentina"],
    "巴西": ["Brazil"],
    "意大利": ["Italy"],
    "荷兰": ["Netherlands", "Holland"],
}


@dataclass(frozen=True)
class Candidate:
    id: str
    title: str
    slug: str
    start: str
    active: bool | None
    closed: bool | None
    score: float
    matched_terms: list[str]


def normalize(value: str | None) -> str:
    value = unicodedata.normalize("NFKC", value or "")
    return " ".join(value.casefold().replace("&", " and ").split())


def load_aliases(path: Path) -> dict[str, list[str]]:
    aliases = {k: list(v) for k, v in BUILTIN_ALIASES.items()}
    if not path.exists():
        return aliases

    with path.open("r", encoding="utf-8") as f:
        custom = json.load(f)
    for key, values in custom.items():
        if isinstance(values, str):
            values = [values]
        aliases.setdefault(key, [])
        for value in values:
            if value not in aliases[key]:
                aliases[key].append(value)
    return aliases


def http_get(path: str, params: dict[str, Any] | None = None) -> Any:
    query = urlencode(params or {}, doseq=True)
    url = f"{GAMMA_API}{path}"
    if query:
        url = f"{url}?{query}"

    request = Request(url, headers={"User-Agent": "polymarket-football-id-script/1.0"})
    try:
        with urlopen(request, timeout=20) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Polymarket API HTTP {exc.code}: {body}") from exc
    except URLError as exc:
        raise RuntimeError(f"无法连接 Polymarket API: {exc.reason}") from exc


def resolve_team_terms(team_zh: str, aliases: dict[str, list[str]]) -> list[str]:
    raw = team_zh.strip()
    terms = [raw]
    for value in aliases.get(raw, []):
        if value not in terms:
            terms.append(value)

    # Confirm or enrich candidates through the official teams endpoint.
    for term in list(terms):
        try:
            teams = http_get("/teams", {"name": term, "limit": 20})
        except RuntimeError:
            continue
        if not isinstance(teams, list):
            continue
        for team in teams:
            for field in ("name", "abbreviation", "alias"):
                value = team.get(field)
                if value and len(normalize(value)) < 3:
                    continue
                if value and value not in terms:
                    terms.append(value)
    return terms


def event_text(event: dict[str, Any]) -> str:
    pieces = [
        event.get("title"),
        event.get("subtitle"),
        event.get("description"),
        event.get("slug"),
        event.get("category"),
        event.get("subcategory"),
        event.get("gameId"),
    ]
    participants = event.get("participants")
    if isinstance(participants, list):
        for participant in participants:
            if isinstance(participant, dict):
                pieces.extend(str(v) for v in participant.values() if v)
            elif participant:
                pieces.append(str(participant))
    return " ".join(str(piece) for piece in pieces if piece)


def looks_like_football(event: dict[str, Any]) -> bool:
    text = normalize(event_text(event))
    football_markers = (
        "soccer",
        "football",
        "epl",
        "premier league",
        "la liga",
        "serie a",
        "bundesliga",
        "champions league",
        "europa league",
        "world cup",
        "uefa",
        "fifa",
        "mls",
    )
    # Avoid American football false positives when possible.
    non_soccer_markers = (
        "nfl",
        "super bowl",
        "college football",
        "rocket league",
        " esports",
        "rlcs",
        "counter-strike",
        "dota",
        "league of legends",
        "valorant",
    )
    return any(marker in text for marker in football_markers) and not any(
        marker in text for marker in non_soccer_markers
    )


def parse_date(value: str | None) -> datetime:
    if not value:
        return datetime.max.replace(tzinfo=timezone.utc)
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return datetime.max.replace(tzinfo=timezone.utc)


def score_event(event: dict[str, Any], team_terms: list[str]) -> tuple[float, list[str]]:
    text = normalize(event_text(event))
    title = normalize(str(event.get("title") or event.get("ticker") or ""))
    matched: list[str] = []
    score = 0.0

    for term in team_terms:
        nterm = normalize(term)
        if not nterm:
            continue
        if nterm in text:
            matched.append(term)
            score += 10 + min(len(nterm) / 4, 5)
        else:
            ratio = SequenceMatcher(None, nterm, text).ratio()
            if ratio > 0.18:
                score += ratio

    if looks_like_football(event):
        score += 5
    if " vs " in title or " v " in title:
        score += 12
    prop_markers = (
        " next ",
        " manager",
        " coach",
        " break the",
        " record",
        " score a goal",
        " assists",
        " transfer",
        " sign for",
        " win the league",
        " win champions league",
    )
    if any(marker in f" {title} " for marker in prop_markers):
        score -= 8
    if title.startswith("will ") and " vs " not in title and " v " not in title:
        score -= 6
    if event.get("active") is True:
        score += 2
    if event.get("closed") is False:
        score += 1
    if event.get("archived") is True:
        score -= 4
    if event.get("closed") is True:
        score -= 2

    return score, matched


def collect_events(team_terms: list[str], include_closed: bool, limit: int) -> list[dict[str, Any]]:
    events_by_id: dict[str, dict[str, Any]] = {}
    status_values = ["active"]
    if include_closed:
        status_values.append("all")

    for term in team_terms:
        for status in status_values:
            data = http_get(
                "/public-search",
                {
                    "q": term,
                    "events_status": status,
                    "limit_per_type": max(limit, 10),
                    "search_profiles": "false",
                    "search_tags": "false",
                },
            )
            for event in data.get("events") or []:
                if event.get("id"):
                    events_by_id[str(event["id"])] = event

    # Fallback: active sports events sometimes appear better through /events.
    for params in (
        {"active": "true", "closed": "false", "limit": 100, "category": "sports"},
        {"active": "true", "closed": "false", "limit": 100, "categories": "sports"},
    ):
        try:
            data = http_get("/events", params)
        except RuntimeError:
            continue
        events = data if isinstance(data, list) else data.get("data") or data.get("events") or []
        for event in events:
            if event.get("id"):
                events_by_id.setdefault(str(event["id"]), event)

    return list(events_by_id.values())


def find_matches(team_zh: str, include_closed: bool, limit: int, alias_file: Path) -> list[Candidate]:
    aliases = load_aliases(alias_file)
    team_terms = resolve_team_terms(team_zh, aliases)
    events = collect_events(team_terms, include_closed, limit)

    candidates: list[Candidate] = []
    for event in events:
        if not looks_like_football(event):
            continue
        score, matched_terms = score_event(event, team_terms)
        if not matched_terms:
            continue
        if not include_closed and event.get("closed") is True:
            continue
        candidates.append(
            Candidate(
                id=str(event.get("id", "")),
                title=str(event.get("title") or event.get("ticker") or ""),
                slug=str(event.get("slug") or ""),
                start=str(event.get("startDate") or event.get("eventStartTime") or ""),
                active=event.get("active"),
                closed=event.get("closed"),
                score=score,
                matched_terms=matched_terms,
            )
        )

    candidates.sort(key=lambda item: (-item.score, parse_date(item.start), item.title))
    return candidates[:limit]


def print_human(candidates: list[Candidate]) -> None:
    if not candidates:
        print("未找到匹配的足球比赛。可以尝试：")
        print("1. 使用球队更常见的中文简称，例如：曼城、皇马、巴黎。")
        print("2. 在 aliases_zh.json 里补充中文名到英文名的映射。")
        print("3. 加上 --include-closed 查询已结束比赛。")
        return

    best = candidates[0]
    print(best.id)
    print()
    print("最佳匹配：")
    print(f"- event_id: {best.id}")
    print(f"- title: {best.title}")
    print(f"- slug: {best.slug}")
    print(f"- start: {best.start or '未知'}")
    print(f"- active: {best.active}, closed: {best.closed}")
    print(f"- matched_terms: {', '.join(best.matched_terms)}")

    if len(candidates) > 1:
        print()
        print("其他可能匹配：")
        for item in candidates[1:]:
            print(f"- {item.id} | {item.title} | {item.start or '未知'} | {item.slug}")


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="通过 Polymarket 官方 API 查询足球比赛 event id")
    parser.add_argument("team", nargs="?", help="球队中文名，例如：曼城、皇马、巴黎")
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT, help="返回候选数量，默认 10")
    parser.add_argument("--include-closed", action="store_true", help="包含已结束/关闭的比赛")
    parser.add_argument("--json", action="store_true", help="以 JSON 输出候选结果")
    parser.add_argument(
        "--alias-file",
        default="aliases_zh.json",
        help="中文别名映射文件路径，默认 aliases_zh.json",
    )
    args = parser.parse_args()

    team = args.team or input("请输入球队中文名字：").strip()
    if not team:
        print("球队名不能为空。", file=sys.stderr)
        return 2

    try:
        candidates = find_matches(team, args.include_closed, args.limit, Path(args.alias_file))
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps([candidate.__dict__ for candidate in candidates], ensure_ascii=False, indent=2))
    else:
        print_human(candidates)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
