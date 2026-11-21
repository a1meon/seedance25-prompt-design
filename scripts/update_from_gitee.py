"""Check the release branch and update the installed skill in place."""
import argparse
import ctypes
import errno
import io
import json
import ntpath
import os
from pathlib import Path, PurePosixPath, PureWindowsPath
import re
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
from typing import NamedTuple, Optional

NAME = "seedance25-prompt-design-v1-0"
SOURCE = "gitee-source.json"
REVISION = ".gitee-revision"
PROBE_SECONDS = 6
FETCH_SECONDS = 20


class Source(NamedTuple):
    legacy: str
    github: Optional[str]
    ref: str
    subdir: str

    @property
    def primary(self):
        return self.github or self.legacy

    def accepts(self, candidate):
        # The Gitee bridge may introduce GitHub once. Subsequent packages
        # must keep that destination and the legacy settings used by old clients.
        return (self.legacy == candidate.legacy and self.ref == candidate.ref
                and self.subdir == candidate.subdir
                and (self.github is None or self.github == candidate.github))


class RemoteUnavailable(Exception):
    pass


def git(*args, cwd=None, timeout=15):
    env = dict(os.environ, GIT_TERMINAL_PROMPT="0", GCM_INTERACTIVE="Never")
    return subprocess.run(
        ["git", "-c", "core.hooksPath=/dev/null", *args], cwd=cwd, env=env,
        stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        check=True, timeout=timeout,
    ).stdout


