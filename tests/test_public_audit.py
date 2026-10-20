"""Ensure the release gate sees tracked leaks, new files and encoded identifiers."""
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from audit_public import audit


class PublicAuditTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name)
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)

    def write(self, name, text):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def test_new_sensitive_file_is_reported_without_its_value(self):
        self.write("example.py", "address = " + repr("private-person" + "@" + "personal.invalid-domain.com"))
        report = audit(self.root)
        self.assertEqual(report["findings"][0]["category"], "non-example-email")
        self.assertNotIn("private-person", str(report))

    def test_ignored_file_is_not_export_candidate_but_tracked_ignored_file_is_flagged(self):
        self.write("backend/data/profile.json", "{}")
        subprocess.run(["git", "-C", str(self.root), "add", "."], check=True)
        self.write(".gitignore", "backend/data/\n.local/\n")
        self.write(".local/secrets.env", "A_TOKEN=local-only")
        report = audit(self.root)
        self.assertEqual(report["finding_count"], 1)
        self.assertEqual(report["findings"][0]["category"], "private-artifact")

    def test_deleted_tracked_file_is_absent_and_example_email_is_allowed(self):
        self.write("old.db", "private runtime")
        subprocess.run(["git", "-C", str(self.root), "add", "."], check=True)
        (self.root / "old.db").unlink()
        self.write("README.md", "Contact user@example.com for this synthetic example.")
        self.assertEqual(audit(self.root)["finding_count"], 0)

    def test_unicode_escapes_are_inspected(self):
        # Use a synthetic local denylist; real identities never enter test fixtures.
        source_name = "PrivateOwner"
        self.write(".gitignore", ".local/\n")
        self.write(".local/privacy-denylist.json", '["PrivateOwner"]')
        encoded = "".join("\\u%04x" % ord(char) for char in source_name)
        self.write("fixture.json", '{"owner": "' + encoded + '"}')
        self.assertTrue(any(f["category"] == "known-identity"
                            for f in audit(self.root)["findings"]))

    def test_names_inside_regular_expression_classes_are_inspected(self):
        self.write(".gitignore", ".local/\n")
        self.write(".local/privacy-denylist.json", '["PrivateOwner"]')
        self.write("rules.py", 'pattern = r"\\bpriv[ae]teown[ée]r\\b"')
        self.assertTrue(any(f["category"] == "known-identity"
                            for f in audit(self.root)["findings"]))


if __name__ == "__main__":
    unittest.main()
