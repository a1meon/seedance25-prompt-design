"""Offline regression tests. On Windows run: py -3 -B -m unittest discover -s tests"""
import io
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile
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
