"""Unit tests for the read-only ASTRA baseline tooling."""
from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "astra_baseline_audit.py"
SPEC = importlib.util.spec_from_file_location("astra_baseline_audit", SCRIPT_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"Cannot load baseline tool at {SCRIPT_PATH}")
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)


class BaselineAuditTests(unittest.TestCase):
    def test_compare_trees_identical_then_detects_content_difference(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            left = root / "SHADOWLINK-FIELD"
            right = root / "Final-Project" / "SHADOWLINK-FIELD"
            left.mkdir(parents=True)
            right.mkdir(parents=True)
            (left / "requirements.txt").write_text("fastapi==0.1\n", encoding="utf-8")
            (right / "requirements.txt").write_text("fastapi==0.1\n", encoding="utf-8")

            identical = AUDIT.compare_trees(root, "SHADOWLINK-FIELD", "Final-Project/SHADOWLINK-FIELD")
            self.assertTrue(identical["identical_under_manifest_rules"])
            self.assertEqual(identical["matching_entries"], 1)

            (right / "requirements.txt").write_text("fastapi==0.2\n", encoding="utf-8")
            different = AUDIT.compare_trees(root, "SHADOWLINK-FIELD", "Final-Project/SHADOWLINK-FIELD")
            self.assertFalse(different["identical_under_manifest_rules"])
            self.assertEqual(different["different_entries"], ["requirements.txt"])

    def test_manifest_ignores_dependency_and_cache_directories(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "src").mkdir()
            (root / "src" / "app.py").write_text("print('ok')\n", encoding="utf-8")
            for name in (".git", ".venv", "node_modules", "__pycache__"):
                (root / name).mkdir()
                (root / name / "ignored.py").write_text("ignored\n", encoding="utf-8")

            manifest = AUDIT.tree_manifest(root)
            self.assertIn("src/app.py", manifest)
            self.assertNotIn(".git/ignored.py", manifest)
            self.assertNotIn(".venv/ignored.py", manifest)
            self.assertNotIn("node_modules/ignored.py", manifest)

    def test_path_scan_finds_external_refs_but_excludes_mirror_and_audit_docs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "scripts").mkdir()
            (root / "scripts" / "launcher.py").write_text(
                'NESTED_ROOT = "Final-Project/SHADOWLINK-FIELD"\n', encoding="utf-8"
            )
            (root / "docs" / "audits").mkdir(parents=True)
            (root / "docs" / "plans").mkdir(parents=True)
            (root / "docs" / "audits" / "ASTRA_REMOTE_REPOSITORY_AUDIT_2026-10-23.md").write_text(
                "This audit refers to Final-Project/SHADOWLINK-FIELD intentionally.\n", encoding="utf-8"
            )
            (root / "docs" / "plans" / "ASTRA_REINTEGRATION_GSD_PLAN.md").write_text(
                "The plan refers to Final-Project/SHADOWLINK-FIELD intentionally.\n", encoding="utf-8"
            )
            nested = root / "Final-Project" / "SHADOWLINK-FIELD"
            nested.mkdir(parents=True)
            (nested / "own_path.py").write_text(
                'SELF = "Final-Project/SHADOWLINK-FIELD"\n', encoding="utf-8"
            )

            result = AUDIT.path_reference_audit(root)
            self.assertEqual(result["match_count_returned"], 1)
            self.assertEqual(result["code_or_config_match_count"], 1)
            self.assertEqual(result["documentation_match_count"], 0)
            self.assertEqual(result["matches"][0]["path"], "scripts/launcher.py")

    def test_path_scan_normalizes_windows_separators(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "config").mkdir()
            windows_path = "Final-Project" + chr(92) + "SHADOWLINK-FIELD"
            (root / "config" / "launch.json").write_text(
                '{"path": "' + windows_path + '" }\\n', encoding="utf-8"
            )
            result = AUDIT.path_reference_audit(root)
            self.assertEqual(result["match_count_returned"], 1)
            self.assertEqual(result["code_or_config_match_count"], 1)


if __name__ == "__main__":
    unittest.main()
