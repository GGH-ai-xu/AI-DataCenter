import unittest
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class InstallScriptTests(unittest.TestCase):
    def test_install_deps_batch_calls_both_setup_scripts(self):
        script = (ROOT / "install-deps.bat").read_text(encoding="utf-8")

        self.assertIn(r"scripts\setup-uv-env.ps1", script)
        self.assertIn(r"scripts\setup-frontend.ps1", script)

    def test_setup_uv_env_uses_repo_root_venv_with_uv(self):
        script = (ROOT / "scripts" / "setup-uv-env.ps1").read_text(encoding="utf-8")

        self.assertIn('Join-Path $root ".venv"', script)
        self.assertIn("uv venv $venvDir", script)
        self.assertIn("uv pip install --python $venvPython", script)
        self.assertIn('Join-Path $root "backend\\requirements.txt"', script)
        self.assertIn('Join-Path $root "server-agent\\requirements.txt"', script)

    def test_setup_frontend_installs_with_npm_ci(self):
        script = (ROOT / "scripts" / "setup-frontend.ps1").read_text(encoding="utf-8")

        self.assertIn('Join-Path $root "frontend"', script)
        self.assertIn('@("npm", "ci", "--include=optional")', script)

    def test_setup_frontend_includes_optional_dependencies(self):
        script = (ROOT / "scripts" / "setup-frontend.ps1").read_text(encoding="utf-8")

        self.assertIn("--include=optional", script)

    def test_frontend_declares_rolldown_native_bindings(self):
        package_json = json.loads((ROOT / "frontend" / "package.json").read_text(encoding="utf-8"))

        optional_dependencies = package_json.get("optionalDependencies", {})
        self.assertIn("@rolldown/binding-win32-x64-msvc", optional_dependencies)
        self.assertIn("@rolldown/binding-linux-x64-gnu", optional_dependencies)

    def test_setup_frontend_repairs_rolldown_native_binding(self):
        script = (ROOT / "scripts" / "setup-frontend.ps1").read_text(encoding="utf-8")

        self.assertIn("Get-RolldownBindingPackage", script)
        self.assertIn("@rolldown/binding-win32-x64-msvc@1.0.0-rc.11", script)
        self.assertIn("@rolldown/binding-linux-x64-gnu@1.0.0-rc.11", script)
        self.assertIn('@("npm", "install", "--no-save"', script)


if __name__ == "__main__":
    unittest.main()
