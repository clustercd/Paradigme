"""Public research through DuckDuckGo, Wikipedia, Google News, YouTube, and Internet Archive."""
from __future__ import annotations
import asyncio
import html
import logging
import re
import urllib.parse as up
import unicodedata
import xml.etree.ElementTree as ET
import httpx
from typing import Any

log = logging.getLogger("paradigme.research")

_TRUSTED_DOMAINS = (
    "gouv.fr", "gov", "europa.eu", "insee.fr", "who.int",
    "un.org", "oecd.org", "wikipedia.org",
)
_SOURCE_PRIORITY = {
    "wikipedia": 0, "web": 1, "actualite": 2, "youtube": 3,
    "livre": 4, "reportage": 4, "archive_web": 5,
}


def _host_is_trusted(hostname: str | None) -> bool:
    """Return whether a normalized host is an approved institutional domain."""
    if not hostname:
        return False
    try:
        # IDNA prevents visually similar Unicode hostnames from matching a
        # trusted ASCII domain. A terminal dot is a valid DNS spelling.
        host = hostname.rstrip(".").encode("idna").decode("ascii").lower()
    except (UnicodeError, ValueError):
        return False
    return any(host == domain or host.endswith("." + domain) for domain in _TRUSTED_DOMAINS)


def _url_host(url: str) -> str | None:
    """Extract an HTTP(S) URL's actual hostname, ignoring path/query/userinfo."""
    try:
        parsed = up.urlsplit(url)
        if parsed.scheme.lower() not in ("http", "https"):
            return None
        return parsed.hostname
    except (TypeError, ValueError):
        return None


def _source_rank(item: dict) -> tuple[int, int, int]:
    """Rank sources by redirect status, verified host, then source type."""
    url = str(item.get("url", ""))
    host = _url_host(url)
    trusted = 0 if _host_is_trusted(host) else 1
    normalized_host = (host or "").lower().rstrip(".")
    redirect = int(
        normalized_host == "news.google.com"
        or normalized_host.endswith(".news.google.com")
    )
    return (redirect, trusted, _SOURCE_PRIORITY.get(item.get("source", ""), 9))

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
}


