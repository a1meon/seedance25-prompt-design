"""Check the configured Gitee branch and replace the installed skill in place."""
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
import time

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
    config = json.loads((root / SOURCE).read_text(encoding="utf-8-sig"))
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
    skill = (destination / "SKILL.md").read_text(encoding="utf-8")
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
    if os.name != "nt":
        import fcntl
        fcntl.flock(lock, fcntl.LOCK_EX)
        return

    import msvcrt
    lock.seek(0)
    deadline = time.monotonic() + 180
    while True:
        try:
            msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
            return  # Closing the file releases the byte-range lock.
        except OSError as error:
            if error.errno not in (errno.EACCES, errno.EAGAIN, errno.EDEADLK):
                raise
            if time.monotonic() >= deadline:
                raise TimeoutError("另一更新进程仍持有安装锁") from error
            time.sleep(0.25)


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
    with (cache / "lock").open("a+b") as lock:
        lock_update(lock)
        work = cache / "transaction"
        if work.exists():
            discard(work)
        pending = cache / "pending"
        resumed = pending.exists()
        if resumed:
            finish_windows_update(root, pending, work)
            discard(work)
        remote, ref, subdir = read_source(root)
        try:
            line = git("ls-remote", "--exit-code", "--refs", remote, ref).decode().strip()
        except (OSError, subprocess.SubprocessError) as error:
            if resumed:
                raise OSError("上次中断的更新已在本地完成，本次查询 Gitee 版本失败") from error
            raise
        revision, actual_ref = line.split("\t")
        if actual_ref != ref or not re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", revision):
            raise ValueError("远端分支返回了无效的提交标识")
        if checkout:
            return update_checkout(root, remote, ref, revision)
        marker = root / REVISION
        if marker.exists() and marker.read_text(encoding="ascii").strip() == revision:
            return "updated" if resumed else "current"
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
        print(update(args.install_dir.resolve(strict=True)))
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError, tarfile.TarError) as error:
        if isinstance(error, subprocess.CalledProcessError):
            message = f"Git 命令 {error.cmd[3]} 失败，退出码 {error.returncode}，请检查网络、分支与仓库访问权限"
        else:
            message = str(error)
        sys.exit("更新检查未完成：" + message)
