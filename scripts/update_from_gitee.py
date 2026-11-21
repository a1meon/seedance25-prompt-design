"""Check the configured Gitee branch and replace the installed skill in place."""
import ctypes
import fcntl
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
import tarfile

NAME = "seedance25-prompt-design-v1-0"
SOURCE = "gitee-source.json"
REVISION = ".gitee-revision"


def git(*args, cwd=None):
    env = dict(os.environ, GIT_TERMINAL_PROMPT="0")
    return subprocess.run(
        ["git", "-c", "core.hooksPath=/dev/null", *args], cwd=cwd, env=env,
        stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        check=True, timeout=90,
    ).stdout


def read_source(root):
    config = json.loads((root / SOURCE).read_text())
    remote = config["repository"]
    if not isinstance(remote, str) or not re.fullmatch(
        r"(?:https://gitee\.com/|git@gitee\.com:)[\w.-]+/[\w.-]+", remote
    ):
        raise ValueError("更新源需要配置为指定的 Gitee 仓库")
    branch = config["branch"]
    git("check-ref-format", "refs/heads/" + branch)
    subdir = config["directory"]
    if subdir != "." and any(not re.fullmatch(r"[\w.-]+", p) or p in (".", "..") for p in subdir.split("/")):
        raise ValueError("技能子目录无效")
    return remote, "refs/heads/" + branch, subdir


def export_skill(repo, revision, subdir, destination):
    tree = revision if subdir == "." else f"{revision}:{subdir}"
    archive = git("archive", "--format=tar", tree, cwd=repo)
    destination.mkdir()
    with tarfile.open(fileobj=io.BytesIO(archive), mode="r:") as tar:
        for member in tar:
            path = PurePosixPath(member.name)
            if path.is_absolute() or ".." in path.parts or ".git" in path.parts or path.name == REVISION:
                raise ValueError("更新包路径无效")
            target = destination / path
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
            elif member.isfile():
                target.parent.mkdir(parents=True, exist_ok=True)
                with target.open("xb") as output, tar.extractfile(member) as source:
                    shutil.copyfileobj(source, output)
                target.chmod(0o755 if member.mode & 0o111 else 0o644)
            else:
                raise ValueError("更新包包含非普通文件")
    skill = (destination / "SKILL.md").read_text()
    front = re.match(r"\A---\n(.*?)\n---\n", skill, re.S)
    if not front or f"name: {NAME}" not in front[1].splitlines():
        raise ValueError("更新包的技能标识不匹配")
    if not (destination / "scripts/update_from_gitee.py").is_file():
        raise ValueError("更新包缺少更新入口")
    for ref in re.findall(r"\]\((references/[^)#]+)(?:#[^)]*)?\)", skill):
        if not (destination / ref).is_file():
            raise ValueError("更新包缺少 " + ref)


def exchange(installed, staged):
    # A single filesystem operation leaves a valid entrypoint even across a crash.
    lib = ctypes.CDLL(None, use_errno=True)
    left, right = os.fsencode(installed), os.fsencode(staged)
    if sys.platform == "darwin":
        result = lib.renamex_np(left, right, 2)  # RENAME_SWAP
    elif sys.platform.startswith("linux") and hasattr(lib, "renameat2"):
        result = lib.renameat2(-100, left, -100, right, 2)  # RENAME_EXCHANGE
    else:
        raise OSError("当前平台无法原子替换技能目录")
    if result:
        code = ctypes.get_errno()
        raise OSError(code, os.strerror(code))


def repository_path(url):
    return re.sub(r"\.git$", "", url.replace("git@gitee.com:", "https://gitee.com/"))


def update_checkout(root, remote, ref, revision):
    origin = git("remote", "get-url", "origin", cwd=root).decode().strip()
    if repository_path(origin) != repository_path(remote):
        raise ValueError("安装副本的 origin 与技能更新源不一致")
    branch = git("rev-parse", "--abbrev-ref", "HEAD", cwd=root).decode().strip()
    if "refs/heads/" + branch != ref:
        raise ValueError("请从技能配置的分支更新此安装副本")
    if git("status", "--porcelain", "--untracked-files=normal", cwd=root):
        raise ValueError("安装副本有本地改动，请先处理这些改动再更新")
    head = git("rev-parse", "HEAD", cwd=root).decode().strip()
    if head == revision:
        return "current"
    git("fetch", "--quiet", "--no-tags", "origin", ref, cwd=root)
    fetched = git("rev-parse", "--verify", "FETCH_HEAD^{commit}", cwd=root).decode().strip()
    try:
        git("merge-base", "--is-ancestor", head, fetched, cwd=root)
    except subprocess.CalledProcessError as error:
        if error.returncode == 1:
            raise ValueError("安装副本有独立提交，无法快进到 Gitee 版本") from error
        raise
    git("merge", "--ff-only", "--no-overwrite-ignore", fetched, cwd=root)
    return "updated"


def update(root):
    checkout = (root / ".git").exists()
    if root.name != NAME or (checkout and (root.parent.name != "skills" or not (root / ".git").is_dir())):
        raise ValueError("请从此技能的安装目录执行更新")
    # Stage outside the skills discovery directory. A subsequent caller cleans
    # up a previous interrupted download or the old snapshot after a swap.
    cache = root.parent.parent / ("." + root.parent.name + "-" + NAME + "-sync")
    cache.mkdir(mode=0o700, exist_ok=True)
    with (cache / "lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        work = cache / "transaction"
        if work.exists():
            shutil.rmtree(work)
        remote, ref, subdir = read_source(root)
        line = git("ls-remote", "--exit-code", "--refs", remote, ref).decode().strip()
        revision, actual_ref = line.split("\t")
        if actual_ref != ref or not re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", revision):
            raise ValueError("远端分支返回了无效的提交标识")
        if checkout:
            return update_checkout(root, remote, ref, revision)
        marker = root / REVISION
        if marker.exists() and marker.read_text().strip() == revision:
            return "current"
        work.mkdir(mode=0o700)
        try:
            repo = work / "repo"
            git("init", "--bare", "--quiet", str(repo))
            git("fetch", "--quiet", "--depth=1", "--no-tags", remote, ref, cwd=repo)
            fetched = git("rev-parse", "--verify", "FETCH_HEAD^{commit}", cwd=repo).decode().strip()
            staged = work / "next"
            export_skill(repo, fetched, subdir, staged)
            if read_source(staged) != (remote, ref, subdir):
                raise ValueError("更新包的来源与当前配置不一致")
            (staged / REVISION).write_text(fetched + "\n")
            exchange(root, staged)
        finally:
            shutil.rmtree(work)
        return "updated"


if __name__ == "__main__":
    try:
        print(update(Path(__file__).resolve().parents[1]))
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError, tarfile.TarError) as error:
        if isinstance(error, subprocess.CalledProcessError):
            message = f"Git 命令 {error.cmd[3]} 失败，退出码 {error.returncode}，请检查网络、分支与仓库访问权限"
        else:
            message = str(error)
        sys.exit("更新检查未完成：" + message)
