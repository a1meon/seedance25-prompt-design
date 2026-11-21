"""List issues, submit a complete tuning case, or add it to an existing issue."""

import argparse
from http.client import HTTPException
import ipaddress
import json
import os
from pathlib import Path
import re
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import build_opener, HTTPRedirectHandler, Request


OWNER = "a1meon_admin"
REPO = "seedance25_prompt"
API = "https://gitee.com/api/v5/repos/" + OWNER
ISSUES = f"https://gitee.com/{OWNER}/{REPO}/issues"
SECTIONS = ("问题简述", "完整提示词", "完整剧本", "参考素材")


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


def pages(path, token, filters=""):
    page = 1
    while True:
        batch = gitee(f"{path}?{filters}per_page=100&page={page}", token)
        if not isinstance(batch, list):
            raise ValueError("未收到 Gitee 列表")
        yield from batch
        if len(batch) < 100:
            return
        page += 1


def list_issues(token):
    return pages(f"/{REPO}/issues", token, "state=all&")


def issue_url(issue):
    number = str(issue["number"])
    if not re.fullmatch(r"[a-zA-Z0-9]+", number):
        raise ValueError("Gitee 响应缺少有效的 Issue 编号")
    return f"{ISSUES}/{number}"


def normalized_title(title):
    return " ".join(title.split()).casefold()


def web_submission_help(page):
    return (f"可通过网页提交。首次使用可在 https://gitee.com/signup 注册，"
            f"已有账号可在 https://gitee.com/login 登录，再打开 {page}。\n")


def has_file_link(line):
    for url in re.findall(r"https://[^\s)<>]+", line):
        parts = urlsplit(url)
        host = (parts.hostname or "").rstrip(".")
        if not host or parts.username is not None or host == "localhost" or host.endswith(".localhost"):
            continue
        try:
            address = ipaddress.ip_address(host)
        except ValueError:
            return True
        if not address.is_loopback and not address.is_unspecified:
            return True
    return False


def read_case(path):
    body = path.read_text(encoding="utf-8-sig").strip()
    sections = {}
    with_original_text = set()
    current = None
    fence = ""
    for line in body.splitlines():
        if fence:
            candidate = line.strip()
            if candidate.startswith(fence) and not candidate.strip(fence[0]):
                fence = ""
            elif candidate:
                with_original_text.add(current)
        else:
            opening = re.match(r"^ {0,3}(`{3,}|~{3,})", line)
            if opening:
                fence = opening[1]
            elif line.startswith("## ") and line[3:].strip() in SECTIONS:
                current = line[3:].strip()
                if current in sections:
                    raise ValueError(f"重复栏目：{current}")
                sections[current] = []
                continue
        if current is not None:
            sections[current].append(line)
    if fence:
        raise ValueError("原文的 Markdown 代码围栏未闭合")
    for name in SECTIONS:
        if not any(line.strip() for line in sections.get(name, [])):
            raise ValueError(f"缺少内容：{name}")
    for name, absent in (("完整提示词", "本次尚未生成提示词"), ("完整剧本", "本次未提供剧本")):
        lines = sections[name]
        value = "\n".join(lines).strip()
        if value.rstrip("。") == absent or any(has_file_link(line) for line in lines):
            continue
        if name not in with_original_text:
            raise ValueError(f"{name}需提供围栏内的全文、原文件 HTTPS 链接或当次确实没有的说明")
    assets = [line.strip() for line in sections["参考素材"] if line.strip()]
    for line in assets:
        if line.rstrip("。") == "本次未使用参考素材" or "仅预留，未绑定" in line:
            continue
        if not has_file_link(line):
            raise ValueError("参考素材每行需附原件的 HTTPS 链接；尚未绑定的预留槽需标明")
    return body


def supplement(number, body, token):
    url = issue_url({"number": number})
    path = f"/{REPO}/issues/{number}"
    issue = gitee(path, token)
    if (issue.get("body") or "").replace("\r\n", "\n").strip() == body:
        print("existing", url)
        return
    comments = path + "/comments"
    for comment in pages(comments, token):
        if (comment.get("body") or "").replace("\r\n", "\n").strip() == body:
            print("existing", url)
            return
    result = gitee(comments, token, {"body": body})
    if not result.get("id"):
        raise ValueError("Gitee 响应缺少评论编号")
    print("supplemented", url)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("list", help="查看已开及已关闭的 Issue")
    create = commands.add_parser("create", help="新建有调优价值的案例，同标题只返回原 Issue 链接")
    create.add_argument("--title", required=True)
    extra = commands.add_parser("supplement", help="向已有 Issue 提交能帮助定位问题或验证修复的新证据")
    extra.add_argument("--issue", required=True, help="原 Issue 编号")
    check = commands.add_parser("check", help="在本地检查完整材料报告的栏目和附件链接格式")
    for command in (create, extra, check):
        command.add_argument("--body-file", required=True, type=Path)
    args = parser.parse_args()
    token = os.environ.get("GITEE_ACCESS_TOKEN")
    if args.command == "list":
        for issue in list_issues(token):
            print(issue_url(issue), issue["state"], issue["title"])
        return

    if args.command == "create":
        title = args.title.strip()
        if not title:
            parser.error("标题需要有内容")
        try:
            for issue in list_issues(token):
                if normalized_title(issue["title"]) == normalized_title(title):
                    print("existing", issue_url(issue))
                    return
        except HTTPError as error:
            if not token and error.code in (401, 403):
                parser.exit(1, web_submission_help(ISSUES))
            raise
    try:
        body = read_case(args.body_file)
    except ValueError as error:
        parser.error(str(error))
    if args.command == "check":
        print("四项栏目与附件链接格式通过")
        return
    if not token:
        page = issue_url({"number": args.issue}) if args.command == "supplement" else ISSUES
        parser.exit(1, web_submission_help(page))

    try:
        if args.command == "supplement":
            supplement(args.issue, body, token)
            return
        result = gitee("/issues", token, {"repo": REPO, "title": title, "body": body})
        url = issue_url(result)
    except (HTTPException, OSError, ValueError, KeyError, TypeError) as error:
        sys.exit(f"未确认报告已提交（{error_label(error)}）。请先查询原帖和评论。")
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
