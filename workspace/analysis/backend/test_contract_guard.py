"""python3 -m unittest backend.test_contract_guard"""
from pathlib import Path
from unittest import TestCase

from backend.contract_guard import command_mutates_git, path_is_contract_clone


class ContractClonePathTests(TestCase):
    def test_redmine_clone_is_protected(self):
        root = Path("/home/ansif/works/01_Build/jcatrysse_ror/redmine")
        self.assertTrue(path_is_contract_clone(root))
        self.assertTrue(path_is_contract_clone(root / "app/models/issue.rb"))

    def test_workflows_and_stack_folders_are_writable_paths(self):
        build = Path("/home/ansif/works/01_Build")
        self.assertFalse(path_is_contract_clone(build))
        self.assertFalse(path_is_contract_clone(Path("/home/ansif/works/_common/ansif/profile/_referrals/grafana/README.md")))
        self.assertFalse(path_is_contract_clone(Path("/home/ansif/works/_common/ansif/profile/_referrals/redmine-plugins/README.md")))
        self.assertFalse(path_is_contract_clone(build / "jcatrysse_ror/workflows/note.md"))


class NotesPathTests(TestCase):
    def test_notes_prefix_maps_to_content_notes(self):
        from backend.workspace import resolve_workspace_path

        p = resolve_workspace_path("Notes/learns/Readme.md")
        self.assertEqual(p, Path("/home/ansif/works/01_Build/studies/learns/Readme.md").resolve())
        self.assertTrue(p.is_file())
        p2 = resolve_workspace_path("studies/learns/Readme.md")
        self.assertEqual(p, p2)

    def test_notes_tracks_include_jan_redmine(self):
        from backend.workspace import list_notes_tracks

        ids = {track["id"] for track in list_notes_tracks()}
        self.assertIn("jan-redmine", ids)
        self.assertIn("past-projects", ids)
        self.assertIn("from-coding-agent", ids)

    def test_save_chat_note_writes_under_content_learns(self):
        from backend.workspace import save_chat_note

        result = save_chat_note("from-coding-agent", "Grafana Loki ships logs to Loki.", "Grafana log pipeline")
        saved = Path(result["content_path"])
        self.addCleanup(saved.unlink, missing_ok=True)
        self.assertTrue(saved.is_file())
        self.assertTrue(str(saved).startswith(str(Path("/home/ansif/works/01_Build/studies/learns/from-coding-agent"))))
        self.assertIn("Grafana Loki", saved.read_text(encoding="utf-8"))


class SidebarTreeTests(TestCase):
    def test_redmine_clone_is_not_fully_listed(self):
        from backend.workspace import list_entries

        paths = {entry["path"] for entry in list_entries()}
        self.assertIn("jcatrysse_ror", paths)
        self.assertIn("jcatrysse_ror/redmine", paths)
        self.assertNotIn("_referrals/grafana", paths)
        self.assertFalse(any("/redmine/app/" in path or "/redmine/test/" in path for path in paths))


class SmallModelChatTests(TestCase):
    def test_local_1_5b_skips_tools(self):
        from backend.agent import model_uses_tools

        self.assertFalse(model_uses_tools("qwen2.5-coder:1.5b"))
        self.assertFalse(model_uses_tools("qwen2.5-coder:0.5b"))
        self.assertTrue(model_uses_tools("qwen2.5-coder:14b"))

    def test_compact_prompt_includes_open_editor_file(self):
        from backend.agent import _build_system_prompt

        prompt = _build_system_prompt([".coding-agent/rules.md"], compact=True)
        self.assertIn("Open in editor / attached: .coding-agent/rules.md", prompt)
        self.assertIn("# 01_Build", prompt)
        self.assertIn("Save to Notes", prompt)
        self.assertNotIn("Use exact tool names", prompt)
        self.assertLess(len(prompt), 3500)


class GitMutateTests(TestCase):
    def test_status_is_safe(self):
        self.assertFalse(command_mutates_git("git status --short"))
        self.assertFalse(command_mutates_git("git diff"))

    def test_commit_is_blocked(self):
        self.assertTrue(command_mutates_git("git commit -m hi"))
        self.assertTrue(command_mutates_git("git push origin HEAD"))
