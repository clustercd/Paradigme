"""Isolated regression checks; no external network or email delivery."""
import asyncio
import copy
import json
import os
from pathlib import Path
import string
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

import httpx

_BOOT = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
_BOOT_PATH = Path(_BOOT.name)
with patch.dict(os.environ, {
    "PARADIGME_CONFIG": str(_BOOT_PATH / "config.json"),
    "PARADIGME_DATA_DIR": str(_BOOT_PATH / "data"),
    "PARADIGME_LOGS_DIR": str(_BOOT_PATH / "logs"),
}):
    import app
import analysis
import prompts
from llm_client import LLMClient
from labels import display_label
from cleaning import is_placeholder
from tree_builder import build_tree
from pdf_report import generate_pdf
from txt_report import generate_txt

ROOT = Path(__file__).resolve().parents[1]


def synthetic_result():
    summary = (
        "The supplied source describes how a small team documented its software maintenance practices [1]. "
        "It explains that contributors reviewed changes together and recorded unresolved limitations in the project notes [1]. "
        "The excerpt does not establish whether these practices would transfer to other organizations [1]."
    )
    return {
        "subject": "Open-source collaboration", "context": "Synthetic validation fixture",
        "generated_at": "2026-01-01T12:00:00", "analysis_model": "classique",
        "analysis_model_name": "Classic (Sector analysis)",
        "model_used": {"name": "synthetic-test-model", "server_type": "test"},
        "research": {"sources": [{"ref": i, "title": "Synthetic research fixture",
            "url": f"https://example.org/source/{i}", "source": "web",
            "snippet": summary, "content_excerpt": summary} for i in range(1, 4)]},
        "synthesis": {"synthese": summary,
            "actions_immediates": ["Document the team's existing review process and record its limitations before comparing alternatives.",
                "Interview maintainers about unresolved coordination costs and check the evidence against their records."],
            "questions_a_se_poser": ["Which constraints limit participation?", "What evidence could test transferability?"],
            "reponses_aux_questions": [{"question": "Which constraints limit participation?", "reponse": "The fixture does not resolve that question."}]},
        "sectors": {"resume_situation": summary, "secteurs": [{"nom": "Collaboration",
            "intensite": 5, "nature": "mixte", "effets_actuels": ["Review practices are documented [1]."],
            "parties_prenantes": ["Maintainers"]}]},
        "tree": build_tree("Open-source collaboration", {"branches": [
            {"label": "Review participation could grow", "type": "opportunite", "si_oui": "More reviews could be shared", "si_non": "Review load could stay concentrated"},
            {"label": "Coordination costs could increase", "type": "risque", "si_oui": "Teams could need clearer scheduling", "si_non": "Existing routines could remain sufficient"}]}),
        "projections": {"horizons": [{"duree": "5 years", "scenarios": [{"type": "median",
            "probabilite_estimee": 0.5, "narratif": "If participation remains stable, existing routines could continue.",
            "indicateurs_cles": ["Review participation"], "declencheurs": ["A change in contributor availability"]}]}]},
        "methodology": {"projection_notice": "Illustrative scenarios, not calibrated forecasts."},
    }


class ApplicationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.cfg = json.loads((ROOT / "config.example.json").read_text(encoding="utf-8"))
        self.cfg["llm"]["groq"]["api_key"] = "synthetic-secret-for-tests"
        self.cfg["llm"]["api_key"] = "synthetic-generic-key"
        self.cfg["email"]["smtp_password"] = "synthetic-mail-password"
        self.patchers = []
        for key, path in {"CONFIG_PATH": self.root / "config.json", "REPORTS_DIR": self.root / "reports",
                          "RESULTS_DIR": self.root / "results", "HISTORY_PATH": self.root / "history.json"}.items():
            patcher = patch.object(app, key, path); patcher.start(); self.patchers.append(patcher)
        app.REPORTS_DIR.mkdir(); app.RESULTS_DIR.mkdir()
        app.save_config(self.cfg)
        app.JOBS.clear()
        self.client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app.app), base_url="http://test")

    async def asyncTearDown(self):
        await self.client.aclose()
        for task in list(app.ACTIVE_ANALYSES):
            task.cancel()
        if app.ACTIVE_ANALYSES:
            await asyncio.gather(*app.ACTIVE_ANALYSES, return_exceptions=True)
        for patcher in reversed(self.patchers):patcher.stop()
        self.temp.cleanup()

    async def test_config_and_debug_do_not_reveal_keys(self):
        cfg = (await self.client.get("/api/config")).json()
        self.assertEqual(cfg["llm"]["api_key"], "***")
        self.assertEqual(cfg["llm"]["groq"]["api_key"], "***")
        self.assertEqual(cfg["email"]["smtp_password"], "***")
        debug = await self.client.get("/api/debug-llm")
        self.assertNotIn("synthetic", debug.text)
        self.assertNotIn("prefix", debug.text)
        self.assertTrue(debug.json()["groq_key_present"])
        await self.client.post("/api/config", json={"llm": {"api_key": "***"}, "email": {"smtp_password": "***"}})
        self.assertEqual(app.load_config()["llm"]["api_key"], "synthetic-generic-key")

    async def test_setup_preserves_credentials_when_blank(self):
        response = await self.client.post("/api/setup/save", json={"provider": "groq", "api_key": ""})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(app.load_config()["llm"]["groq"]["api_key"], "synthetic-secret-for-tests")

    async def test_saved_job_survives_memory_reset_and_generates_text(self):
        result = synthetic_result()
        app.save_completed_job("fixture", {"id": "fixture", "status": "done", "result": result})
        self.assertEqual((await self.client.get("/api/job/fixture")).json()["result"]["subject"], result["subject"])
        text = await self.client.get("/api/report/fixture/txt")
        self.assertEqual(text.status_code, 200)
        self.assertIn("EXECUTIVE SYNTHESIS", text.text)
        self.assertIn("central", text.text.lower())
        self.assertNotIn("mixte", text.text)

    async def test_analyze_returns_while_job_is_running_and_persists_completion(self):
        release = asyncio.Event()
        async def fake_run(jid, req, jobs, llm, cfg, log):
            await release.wait()
            result = synthetic_result()
            jobs[jid].update(status="done", result=result, model_used=result["model_used"])
            return result
        with patch.object(app, "run_analysis", fake_run):
            response = await asyncio.wait_for(self.client.post("/api/analyze", json={"subject": "Fixture"}), timeout=1)
            jid = response.json()["job_id"]
            self.assertTrue(app.ACTIVE_ANALYSES)
            release.set()
            await asyncio.gather(*app.ACTIVE_ANALYSES)
            app.JOBS.clear()
            self.assertEqual((await self.client.get(f"/api/job/{jid}")).json()["status"], "done")
            self.assertEqual((await self.client.get("/api/history")).json()[0]["id"], jid)

    async def test_no_engine_produces_error_without_email(self):
        llm = AsyncMock(); llm.health.return_value = {"ok": False, "active_engine": "none"}
        jobs = {"fixture": {}}
        with patch("mailer.send_report") as send:
            result = await analysis.run_analysis("fixture", app.AnalyzeRequest(subject="Fixture"), jobs, llm,
                {"_reports_dir": str(self.root / "reports")}, lambda *args: None)
        self.assertIsNone(result)
        self.assertEqual(jobs["fixture"]["status"], "error")
        send.assert_not_called()

    def test_quality_accepts_consistent_synthetic_source_references(self):
        result = synthetic_result()
        quality = analysis._assess_result_quality(result, app.AnalyzeRequest(subject=result["subject"]))
        self.assertTrue(quality["usable"], quality["issues"])
        self.assertEqual(quality["cited_references"], [1])
        self.assertEqual(quality["unknown_references"], [])
        self.assertIn("do not verify", quality["citation_note"])

    def test_quality_rejects_unknown_reference_in_summary(self):
        result = synthetic_result()
        result["synthesis"]["synthese"] += " This unsupported detail has no source record [999]."
        quality = analysis._assess_result_quality(result, app.AnalyzeRequest(subject=result["subject"]))
        self.assertFalse(quality["usable"])
        self.assertIn("[999]", " ".join(quality["issues"]))
        self.assertEqual(quality["unknown_references"], [999])

    def test_quality_rejects_missing_references(self):
        result = synthetic_result()
        result["synthesis"]["synthese"] = result["synthesis"]["synthese"].replace("[1]", "")
        result["sectors"]["resume_situation"] = result["sectors"]["resume_situation"].replace("[1]", "")
        result["sectors"]["secteurs"][0]["effets_actuels"] = ["The fixture describes review practices."]
        quality = analysis._assess_result_quality(result, app.AnalyzeRequest(subject=result["subject"]))
        self.assertFalse(quality["usable"])
        self.assertIn("no source references found", " ".join(quality["issues"]))

    def test_quality_rejects_unknown_references_outside_summary(self):
        result = synthetic_result()
        result["projections"]["horizons"][0]["scenarios"][0]["narratif"] += " [999]"
        quality = analysis._assess_result_quality(result, app.AnalyzeRequest(subject=result["subject"]))
        self.assertFalse(quality["usable"])
        self.assertIn("[999]", " ".join(quality["issues"]))

    def test_quality_rejects_unknown_reference_in_regional_timelines(self):
        result = synthetic_result()
        result["regional_timelines"] = {"regions": [{"region": "chine", "evenements": [
            {"titre": "Synthetic event [999]"}]}]}
        quality = analysis._assess_result_quality(result, app.AnalyzeRequest(subject=result["subject"]))
        self.assertFalse(quality["usable"])
        self.assertEqual(quality["unknown_references"], [999])

    def test_quality_rejects_unknown_structured_source_references(self):
        for field in ("citations", "sources_principales_utilisees"):
            with self.subTest(field=field):
                result = synthetic_result()
                result["synthesis"][field] = [999]
                quality = analysis._assess_result_quality(
                    result, app.AnalyzeRequest(subject=result["subject"]))
                self.assertFalse(quality["usable"])
                self.assertEqual(quality["unknown_references"], [999])

    def test_quality_accepts_known_structured_source_references(self):
        result = synthetic_result()
        result["synthesis"]["sources_principales_utilisees"] = [1, "2"]
        result["sectors"]["secteurs"][0]["citations"] = [3]
        quality = analysis._assess_result_quality(result, app.AnalyzeRequest(subject=result["subject"]))
        self.assertTrue(quality["usable"], quality["issues"])
        self.assertEqual(quality["unknown_references"], [])

    def test_quality_rejects_incoherent_source_identifiers(self):
        result = synthetic_result()
        for source in result["research"]["sources"]:
            source["ref"] = "source-one"
        quality = analysis._assess_result_quality(result, app.AnalyzeRequest(subject=result["subject"]))
        self.assertFalse(quality["usable"])
        self.assertIn("invalid reference identifiers", " ".join(quality["issues"]))

    def test_quality_rejects_duplicate_source_identifiers(self):
        result = synthetic_result()
        result["research"]["sources"][1]["ref"] = 1
        quality = analysis._assess_result_quality(result, app.AnalyzeRequest(subject=result["subject"]))
        self.assertFalse(quality["usable"])
        self.assertIn("duplicate reference identifiers", " ".join(quality["issues"]))

    async def test_classic_pipeline_passes_with_cited_synthetic_evidence(self):
        result = synthetic_result()
        responses = [{"queries": ["synthetic research"]}, result["sectors"], {"tree": result["tree"]["tree"]},
                     *[copy.deepcopy(result["projections"]["horizons"][0]) for _ in range(5)], {}, result["synthesis"]]
        llm = AsyncMock(); llm.engine_params = {}
        llm.health.return_value = {"ok": True, "active_engine": "local", "model": "fixture"}
        llm.chat_json.side_effect = responses
        jobs = {"fixture": {}}
        with patch("research.gather_sources", new=AsyncMock(return_value=result["research"])), patch("mailer.send_report") as send:
            output = await analysis.run_analysis("fixture", app.AnalyzeRequest(subject=result["subject"], generate_pdf=False),
                jobs, llm, {"_reports_dir": str(self.root / "reports")}, lambda *args: None)
        self.assertIsNotNone(output, jobs["fixture"].get("error"))
        self.assertTrue(output["quality"]["usable"])
        self.assertEqual(jobs["fixture"]["status"], "done")
        send.assert_not_called()


