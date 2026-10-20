"""Check historical leaks that a clean working tree cannot reveal."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from audit_git_history import audit_history
from audit_public import audit


class GitHistoryAuditTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name) / "repo"
        self.root.mkdir()
        self.env = {key: value for key, value in os.environ.items()
                    if not key.startswith("GIT_") and key != "PUBLIC_PRIVACY_DENYLIST"}
        self.env.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull)
        self.git("init", "-q", "--template=", "-b", "main")
        self.git("config", "user.name", "VideoTransformer Contributors")
        self.git("config", "user.email", "contributors@example.com")
        self.write("README.md", "Synthetic public source.\n")
        self.write("frontend/src/data/helpers.js", "export const items = [];\n")
        self.write("backend/data/profiles/.gitkeep", "")
        self.commit()

    def git(self, *args, data=None):
        return subprocess.check_output(
            ["git", "-c", f"safe.directory={self.root.as_posix()}", "-C", str(self.root), *args],
            input=data, env=self.env, stderr=subprocess.PIPE)

    def write(self, name, text):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def commit(self, *args):
        self.git("add", ".")
        self.git("commit", "-q", "-m", "Public snapshot", *args)

    def report(self):
        return audit_history(self.root)

    def test_clean_repository_passes(self):
        report = self.report()
        self.assertEqual(report["finding_count"], 0)
        self.assertEqual(report["object_types"]["commit"], 1)
        self.assertEqual(report["unreachable_objects"], 0)

    def test_deleted_file_is_still_detected_in_history(self):
        self.write("reports/note.txt", "Synthetic private report.\n")
        self.commit()
        (self.root / "reports/note.txt").unlink()
        self.commit()
        self.assertEqual(audit(self.root)["finding_count"], 0)
        self.assertIn("private-artifact", self.report()["categories"])

    def test_unreachable_blob_is_detected_even_after_packing(self):
        secret = ("private-person" + "@" + "personal.invalid-domain.com").encode()
        self.git("hash-object", "-w", "--stdin", data=secret)
        self.git("repack", "-ad")
        report = self.report()
        self.assertIn("non-example-email", report["categories"])
        self.assertGreater(report["unreachable_objects"], 0)
        self.assertNotIn(secret.decode(), json.dumps(report))

    def test_author_and_reflog_survive_identity_config_change(self):
        private_email = "private-person" + "@" + "personal.invalid-domain.com"
        self.git("config", "user.email", private_email)
        self.commit("--allow-empty")
        self.git("config", "user.email", "contributors@example.com")
        report = self.report()
        matches = [item for item in report["findings"] if item["category"] == "non-example-email"]
        self.assertTrue(any(item["object"].startswith("metadata:") for item in matches))
        self.assertTrue(any(not item["object"].startswith("metadata:") for item in matches))

    def test_external_identity_list_checks_encoded_commit_message(self):
        private_list = Path(self.folder.name) / "identifiers.json"
        private_list.write_text('["PrivateOwner"]', encoding="utf-8")
        encoded = "".join("\\u%04x" % ord(char) for char in "PrivateOwner")
        self.git("commit", "-q", "--allow-empty", "-m", encoded)
        report = audit_history(self.root, private_list)
        self.assertTrue(report["private_denylist_loaded"])
        self.assertIn("known-identity", report["categories"])
        self.assertFalse((self.root / ".local").exists())

    def test_remote_configuration_is_inspected(self):
        private_url = "https://private-person" + "@" + "personal.invalid-domain.com/repo.git"
        self.git("remote", "add", "private", private_url)
        self.assertIn("non-example-email", self.report()["categories"])


if __name__ == "__main__":
    unittest.main()
