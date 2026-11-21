"""List feedback or submit one sanitized issue to the skill's Gitee repository."""

import argparse
from http.client import HTTPException
import json
import os
from pathlib import Path
import re
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import build_opener, HTTPRedirectHandler, Request


OWNER = "a1meon_admin"
REPO = "seedance25_prompt"
API = "https://gitee.com/api/v5/repos/" + OWNER
ISSUES = f"https://gitee.com/{OWNER}/{REPO}/issues"


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def gitee(path, token, fields=None):
    headers = {"Accept": "application/json"}
    data = None
    if fields is None:
        if token:
            headers["Authorization"] = "Bearer " + token
    else:
        data = urlencode(dict(fields, access_token=token)).encode("ascii")
    request = Request(API + path, data=data, headers=headers)
    with build_opener(NoRedirect()).open(request, timeout=20) as response:
        return json.load(response)


def list_issues(token):
    page = 1
    while True:
        batch = gitee(f"/{REPO}/issues?state=all&per_page=100&page={page}", token)
        if not isinstance(batch, list):
            raise ValueError("未收到 Gitee Issue 列表")
        yield from batch
        if len(batch) < 100:
            return
        page += 1


def issue_url(issue):
    number = str(issue["number"])
    if not re.fullmatch(r"[a-zA-Z0-9]+", number):
        raise ValueError("Gitee 响应缺少有效的 Issue 编号")
    return f"{ISSUES}/{number}"


def normalized_title(title):
    return " ".join(title.split()).casefold()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("list", help="查看已开及已关闭的 Issue")
    create = commands.add_parser("create", help="提交一份已脱敏的报告，同标题返回已有链接")
    create.add_argument("--title", required=True)
    create.add_argument("--body-file", required=True, type=Path)
    args = parser.parse_args()
    token = os.environ.get("GITEE_ACCESS_TOKEN")
    if args.command == "list":
        for issue in list_issues(token):
            print(issue_url(issue), issue["state"], issue["title"])
        return

    if not token:
        parser.exit(1, "创建需要 GITEE_ACCESS_TOKEN，或使用已登录的 Gitee 工具。\n")
    title = args.title.strip()
    body = args.body_file.read_text(encoding="utf-8").strip()
    if not title or not body:
        parser.error("标题和正文都需要有内容")
    for issue in list_issues(token):
        if normalized_title(issue["title"]) == normalized_title(title):
            print("existing", issue_url(issue))
            return

    try:
        result = gitee("/issues", token, {"repo": REPO, "title": title, "body": body})
        url = issue_url(result)
    except (HTTPException, OSError, ValueError, KeyError, TypeError) as error:
        sys.exit(f"未确认 Issue 已创建（{error_label(error)}）。请先查询仓库核对结果。")
    print("created", url)


def error_label(error):
    if isinstance(error, HTTPError):
        return f"HTTP {error.code}"
    if isinstance(error, URLError):
        return f"网络连接失败：{type(error.reason).__name__}"
    return type(error).__name__


if __name__ == "__main__":
    try:
        main()
    except (HTTPException, OSError, ValueError, KeyError, TypeError) as error:
        sys.exit(f"反馈查询或准备失败（{error_label(error)}）。")
