"""Verify dual publication and recovery using two real, local Git remotes."""
import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE / "scripts"))
from publish import publish


class PublicationTests(unittest.TestCase):
    def test_partial_release_retries_same_commit_on_both_hosts(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            cfg = base / "gitconfig"
            root = base / "checkout"
            root.mkdir()
            def git(*args):
                return subprocess.check_output(["git", *args], cwd=root, text=True).strip()

            with patch.dict(os.environ, {"GIT_CONFIG_GLOBAL": str(cfg), "GIT_CONFIG_NOSYSTEM": "1",
                                         "GIT_ALLOW_PROTOCOL": "file", "GIT_TERMINAL_PROMPT": "0"}):
                git("init", "--quiet")
                git("symbolic-ref", "HEAD", "refs/heads/main")
                source = (PACKAGE / "gitee-source.json").read_text(encoding="utf-8")
                (root / "gitee-source.json").write_text(source, encoding="utf-8")
                git("add", ".")
                git("-c", "user.name=Test", "-c", "user.email=test@localhost",
                    "-c", "commit.gpgSign=false", "commit", "-qm", "release")
                head = git("rev-parse", "HEAD")
                config = json.loads(source)
                gitee, github = base / "gitee.git", base / "github.git"
                for bare, url in ((gitee, config["repository"]), (github, config["github_repository"])):
                    git("config", "--file", str(cfg), "url." + bare.as_uri() + ".insteadOf", url)
                git("init", "--quiet", "--bare", str(gitee))
                with contextlib.redirect_stdout(io.StringIO()), self.assertRaisesRegex(ValueError, "GitHub"):
                    publish(root)
                self.assertEqual(git("--git-dir", str(gitee), "rev-parse", "refs/heads/main"), head)
                git("init", "--quiet", "--bare", str(github))
                with contextlib.redirect_stdout(io.StringIO()):
                    publish(root)
                    publish(root)
                for bare in (gitee, github):
                    self.assertEqual(git("--git-dir", str(bare), "rev-parse", "refs/heads/main"), head)