def remote_git(*args, cwd=None, timeout):
    # Files avoid waiting on pipe handles inherited by a credential/transport
    # helper after the top-level Git process times out (notably on Windows).
    env = dict(os.environ, GIT_TERMINAL_PROMPT="0", GCM_INTERACTIVE="Never")
    command = ["git", "-c", "core.hooksPath=/dev/null", "-c", "http.lowSpeedLimit=1",
               "-c", "http.lowSpeedTime=" + str(timeout), *args]
    with tempfile.TemporaryFile() as out, tempfile.TemporaryFile() as err:
        with subprocess.Popen(command, cwd=cwd, env=env, stdin=subprocess.DEVNULL,
                              stdout=out, stderr=err, start_new_session=os.name != "nt") as proc:
            try:
                proc.wait(timeout=timeout)
            except subprocess.TimeoutExpired as error:
                if os.name == "nt":
                    try:
                        subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=2)
                    except (OSError, subprocess.TimeoutExpired):
                        pass
                else:
                    import signal
                    try:
                        os.killpg(proc.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                proc.kill()
                raise RemoteUnavailable from error
        if proc.returncode:
            if args[0] == "ls-remote" and proc.returncode == 2:
                raise ValueError("远端缺少技能配置的分支")
            raise RemoteUnavailable
        out.seek(0)
        return out.read()


def parse_source(data):
    config = json.loads(data)
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
    github = config.get("github_repository")
    if github is not None and (not isinstance(github, str) or not re.fullmatch(
        r"https://github\.com/[a-zA-Z0-9-]+/[\w.-]+", github
    ) or github.rsplit("/", 1)[1] in (".", "..")):
        raise ValueError("GitHub 更新源需要使用仓库的 HTTPS 地址")
    return Source(remote, github, "refs/heads/" + branch, subdir)


def read_source(root):
    return parse_source((root / SOURCE).read_text(encoding="utf-8-sig"))


def configured_source(root, bootstrap):
    source = read_source(root)
    if bootstrap and bootstrap != root and not source.github:
        helper_source = read_source(bootstrap)
        if source.accepts(helper_source):
            return helper_source
    return source


def export_skill(repo, revision, subdir, destination):
    tree = revision if subdir == "." else f"{revision}:{subdir}"
    archive = git("archive", "--format=tar", tree, cwd=repo)
    destination.mkdir()
    with tarfile.open(fileobj=io.BytesIO(archive), mode="r:") as tar:
        for member in tar:
            path = PurePosixPath(member.name)
            if path.is_absolute() or ".." in path.parts or ".git" in path.parts or path.name == REVISION:
                raise ValueError("更新包路径无效")
            if sys.platform == "win32" and any(
                re.search(r'[<>:"\\|?*\x00-\x1f]', part) or part.endswith((" ", "."))
                or windows_reserved(part) or part.lower() in (".git", REVISION)
                for part in path.parts
            ):
                raise ValueError("更新包路径与 Windows 不兼容")
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
    verify_skill(destination)


def verify_skill(destination):
    skill = (destination / "SKILL.md").read_text(encoding="utf-8-sig")
    front = re.match(r"\A---\n(.*?)\n---\n", skill, re.S)
    if not front or f"name: {NAME}" not in front[1].splitlines():
        raise ValueError("更新包的技能标识不匹配")
    if not (destination / "scripts/update_from_gitee.py").is_file():
        raise ValueError("更新包缺少更新入口")
    for ref in re.findall(r"\]\((references/[^)#]+)(?:#[^)]*)?\)", skill):
        if not (destination / ref).is_file():
            raise ValueError("更新包缺少 " + ref)


def windows_reserved(part):
    if hasattr(ntpath, "isreserved"):
        return ntpath.isreserved(part)
    return PureWindowsPath(part).is_reserved()  # Python 3.8–3.12


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


def lock_update(lock):
    try:
        if os.name == "nt":
            import msvcrt
            lock.seek(0)
            msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError as error:
        if error.errno in (errno.EACCES, errno.EAGAIN, errno.EDEADLK):
            raise BlockingIOError("另一进程正在检查或安装更新") from error
        raise


def retry_readonly(func, path, exc_info):
    # Git for Windows can leave read-only pack files in the temporary bare repo.
    if (os.name != "nt" or func not in (os.unlink, os.remove, os.rmdir)
            or not os.lstat(path).st_file_attributes & stat.FILE_ATTRIBUTE_READONLY):
        raise exc_info[1]
    os.chmod(path, stat.S_IWRITE)
    func(path)


def discard(path):
    if path.is_symlink():
        path.unlink()
    elif path.is_dir():
        shutil.rmtree(path, onerror=retry_readonly)
    else:
        try:
            path.unlink()
        except PermissionError:
            retry_readonly(os.unlink, path, sys.exc_info())


def install_file(source, target):
    if target.is_file() and target.read_bytes() == source.read_bytes():
        return
    with tempfile.NamedTemporaryFile(dir=target.parent, delete=False) as output:
        temporary = Path(output.name)
    try:
        shutil.copyfile(source, temporary)
        if os.name == "nt" and target.exists():
            if target.stat().st_file_attributes & stat.FILE_ATTRIBUTE_READONLY:
                target.chmod(stat.S_IWRITE)
        os.replace(temporary, target)
    finally:
        if temporary.exists():
            temporary.unlink()


def sync_windows_tree(source, target):
    # Keep the live root, especially SKILL.md and the updater, addressable.
    for item in source.iterdir():
        if item.name == REVISION:
            continue
        dest = target / item.name
        if dest.exists() or dest.is_symlink():
            attrs = getattr(dest.lstat(), "st_file_attributes", 0)
            if dest.is_symlink() or attrs & stat.FILE_ATTRIBUTE_REPARSE_POINT:
                raise ValueError(f"安装路径包含重解析点或符号链接：{dest}")
            if dest.is_dir() != item.is_dir():
                discard(dest)
        if item.is_dir():
            dest.mkdir(exist_ok=True)
            sync_windows_tree(item, dest)
        else:
            install_file(item, dest)
    for dest in target.iterdir():
        if not (source / dest.name).exists():
            discard(dest)


def finish_windows_update(root, pending, consumed):
    if (root / ".git").exists():
        raise ValueError("不能把待完成的安装包写入 Git 检出目录")
    marker = root / REVISION
    if marker.exists():
        discard(marker)
    sync_windows_tree(pending, root)
    install_file(pending / REVISION, marker)
    # Retire the whole journal before cleanup, so a crash while removing it
    # cannot turn a half-deleted staging tree into the next recovery source.
    pending.rename(consumed)


def repository_path(url):
    url = re.sub(r"^(?:git@|ssh://git@)(github\.com|gitee\.com)[:/]", r"https://\1/", url)
    return re.sub(r"\.git$", "", url)


def update_checkout(root, source, revision):
    origin = git("config", "--get", "remote.origin.url", cwd=root).decode().strip()
    if repository_path(origin) not in {repository_path(source.legacy), repository_path(source.primary)}:
        raise ValueError("安装副本的 origin 与技能更新源不一致")
    branch = git("rev-parse", "--abbrev-ref", "HEAD", cwd=root).decode().strip()
    if "refs/heads/" + branch != source.ref:
        raise ValueError("请从技能配置的分支更新此安装副本")
    if git("status", "--porcelain", "--untracked-files=normal", cwd=root):
        raise ValueError("安装副本有本地改动，请先处理这些改动再更新")
    head = git("rev-parse", "HEAD", cwd=root).decode().strip()
    if head == revision:
        return "current"
    remote_git("fetch", "--quiet", "--no-tags", source.primary, source.ref, cwd=root, timeout=FETCH_SECONDS)
    fetched = git("rev-parse", "--verify", "FETCH_HEAD^{commit}", cwd=root).decode().strip()
    try:
        git("merge-base", "--is-ancestor", head, fetched, cwd=root)
    except subprocess.CalledProcessError as error:
        if error.returncode == 1:
            raise ValueError("安装副本有独立提交，无法快进到远端版本") from error
        raise
    if not source.accepts(parse_source(git("show", fetched + ":" + SOURCE, cwd=root))):
        raise ValueError("更新包的来源与当前配置不一致")
    git("merge", "--ff-only", "--no-overwrite-ignore", fetched, cwd=root)
    return "updated"


def update(root, bootstrap=None):
    checkout = (root / ".git").exists()
    if root.name != NAME or (checkout and (root.parent.name != "skills" or not (root / ".git").is_dir())):
        raise ValueError("请从此技能的安装目录执行更新")
    # Stage outside the skills discovery directory. A subsequent caller cleans
    # up a previous interrupted download or the old snapshot after a swap.
    cache = root.parent.parent / ("." + root.parent.name + "-" + NAME + "-sync")
    pending = cache / "pending"
    try:
        cache.mkdir(mode=0o700, exist_ok=True)
        lock = (cache / "lock").open("a+b")
    except PermissionError:
        # Many agent sandboxes can read their installed skills but cannot
        # create the lock. Checking an already-current release needs no write.
        if pending.exists():
            raise
        verify_skill(root)
        source = configured_source(root, bootstrap)
        try:
            available = remote_revision(source)
        except RemoteUnavailable:
            return "offline"
        if checkout:
            installed = git("rev-parse", "HEAD", cwd=root).decode().strip()
        else:
            marker = root / REVISION
            installed = marker.read_text(encoding="ascii").strip() if marker.exists() else None
        return "current" if installed == available else "needs-write"
    with lock:
        try:
            lock_update(lock)
        except BlockingIOError:
            if sys.platform == "win32" or checkout:
                raise  # Another process may be replacing individual files.
            verify_skill(root)
            return "busy"
        work = cache / "transaction"
        if work.exists():
            discard(work)
        resumed = pending.exists()
        if resumed:
            finish_windows_update(root, pending, work)
            discard(work)
        source = configured_source(root, bootstrap)
        try:
            return sync_release(root, source, checkout, resumed, work, pending)
        except RemoteUnavailable:
            verify_skill(root)
            return "updated-offline" if resumed else "offline"


def remote_revision(source):
    line = remote_git("ls-remote", "--exit-code", "--refs", source.primary, source.ref,
                      timeout=PROBE_SECONDS).decode().strip()
    revision, actual_ref = line.split("\t")
    if actual_ref != source.ref or not re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", revision):
        raise ValueError("远端分支返回了无效的提交标识")
    return revision


def sync_release(root, source, checkout, resumed, work, pending):
    revision = remote_revision(source)
    if checkout:
        return update_checkout(root, source, revision)
    marker = root / REVISION
    if marker.exists() and marker.read_text(encoding="ascii").strip() == revision:
        return "updated" if resumed else "current"
    work.mkdir(mode=0o700)
    try:
        repo = work / "repo"
        git("init", "--bare", "--quiet", str(repo))
        remote_git("fetch", "--quiet", "--depth=1", "--no-tags", source.primary, source.ref,
                   cwd=repo, timeout=FETCH_SECONDS)
        fetched = git("rev-parse", "--verify", "FETCH_HEAD^{commit}", cwd=repo).decode().strip()
        staged = work / "next"
        export_skill(repo, fetched, source.subdir, staged)
        if not source.accepts(read_source(staged)):
            raise ValueError("更新包的来源与当前配置不一致")
        (staged / REVISION).write_text(fetched + "\n", encoding="ascii")
        if sys.platform == "win32":
            staged.rename(pending)
            finish_windows_update(root, pending, staged)
        else:
            exchange(root, staged)
    finally:
        discard(work)
    return "updated"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--install-dir", type=Path, default=Path(__file__).resolve().parents[1],
                        help="已有技能安装目录，可用新版更新器引导旧版完成首次升级")
    args = parser.parse_args()
    try:
        print(update(args.install_dir.resolve(strict=True), Path(__file__).resolve().parents[1]))
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError, tarfile.TarError) as error:
        if isinstance(error, subprocess.CalledProcessError):
            message = f"Git 命令 {error.cmd[3]} 失败，退出码 {error.returncode}，请检查网络、分支与仓库访问权限"
        else:
            message = str(error)
        sys.exit("更新检查未完成：" + message)