class ProviderTests(unittest.IsolatedAsyncioTestCase):
    async def test_local_provider_never_uses_environment_groq_key(self):
        with patch.dict(os.environ, {"GROQ_API_KEY": "synthetic-environment-key"}):
            for provider in ("bridge", "ollama", "llamacpp", "custom", "openai", "anthropic"):
                self.assertFalse(LLMClient({"provider": provider}).groq_enabled)

    async def test_bridge_health_and_chat(self):
        requests = []
        def handler(request):
            requests.append(request)
            return httpx.Response(200, json={"model_loaded": True, "current_model": "fixture"} if request.url.path == "/status" else {"response": '{"answer":"Synthetic reply"}'})
        original = httpx.AsyncClient
        def client(**kwargs):return original(transport=httpx.MockTransport(handler), **kwargs)
        with patch("llm_client.httpx.AsyncClient", client):
            llm = LLMClient({"provider": "bridge", "base_url": "http://test"})
            self.assertTrue((await llm.health())["ok"])
            self.assertEqual((await llm.chat_json("Fixture"))["answer"], "Synthetic reply")
        self.assertEqual([r.url.path for r in requests], ["/status", "/chat"])
        self.assertIn("English", json.loads(requests[-1].content)["messages"][0]["content"])

    async def test_anthropic_messages_protocol(self):
        requests = []
        def handler(request):
            requests.append(request)
            return httpx.Response(200, json={"content": [{"type": "text", "text": '{"answer":"Synthetic reply"}'}]})
        original = httpx.AsyncClient
        with patch("llm_client.httpx.AsyncClient", lambda **kw: original(transport=httpx.MockTransport(handler), **kw)):
            llm = LLMClient({"provider": "anthropic", "base_url": "https://example.org/v1", "api_key": "fixture", "model": "fixture"})
            self.assertEqual((await llm.chat_json("Fixture"))["answer"], "Synthetic reply")
        self.assertEqual(requests[0].url.path, "/v1/messages")
        self.assertEqual(requests[0].headers["x-api-key"], "fixture")
        self.assertNotIn("system", [m["role"] for m in json.loads(requests[0].content)["messages"]])


class OutputTests(unittest.TestCase):
    def test_all_prompts_format_without_schema_brace_errors(self):
        for name, text in vars(prompts).items():
            if name.isupper() and isinstance(text, str):
                fields = {field: "fixture" for _, field, _, _ in string.Formatter().parse(text) if field}
                self.assertTrue(text.format(**fields), name)

    def test_legacy_enum_labels_and_english_placeholders(self):
        self.assertEqual(display_label("mixte"), "mixed")
        self.assertEqual(display_label("5 ans"), "5 years")
        self.assertTrue(is_placeholder("effect 1"))
        self.assertFalse(is_placeholder("Documented review practices changed participation."))

    def test_pdf_and_text_reports_with_synthetic_content(self):
        with tempfile.TemporaryDirectory() as directory:
            pdf = Path(directory) / "report.pdf"; txt = Path(directory) / "report.txt"
            generate_pdf(synthetic_result(), str(pdf)); generate_txt(synthetic_result(), str(txt))
            self.assertTrue(pdf.read_bytes().startswith(b"%PDF"))
            self.assertIn("ANALYSIS REPORT", txt.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
