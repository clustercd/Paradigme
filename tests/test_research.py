"""Synthetic regression tests for institutional source ranking."""
import unittest

import httpx
from unittest.mock import patch

from research import (
    _fetch_source, _host_is_trusted, _source_rank,
    format_sources_for_llm, gather_sources,
)


class TrustedSourceRankingTests(unittest.TestCase):
    def test_authentic_domains_and_legitimate_subdomains_are_trusted(self):
        for host in (
            "who.int", "www.who.int", "data.europa.eu", "stats.insee.fr",
            "service.gouv.fr", "usa.gov", "agency.example.gov", "en.wikipedia.org",
        ):
            with self.subTest(host=host):
                self.assertTrue(_host_is_trusted(host))

    def test_lookalike_domains_and_query_parameters_are_not_trusted(self):
        urls = (
            "https://who.int.example.org/article",
            "https://example.org/go?source=wikipedia.org",
            "https://wikipedia.org.example.net/article",
            "https://example.gov.org/article",
            "https://who-int.example/article",
            "https://раypal.example/article",  # Unicode lookalike hostname
        )
        for url in urls:
            with self.subTest(url=url):
                self.assertEqual(_source_rank({"url": url, "source": "web"})[1], 1)

    def test_url_components_do_not_override_the_actual_hostname(self):
        self.assertEqual(
            _source_rank({"url": "https://example.org/who.int?q=europa.eu", "source": "web"})[1],
            1,
        )
        self.assertEqual(
            _source_rank({"url": "https://www.who.int:443/path", "source": "web"})[1],
            0,
        )
        self.assertEqual(_source_rank({"url": "not a url", "source": "web"})[1], 1)

    def test_ordinary_sources_remain_rankable_without_institutional_priority(self):
        ordinary = {"url": "https://example.org/report", "source": "web"}
        institution = {"url": "https://www.who.int/report", "source": "web"}
        wikipedia = {"url": "https://en.wikipedia.org/wiki/Example", "source": "wikipedia"}
        self.assertEqual(_source_rank(ordinary), (0, 1, 1))
        self.assertEqual(_source_rank(institution), (0, 0, 1))
        self.assertEqual(_source_rank(wikipedia), (0, 0, 0))

    def test_gather_sources_merges_redirects_before_refs_counts_and_llm_limit(self):
        canonical_url = "https://canonical.test/article"
        search_results = [
            {"source": "web", "provider": "search_a", "title": "Article title",
             "url": "https://alias-one.test/start", "snippet": "Short excerpt"},
            {"source": "web", "provider": "search_b", "title": "A longer article title",
             "url": "https://alias-two.test/start", "snippet": "A longer and more useful search excerpt"},
            {"source": "web", "provider": "search_c", "title": "Canonical record",
             "url": canonical_url, "snippet": "Canonical snippet"},
        ]
        search_results.extend(
            {"source": "web", "provider": "search", "title": f"Distinct {i}",
             "url": f"https://distinct-{i}.test/article", "snippet": f"Snippet {i}"}
            for i in range(9)
        )

        async def fake_search(client, query, max_results=8):
            return search_results

        def handler(request):
            if request.url.host.startswith("alias-"):
                return httpx.Response(302, headers={"Location": canonical_url})
            return httpx.Response(200, headers={"Content-Type": "text/html"},
                                  text="<p>Resolved article excerpt</p>")

        async def scenario():
            client_class = httpx.AsyncClient
            factory = lambda **kwargs: client_class(
                transport=httpx.MockTransport(handler), **kwargs
            )
            with patch("research.search_duckduckgo", new=fake_search), \
                 patch("research.httpx.AsyncClient", side_effect=factory):
                return await gather_sources(
                    ["synthetic query"],
                    enabled={"web": True, "wikipedia": False, "actualite": False,
                             "youtube": False, "archive": False},
                    deep=True,
                )

        import asyncio
        result = asyncio.run(scenario())
        sources = result["sources"]
        merged = [item for item in sources if item["url"] == canonical_url]

        self.assertEqual(len(merged), 1)
        self.assertEqual(len(sources), 10)
        self.assertEqual([item["ref"] for item in sources], list(range(1, 11)))
        self.assertEqual(result["counts_by_source"], {"web": 10})
        self.assertEqual(merged[0]["title"], "A longer article title")
        self.assertEqual(merged[0]["snippet"], "A longer and more useful search excerpt")
        self.assertEqual(merged[0]["content_excerpt"], "Resolved article excerpt")
        self.assertEqual(
            {entry["provider"] for entry in merged[0]["provenance"]},
            {"search_a", "search_b", "search_c"},
        )
        self.assertEqual(
            {entry.get("original_url") for entry in merged[0]["provenance"]
             if entry.get("original_url")},
            {"https://alias-one.test/start", "https://alias-two.test/start"},
        )
        llm_sources = format_sources_for_llm(sources, max_sources=10)
        self.assertEqual(llm_sources.count(canonical_url), 1)
        self.assertEqual(llm_sources.count("["), 10)

    def test_redirect_destination_replaces_starting_host_for_ranking(self):
        async def scenario():
            def handler(request):
                if request.url.host == "www.who.int":
                    return httpx.Response(302, headers={"Location": "https://example.org/article"})
                return httpx.Response(200, headers={"Content-Type": "text/html"}, text="<p>Article</p>")

            async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
                excerpt, final_url = await _fetch_source(client, "https://www.who.int/start")
            source = {"url": final_url, "source": "web"}
            return excerpt, final_url, _source_rank(source)

        import asyncio
        excerpt, final_url, rank = asyncio.run(scenario())
        self.assertEqual(excerpt, "Article")
        self.assertEqual(final_url, "https://example.org/article")
        self.assertEqual(rank, (0, 1, 1))


if __name__ == "__main__":
    unittest.main()