def _clean(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


_TOPIC_STOP = {
    "analyse", "avenir", "concret", "concrete", "evolution", "impact",
    "france", "belgique", "monde", "population", "situation", "actuel",
    "actuelle", "question", "rapport", "information", "informations",
}


def _topic_terms(value: str) -> set[str]:
    normalized = unicodedata.normalize("NFKD", value or "").encode("ascii", "ignore").decode().lower()
    words = re.findall(r"[a-z0-9]{3,}", normalized)
    terms = {word[:-1] if word.endswith("s") and len(word) > 4 else word for word in words}
    terms -= _TOPIC_STOP
    # Include common synonyms to avoid incorrectly rejecting relevant sources.
    if terms & {"feu", "incendie"}:
        terms.update({"feu", "incendie"})
    return terms


def _is_topic_relevant(item: dict, main_subject: str) -> bool:
    terms = _topic_terms(main_subject)
    if not terms:
        return True
    haystack = _topic_terms(" ".join(str(item.get(k) or "") for k in ("title", "snippet", "content_excerpt")))
    return bool(terms & haystack)


# ---------- DuckDuckGo (web) ----------
async def search_duckduckgo(client: httpx.AsyncClient, query: str, max_results: int = 8) -> list[dict]:
    """Try the lightweight endpoint, then the HTML endpoint."""
    # Tentative 1: lite.duckduckgo.com
    try:
        r = await client.post("https://lite.duckduckgo.com/lite/", data={"q": query}, headers=HEADERS, timeout=12)
        if r.status_code == 200 and "result-link" in r.text:
            results = []
            pattern = re.compile(
                r'<a\s+rel="nofollow"\s+href="([^"]+)"\s+class="result-link">(.*?)</a>'
                r'.*?<td\s+class="result-snippet">(.*?)</td>',
                re.DOTALL,
            )
            for m in pattern.finditer(r.text):
                href = m.group(1)
                if "uddg=" in href:
                    qs = up.urlparse(href).query
                    params = up.parse_qs(qs)
                    if "uddg" in params:
                        href = up.unquote(params["uddg"][0])
                if href.startswith("//"):
                    href = "https:" + href
                results.append({
                    "source": "web", "provider": "duckduckgo_lite",
                    "title": _clean(m.group(2)),
                    "url": href,
                    "snippet": _clean(m.group(3)),
                })
                if len(results) >= max_results:
                    break
            if results:
                return results
            log.warning(f"DDG lite: 0 results for '{query[:40]}'")
    except Exception as e:
        log.debug(f"DDG lite failed: {e}")

    # Tentative 2: html.duckduckgo.com
    url = "https://html.duckduckgo.com/html/"
    try:
        r = await client.post(url, data={"q": query}, headers=HEADERS, timeout=12)
        if r.status_code != 200:
            log.warning(f"DDG html status {r.status_code} for '{query[:40]}'")
            return []
        html_text = r.text
        if "anomaly" in html_text.lower() or "unusual traffic" in html_text.lower():
            log.warning(f"DDG blocked (anti-bot) for '{query[:40]}'")
            return []
        results = []
        pattern = re.compile(
            r'<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>(.*?)</a>'
            r'.*?<a[^>]+class="result__snippet"[^>]*>(.*?)</a>',
            re.DOTALL,
        )
        for m in pattern.finditer(html_text):
            href = m.group(1)
            if "uddg=" in href:
                qs = up.urlparse(href).query
                params = up.parse_qs(qs)
                if "uddg" in params:
                    href = up.unquote(params["uddg"][0])
            if href.startswith("//"):
                href = "https:" + href
            results.append({
                "source": "web",
                "provider": "duckduckgo",
                "title": _clean(m.group(2)),
                "url": href,
                "snippet": _clean(m.group(3)),
            })
            if len(results) >= max_results:
                break
        if not results:
            log.warning(f"DDG html: 0 results for '{query[:40]}' (HTML {len(html_text)} chars)")
        return results
    except Exception as e:
        log.warning(f"DDG fallback failed: {e}")
        return []


# ---------- Wikipedia (FR + EN) ----------
async def search_wikipedia(client: httpx.AsyncClient, query: str, lang: str = "en", max_results: int = 3) -> list[dict]:
    base = f"https://{lang}.wikipedia.org/w/api.php"
    try:
        r = await client.get(base, params={
            "action": "query",
            "list": "search",
            "srsearch": query,
            "format": "json",
            "srlimit": max_results,
        }, headers=HEADERS, timeout=10)
        if r.status_code != 200:
            return []
        data = r.json()
        out = []
        for item in data.get("query", {}).get("search", []):
            title = item.get("title", "")
            out.append({
                "source": "wikipedia",
                "provider": f"wikipedia_{lang}",
                "title": title,
                "url": f"https://{lang}.wikipedia.org/wiki/" + up.quote(title.replace(" ", "_")),
                "snippet": _clean(item.get("snippet", "")),
            })
        return out
    except Exception:
        return []


# ---------- Google News (RSS, no API key) ----------
async def search_google_news(client: httpx.AsyncClient, query: str, max_results: int = 8, lang: str = "en") -> list[dict]:
    url = "https://news.google.com/rss/search"
    params = {"q": query, "hl": lang, "gl": "US", "ceid": f"FR:{lang}"}
    try:
        r = await client.get(url, params=params, headers=HEADERS, timeout=12)
        if r.status_code != 200:
            return []
        root = ET.fromstring(r.content)
        out = []
        for item in root.iter("item"):
            title = item.findtext("title") or ""
            link = item.findtext("link") or ""
            desc = item.findtext("description") or ""
            pub = item.findtext("pubDate") or ""
            src_el = item.find("source")
            src_name = src_el.text if src_el is not None else ""
            out.append({
                "source": "actualite",
                "provider": "google_news",
                "title": _clean(title),
                "url": link,
                "snippet": _clean(desc),
                "date": pub,
                "outlet": src_name,
            })
            if len(out) >= max_results:
                break
        return out
    except Exception:
        return []


# ---------- YouTube (page results, titles and channels) ----------
async def search_youtube(client: httpx.AsyncClient, query: str, max_results: int = 6) -> list[dict]:
    url = "https://www.youtube.com/results"
    try:
        r = await client.get(url, params={"search_query": query, "hl": "en"}, headers=HEADERS, timeout=12)
        if r.status_code != 200:
            return []
        text = r.text
        # Find the ytInitialData block
        m = re.search(r"var ytInitialData\s*=\s*({.*?});", text, re.DOTALL)
        if not m:
            m = re.search(r"ytInitialData\s*=\s*({.*?});</script>", text, re.DOTALL)
        if not m:
            return []
        import json as _json
        try:
            data = _json.loads(m.group(1))
        except Exception:
            return []
        out = []
        def walk(node):
            if len(out) >= max_results:
                return
            if isinstance(node, dict):
                if "videoRenderer" in node:
                    v = node["videoRenderer"]
                    vid = v.get("videoId")
                    title = ""
                    if "title" in v and "runs" in v["title"]:
                        title = "".join(x.get("text", "") for x in v["title"]["runs"])
                    elif "title" in v and "simpleText" in v["title"]:
                        title = v["title"]["simpleText"]
                    channel = ""
                    if "ownerText" in v and "runs" in v["ownerText"]:
                        channel = "".join(x.get("text", "") for x in v["ownerText"]["runs"])
                    desc = ""
                    if "detailedMetadataSnippets" in v and v["detailedMetadataSnippets"]:
                        runs = v["detailedMetadataSnippets"][0].get("snippetText", {}).get("runs", [])
                        desc = "".join(x.get("text", "") for x in runs)
                    published = ""
                    if "publishedTimeText" in v:
                        published = v["publishedTimeText"].get("simpleText", "")
                    if vid:
                        out.append({
                            "source": "youtube",
                            "provider": "youtube",
                            "title": title,
                            "url": f"https://www.youtube.com/watch?v={vid}",
                            "snippet": desc,
                            "outlet": channel,
                            "date": published,
                        })
                for v in node.values():
                    walk(v)
            elif isinstance(node, list):
                for x in node:
                    walk(x)
        walk(data)
        return out[:max_results]
    except Exception:
        return []


# ---------- Wayback Machine (archive web) ----------
async def search_wayback(client: httpx.AsyncClient, query: str, max_results: int = 5) -> list[dict]:
    """Query archived pages through the CDX API."""
    try:
        r = await client.get("https://web.archive.org/cdx/search/cdx", params={
            "url": f"*{up.quote(query[:60])}*",
            "limit": str(max_results),
            "fl": "timestamp,original",
            "output": "json",
            "filter": "statuscode:200",
        }, headers=HEADERS, timeout=12)
        if r.status_code != 200:
            return []
        data = r.json()
        out = []
        for row in data[1:max_results + 1] if len(data) > 1 else []:
            try:
                ts, orig = row[0], row[1]
                out.append({
                    "source": "archive_web",
                    "provider": "wayback_machine",
                    "title": f"Archive: {orig}",
                    "url": f"https://web.archive.org/web/{ts}/{orig}",
                    "snippet": f"Capture from {ts[:8]}",
                    "date": ts[:8],
                })
            except Exception:
                continue
        return out
    except Exception:
        return []


# ---------- Internet Archive (livres + media) ----------
async def search_internet_archive(client: httpx.AsyncClient, query: str, max_results: int = 5) -> list[dict]:
    try:
        r = await client.get("https://archive.org/advancedsearch.php", params={
            "q": query + " AND (mediatype:texts OR mediatype:movies)",
            "fl[]": ["identifier", "title", "creator", "description", "mediatype", "year",
                     "subject", "publisher", "language"],
            "rows": str(max_results),
            "output": "json",
        }, headers=HEADERS, timeout=12)
        if r.status_code != 200:
            return []
        docs = r.json().get("response", {}).get("docs", [])
        out = []
        for d in docs:
            ident = d.get("identifier")
            if not ident:
                continue
            is_book = d.get("mediatype") == "texts"
            # Description may be a string or a list of strings
            desc = d.get("description", "")
            if isinstance(desc, list):
                desc = " ".join(str(x) for x in desc)
            desc_clean = _clean(str(desc or ""))
            # Subject keyword list
            subjects = d.get("subject", [])
            if isinstance(subjects, str):
                subjects = [subjects]
            subj_str = ", ".join(str(s) for s in subjects[:5]) if subjects else ""
            # Creator may be a list
            creator = d.get("creator", "")
            if isinstance(creator, list):
                creator = ", ".join(str(c) for c in creator[:2])
            out.append({
                "source": "livre" if is_book else "reportage",
                "provider": "internet_archive",
                "title": d.get("title", ""),
                "url": f"https://archive.org/details/{ident}",
                "snippet": desc_clean[:300],
                "synopsis": desc_clean[:1500] if is_book and len(desc_clean) > 300 else "",
                "outlet": str(creator),
                "date": str(d.get("year", "")),
                "subjects": subj_str,
                "publisher": str(d.get("publisher", "")) if d.get("publisher") else "",
                "language": str(d.get("language", "")) if d.get("language") else "",
            })
        return out
    except Exception:
        return []


# ---------- Fetch + extraction texte d'une page ----------
async def _fetch_source(client: httpx.AsyncClient, url: str, max_chars: int = 4000) -> tuple[str, str]:
    """Fetch an excerpt and report the final URL after any HTTP redirects."""
    try:
        r = await client.get(url, headers=HEADERS, timeout=15, follow_redirects=True)
        final_url = str(r.url)
        if r.status_code != 200:
            return "", final_url
        ct = r.headers.get("content-type", "")
        if "html" not in ct and "xml" not in ct:
            return "", final_url
        text = r.text
        # virer scripts/styles
        text = re.sub(r"<script[^>]*>.*?</script>", " ", text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"<style[^>]*>.*?</style>", " ", text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"<nav[^>]*>.*?</nav>", " ", text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"<footer[^>]*>.*?</footer>", " ", text, flags=re.DOTALL | re.IGNORECASE)
        return _clean(text)[:max_chars], final_url
    except Exception:
        return "", url


async def fetch_text(client: httpx.AsyncClient, url: str, max_chars: int = 4000) -> str:
    """Compatibility wrapper returning only the fetched page excerpt."""
    text, _ = await _fetch_source(client, url, max_chars)
    return text


# ---------- Orchestrateur principal ----------
async def gather_sources(
    queries: list[str],
    enabled: dict | None = None,
    deep: bool = True,
    log=None,
    main_subject: str | None = None,
) -> dict:
    """Search concurrently and optionally retrieve excerpts. Use the main subject to improve Wikipedia relevance."""
    enabled = enabled or {}
    on = lambda k: enabled.get(k, True)

    all_results: list[dict] = []
    queries_used = list(queries)

    import logging as _l
    rlog = _l.getLogger("paradigme.research")
    rlog.info(f"RESEARCH started | {len(queries)} queries | enabled sources: {[k for k in ['web','wikipedia','actualite','youtube','archive'] if on(k)]}")
    if main_subject:
        rlog.info(f"   MAIN SUBJECT: {main_subject}")
    for q in queries:
        rlog.info(f"   QUERY: {q}")

    async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
        tasks = []
        # Use the main subject and keywords for Wikipedia relevance
        if on("wikipedia") and main_subject:
            tasks.append(("wikipedia", main_subject, search_wikipedia(client, main_subject, "en", 3)))
            # Extract significant subject keywords
            keywords = [w for w in re.findall(r"\b[A-Za-z\u00C0-\u017F]{4,}\b", main_subject) if w.lower() not in ("dans", "pour", "avec", "sans", "vers", "chez", "sous", "entre")]
            for kw in keywords[:3]:
                tasks.append(("wikipedia", kw, search_wikipedia(client, kw, "en", 1)))
        for q in queries:
            if on("web"):       tasks.append(("web",       q, search_duckduckgo(client, q, 3)))
            if on("wikipedia") and not main_subject: tasks.append(("wikipedia", q, search_wikipedia(client, q, "en", 1)))
            if on("actualite"): tasks.append(("actualite", q, search_google_news(client, q, 4)))
            if on("youtube"):   tasks.append(("youtube",   q, search_youtube(client, q, 2)))
            if on("archive"):   tasks.append(("archive",   q, search_wayback(client, q, 3)))
            if on("archive"):   tasks.append(("archive",   q, search_internet_archive(client, q, 4)))
        # Search the main subject as well as generated queries
        if on("web") and main_subject:
            tasks.append(("web", main_subject, search_duckduckgo(client, main_subject, 5)))

        coro_list = [t[2] for t in tasks]
        results_list = await asyncio.gather(*coro_list, return_exceptions=True)
        for (kind, q, _), res in zip(tasks, results_list):
            if isinstance(res, Exception):
                rlog.warning(f"   {kind} FAILED for '{q[:40]}': {res}")
                if log:
                    log(f"research {kind} failed: {res}")
                continue
            rlog.info(f"   {kind:10} | '{q[:40]}' -> {len(res)} results")
            for src in res:
                u = src.get("url", "")
                t = (src.get("title", "") or "")[:70]
                rlog.info(f"      [{kind}] {u} | {t}")
            all_results.extend(res)

        # Deduplicate by URL before relevance filtering and deep fetch.
        deduped = _deduplicate_sources(all_results)
        rlog.info(f"DEDUP: {len(all_results)} -> {len(deduped)} unique sources")

        if main_subject:
            before_relevance = len(deduped)
            deduped = [item for item in deduped if _is_topic_relevant(item, main_subject)]
            rlog.info(f"TOPIC RELEVANCE: {before_relevance} -> {len(deduped)} sources")

        # Prioritize directly verifiable sources. Google News may return
        # redirect or consent pages whose excerpts lack the article text.
        # Prefer official pages, Wikipedia, and direct web pages
        # before using news headlines as model context.
        deduped.sort(key=_source_rank)

        # Fetch bounded excerpts from the highest-ranked pages
        if deep and on("web"):
            candidates = [r for r in deduped if r.get("source") in ("web", "wikipedia", "actualite")]
            top_web = [r for r in candidates if not _source_rank(r)[0]][:6]
            rlog.info(f"DEEP FETCH: reading excerpts from {len(top_web)} pages...")
            for r in top_web:
                rlog.info(f"   FETCH: {r.get('url','')}")
            fetch_tasks = [_fetch_source(client, r["url"]) for r in top_web]
            fetched = await asyncio.gather(*fetch_tasks, return_exceptions=True)
            for r, page in zip(top_web, fetched):
                if isinstance(page, tuple):
                    excerpt, final_url = page
                    # Use the actual destination for citations and ranking;
                    # a trusted starting URL must not confer trust on a redirect.
                    if final_url != r.get("url"):
                        r["original_url"] = r.get("url", "")
                    r["url"] = final_url
                    if excerpt:
                        r["content_excerpt"] = excerpt
                        rlog.info(f"   OK: {r.get('url','')[:60]} -> {len(excerpt)} chars")
                elif isinstance(page, Exception):
                    rlog.warning(f"   KO: {r.get('url','')[:60]} -> {page}")
            # Redirect resolution can make separate search results identical.
            # Merge them before ranking, numbering, counting, and LLM selection.
            deduped = _deduplicate_sources(deduped)
            deduped.sort(key=_source_rank)

    # Numerotation finale for citation
    for i, r in enumerate(deduped, 1):
        r["ref"] = i

    counts = _count_by_source(deduped)
    rlog.info(f"RESEARCH complete | {len(deduped)} sources | {counts}")

    return {
        "queries_used": queries_used,
        "sources": deduped,
        "counts_by_source": counts,
    }


def _deduplicate_sources(items: list[dict]) -> list[dict]:
    """Merge records that resolve to the same final URL, preserving useful metadata."""
    merged: dict[str, dict] = {}
    for item in items:
        url = str(item.get("url") or "")
        if not url:
            continue
        existing = merged.get(url)
        if existing is None:
            record = dict(item)
            record["provenance"] = _source_provenance(item, url)
            merged[url] = record
            continue

        # A more highly ranked classification is the representative counted
        # source, while descriptive fields retain the richest available value.
        if _source_rank(item) < _source_rank(existing):
            representative = dict(item)
            representative.update(existing)
            representative["source"] = item.get("source", existing.get("source"))
            representative["url"] = url
            existing.clear()
            existing.update(representative)

        for field in ("title", "snippet", "content_excerpt"):
            values = [str(existing.get(field) or ""), str(item.get(field) or "")]
            best = max(values, key=len)
            if best:
                existing[field] = best

        provenance = existing.setdefault("provenance", [])
        for entry in _source_provenance(item, url):
            if entry not in provenance:
                provenance.append(entry)
        existing["url"] = url
    return list(merged.values())


def _source_provenance(item: dict, final_url: str) -> list[dict]:
    """Capture the originating search result details when records are merged."""
    provenance = item.get("provenance")
    if isinstance(provenance, list):
        entries = [dict(entry) for entry in provenance if isinstance(entry, dict)]
    else:
        entries = []
    entry = {
        key: item[key]
        for key in ("source", "provider", "outlet", "date")
        if item.get(key)
    }
    original_url = item.get("original_url") or item.get("url")
    if original_url and original_url != final_url:
        entry["original_url"] = original_url
    if entry and entry not in entries:
        entries.append(entry)
    return entries


def _count_by_source(items: list[dict]) -> dict:
    out: dict[str, int] = {}
    for r in items:
        s = r.get("source", "?")
        out[s] = out.get(s, 0) + 1
    return out


def format_sources_for_llm(sources: list[dict], max_chars_per_source: int = 700, max_sources: int = 10) -> str:
    """Format bounded source excerpts with numbered citations for the LLM."""
    lines = []
    for r in sources[:max_sources]:
        ref = r.get("ref", "?")
        title = r.get("title", "")[:150]
        src = r.get("source", "")
        outlet = r.get("outlet", "")
        date = r.get("date", "")
        url = r.get("url", "")
        snippet = r.get("snippet", "")
        excerpt = r.get("content_excerpt", "")
        body = (excerpt or snippet)[:max_chars_per_source]
        meta = " | ".join(x for x in [src, outlet, date] if x)
        lines.append(f"[{ref}] ({meta}) {title}\n    URL: {url}\n    EXCERPT: {body}")
    return "\n\n".join(lines)
