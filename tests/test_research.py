"""Synthetic regression tests for institutional source ranking."""
import unittest

import httpx

from research import _fetch_source, _host_is_trusted, _source_rank


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
