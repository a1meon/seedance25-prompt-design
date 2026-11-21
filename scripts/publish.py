"""Fast-forward both release branches to one commit and verify their public heads."""
from pathlib import Path
import subprocess
import sys

sys.dont_write_bytecode = True
from update_from_gitee import read_source


def publish(root):
    def git(*args):
        return subprocess.check_output(["git", *args], cwd=root, text=True, timeout=60).strip()

    source = read_source(root)
    if not source.github or git("symbolic-ref", "HEAD") != source.ref:
        raise ValueError("请在维护仓库的发布分支配置两个更新源后运行")
    if git("status", "--porcelain"):
        raise ValueError("请先提交本次发布的改动")
    target = git("rev-parse", "HEAD")
    failures = []
    for name, url in (("Gitee", source.legacy), ("GitHub", source.github)):
        try:
            if git("ls-remote", "--refs", url, source.ref) != target + "\t" + source.ref:
                git("push", url, target + ":" + source.ref)
            if git("ls-remote", "--refs", url, source.ref) != target + "\t" + source.ref:
                raise ValueError("读回的提交与本次发布目标不一致")
            print(name, target, flush=True)
        except (OSError, ValueError, subprocess.SubprocessError) as error:
            failures.append(f"{name}：{error}")
    if failures:
        raise ValueError("双仓发布未完成。修复后从同一提交重跑。\n" + "\n".join(failures))


if __name__ == "__main__":
    try:
        publish(Path(__file__).resolve().parents[1])
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        sys.exit(str(error))
