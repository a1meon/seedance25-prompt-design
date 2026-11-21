"""Offline regression tests. On Windows run: py -3 -B -m unittest discover -s tests"""
import io
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
from zipfile import ZipFile

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE / "scripts"))
import update_from_gitee as updater


class WindowsSnapshotTests(unittest.TestCase):
    def setUp(self):
        area = tempfile.TemporaryDirectory()
        self.addCleanup(area.cleanup)
        base = Path(area.name)
        self.remote = base / "upstream"
        self.root = base / "带空格的 安装" / "skills" / updater.NAME
        self.root.mkdir(parents=True)
        self.remote.mkdir()
        config = base / "gitconfig"
        self.config = config
        env = patch.dict(os.environ, {
            "GIT_CONFIG_GLOBAL": str(config), "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_ALLOW_PROTOCOL": "file", "GIT_TERMINAL_PROMPT": "0",
        })
        env.start()
        self.addCleanup(env.stop)
        self.git("init", "--quiet")
        self.git("symbolic-ref", "HEAD", "refs/heads/main")
        url = "https://gitee.com/a1meon_admin/seedance25_prompt.git"
        self.git("config", "--file", str(config), "url." + self.remote.as_uri() + ".insteadOf", url)
        self.git("config", "core.autocrlf", "false")
        (self.remote / "scripts").mkdir()
        for name in ("gitee-source.json", "scripts/update_from_gitee.py"):
            shutil.copyfile(PACKAGE / name, self.remote / name)
        if updater.read_source(self.remote).github:
            self.git("config", "--file", str(config), "--add", "url." + self.remote.as_uri() + ".insteadOf",
                     updater.read_source(self.remote).github)
        self.write_skill("旧版")
        (self.remote / "obsolete.txt").write_bytes(b"old")
        self.commit()
        with ZipFile(io.BytesIO(self.git("archive", "--format=zip", "HEAD"))) as archive:
            archive.extractall(self.root)
        (self.root / updater.REVISION).write_bytes(self.git("rev-parse", "HEAD"))
        (self.remote / "obsolete.txt").unlink()
        self.write_skill("新版")
        (self.remote / "中文 参考.md").write_text("表演", encoding="utf-8")
        self.commit()
        self.tip = self.git("rev-parse", "HEAD").decode().strip()

    def git(self, *args):
        return subprocess.check_output(["git", *args], cwd=self.remote, stderr=subprocess.PIPE)

    def commit(self):
        self.git("add", "-A")
        self.git("-c", "user.name=Test", "-c", "user.email=test@localhost",
                 "-c", "commit.gpgSign=false", "commit", "--quiet", "-m", "fixture")

    def write_skill(self, label):
        (self.remote / "SKILL.md").write_text(
            "---\nname: " + updater.NAME + "\n---\n" + label + "\n", encoding="utf-8"
        )

    def assert_updated(self):
        self.assertEqual((self.root / updater.REVISION).read_text(encoding="ascii").strip(), self.tip)
        self.assertEqual((self.root / "SKILL.md").read_bytes(), (self.remote / "SKILL.md").read_bytes())
        self.assertEqual((self.root / "中文 参考.md").read_text(encoding="utf-8"), "表演")
        self.assertFalse((self.root / "obsolete.txt").exists())
        self.assertEqual(list(self.root.parent.iterdir()), [self.root])

    def test_interrupted_file_replace_resumes_and_commits_version_last(self):
        real_replace = os.replace

        def busy_file(src, dest):
            if dest == self.root / "中文 参考.md":
                raise PermissionError("file in use")
            real_replace(src, dest)

        # Exercise the Windows installer on other test hosts too; the lock
        # keeps using the native OS implementation for the current host.
        with patch.object(sys, "platform", "win32"):
            with patch.object(os, "replace", side_effect=busy_file), self.assertRaises(PermissionError):
                updater.update(self.root)
            self.assertFalse((self.root / updater.REVISION).exists())
            self.assertTrue((self.root / "SKILL.md").is_file())
            self.assertTrue((self.root / "scripts/update_from_gitee.py").is_file())
            self.assertEqual(updater.update(self.root), "updated")
            self.assert_updated()
            self.assertEqual(updater.update(self.root), "current")

    def test_external_updater_repairs_old_entrypoint(self):
        installed_script = self.root / "scripts/update_from_gitee.py"
        installed_script.write_text("raise ImportError('fcntl')\n", encoding="utf-8")
        command = [sys.executable, str(PACKAGE / "scripts/update_from_gitee.py"),
                   "--install-dir", str(self.root)]
        self.assertEqual(subprocess.check_output(command, cwd=self.root).strip(), b"updated")
        self.assertEqual(subprocess.check_output([sys.executable, str(installed_script)],
                                                 cwd=self.root).strip(), b"current")
        self.assert_updated()

    def prepare_bridge(self):
        self.github_url = "https://github.com/fixture-owner/skill.git"
        self.github = self.remote.parent / "github"
        self.legacy = updater.read_source(self.root).legacy
        # Start with a real pre-migration configuration, then add one optional
        # field in the Gitee release. The two remotes continue on common history.
        config = json.loads((self.root / updater.SOURCE).read_text(encoding="utf-8"))
        config.pop("github_repository", None)
        (self.root / updater.SOURCE).write_text(json.dumps(config), encoding="utf-8")
        config["github_repository"] = self.github_url
        (self.remote / updater.SOURCE).write_text(json.dumps(config), encoding="utf-8")
        self.commit()
        self.bridge = self.git("rev-parse", "HEAD").decode().strip()
        self.git("clone", "--no-local", "--quiet", str(self.remote), str(self.github))
        self.git("config", "--file", str(self.config), "url." + self.github.as_uri() + ".insteadOf",
                 self.github_url)
        (self.github / "github-only.md").write_text("release", encoding="utf-8")
        self.git("-C", str(self.github), "add", "github-only.md")
        self.git("-C", str(self.github), "-c", "user.name=Test", "-c", "user.email=test@localhost",
                 "-c", "commit.gpgSign=false", "commit", "--quiet", "-m", "GitHub release")

    def test_gitee_bridge_moves_single_install_to_github(self):
        self.prepare_bridge()
        self.assertEqual(updater.update(self.root), "updated")
        self.assertEqual((self.root / updater.REVISION).read_text().strip(), self.bridge)
        self.remote.rename(self.remote.with_name("unavailable-gitee"))
        self.assertEqual(updater.update(self.root), "updated")
        self.assertTrue((self.root / "github-only.md").is_file())
        self.assertEqual(updater.update(self.root), "current")
        self.assertEqual(list(self.root.parent.iterdir()), [self.root])

    def test_gitee_checkout_fast_forwards_from_github_and_protects_edits(self):
        self.prepare_bridge()
        clone = self.remote.parent / "git-install" / "skills" / updater.NAME
        clone.parent.mkdir(parents=True)
        self.git("clone", "--quiet", self.legacy, str(clone))
        self.remote.rename(self.remote.with_name("unavailable-gitee"))
        (clone / "user-edit.md").write_text("keep")
        with self.assertRaisesRegex(ValueError, "本地改动"):
            updater.update(clone)
        (clone / "user-edit.md").unlink()
        self.assertEqual(updater.update(clone), "updated")
        self.assertTrue((clone / "github-only.md").is_file())
        self.assertEqual(updater.update(clone), "current")

    def test_external_helper_can_rescue_legacy_install_without_gitee(self):
        self.prepare_bridge()
        self.remote.rename(self.remote.with_name("unavailable-gitee"))
        self.assertEqual(updater.update(self.root, self.github), "updated")
        self.assertTrue((self.root / "github-only.md").is_file())

    def test_unreachable_primary_keeps_installed_version_without_downgrade(self):
        self.prepare_bridge()
        self.assertEqual(updater.update(self.root), "updated")
        self.assertEqual(updater.update(self.root), "updated")
        self.github.rename(self.github.with_name("unavailable-github"))
        before = (self.root / updater.REVISION).read_bytes()
        self.assertEqual(updater.update(self.root), "retained")
        self.assertEqual((self.root / updater.REVISION).read_bytes(), before)
        self.assertTrue((self.root / "github-only.md").is_file())
        (self.root / "SKILL.md").unlink()
        with self.assertRaises(FileNotFoundError):
            updater.update(self.root)

    def test_interrupted_download_keeps_previous_install(self):
        before = (self.root / updater.REVISION).read_bytes()
        with patch.object(updater, "remote_git", side_effect=[
            (self.tip + "\trefs/heads/main").encode(), updater.RemoteUnavailable()
        ]):
            self.assertEqual(updater.update(self.root, preference="gitee"), "offline")
        self.assertEqual((self.root / updater.REVISION).read_bytes(), before)
        self.assertTrue((self.root / "obsolete.txt").is_file())

    def test_transport_deadline(self):
        start = time.monotonic()
        with self.assertRaises(updater.RemoteUnavailable):
            updater.remote_git("-c", "alias.stall=!sleep 15", "stall", cwd=self.remote, timeout=1)
        self.assertLess(time.monotonic() - start, 6)

    def test_readonly_sandbox_checks_without_installing(self):
        real_mkdir = Path.mkdir

        def readonly_install(path, *args, **kwargs):
            if path.parent == self.root.parent.parent:
                raise PermissionError
            return real_mkdir(path, *args, **kwargs)

        with patch.object(Path, "mkdir", readonly_install):
            self.assertEqual(updater.update(self.root), "needs-write")
            self.assertTrue((self.root / "obsolete.txt").is_file())
        self.assertEqual(updater.update(self.root), "updated")
        with patch.object(Path, "mkdir", readonly_install):
            self.assertEqual(updater.update(self.root), "current")
            self.remote.rename(self.remote.with_name("unavailable"))
            self.assertEqual(updater.update(self.root), "offline")

    def test_auto_installs_newer_gitee_when_github_is_behind(self):
        self.prepare_bridge()
        self.assertEqual(updater.update(self.root, preference="gitee"), "updated")
        self.git("pull", "--ff-only", self.github.as_uri(), "main")
        (self.remote / "gitee-first.md").write_text("new release")
        self.commit()
        self.assertEqual(updater.update(self.root, preference="github"), "updated")
        self.assertFalse((self.root / "gitee-first.md").exists())
        self.assertEqual(updater.update(self.root), "updated")
        self.assertTrue((self.root / "gitee-first.md").is_file())
        self.assertEqual(updater.update(self.root, preference="github"), "retained")
        self.assertEqual(updater.update(self.root, preference="gitee"), "current")

    def test_fallback_if_only_github_download_fails(self):
        source = updater.read_source(self.root)
        original = updater.remote_git
        downloads = []

        def interrupted(*args, **kwargs):
            if args[0] == "fetch":
                downloads.append(args[-2])
                if args[-2] == source.github:
                    raise updater.RemoteUnavailable()
            return original(*args, **kwargs)

        with patch.object(updater, "remote_git", side_effect=interrupted):
            self.assertEqual(updater.update(self.root), "updated")
        self.assertEqual(downloads, [source.github, source.legacy])
        self.assert_updated()

    def test_forked_mirrors_keep_installed_release(self):
        self.prepare_bridge()
        self.assertEqual(updater.update(self.root, preference="gitee"), "updated")
        (self.remote / "gitee-fork.md").write_text("independent")
        self.commit()
        self.assertEqual(updater.update(self.root), "retained")
        self.assertEqual((self.root / updater.REVISION).read_text().strip(), self.bridge)

    def test_newer_advertised_head_cannot_be_downloaded(self):
        self.prepare_bridge()
        self.assertEqual(updater.update(self.root, preference="gitee"), "updated")
        original = updater.remote_git

        def unavailable(*args, **kwargs):
            if args[0] == "fetch" and args[-2] == self.github_url:
                raise updater.RemoteUnavailable()
            return original(*args, **kwargs)

        with patch.object(updater, "remote_git", side_effect=unavailable):
            self.assertEqual(updater.update(self.root), "retained")
        self.assertEqual((self.root / updater.REVISION).read_text().strip(), self.bridge)

    @unittest.skipIf(os.name == "nt", "uses POSIX snapshot exchange")
    def test_concurrent_snapshot_check_returns_immediately(self):
        cache = self.root.parent.parent / ("." + self.root.parent.name + "-" + updater.NAME + "-sync")
        cache.mkdir()
        with (cache / "lock").open("a+b") as lock:
            updater.lock_update(lock)
            self.assertEqual(updater.update(self.root), "busy")

    @unittest.skipUnless(os.name == "nt", "requires Windows file sharing and read-only attributes")
    def test_busy_entrypoint_and_readonly_obsolete_file(self):
        (self.root / "obsolete.txt").chmod(stat.S_IREAD)
        with (self.root / "SKILL.md").open("rb"):
            with self.assertRaises(PermissionError):
                updater.update(self.root)
            self.assertFalse((self.root / updater.REVISION).exists())
        self.assertEqual(updater.update(self.root), "updated")
        self.assert_updated()

    @unittest.skipUnless(os.name == "nt", "requires native Windows byte-range locking")
    def test_windows_lock_across_processes(self):
        import msvcrt

        lock_path = self.remote.parent / "process.lock"
        program = (
            "import sys; sys.path.insert(0, sys.argv[1]); from update_from_gitee import lock_update; "
            "f=open(sys.argv[2], 'a+b'); lock_update(f); print('ready', flush=True); sys.stdin.read(1)"
        )
        with subprocess.Popen([sys.executable, "-B", "-c", program, str(PACKAGE / "scripts"), str(lock_path)],
                              stdin=subprocess.PIPE, stdout=subprocess.PIPE) as child:
            try:
                self.assertEqual(child.stdout.readline().strip(), b"ready")
                with lock_path.open("a+b") as own:
                    own.seek(0)
                    with self.assertRaises(OSError):
                        msvcrt.locking(own.fileno(), msvcrt.LK_NBLCK, 1)
            finally:
                child.communicate(b"x", timeout=10)
        with lock_path.open("a+b") as own:
            updater.lock_update(own)


if __name__ == "__main__":
    unittest.main()
