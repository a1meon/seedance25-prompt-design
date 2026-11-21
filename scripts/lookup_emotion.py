"""在随技能提供的中文表演索引中查找词条，多个检索词分别返回候选。"""

import argparse
from pathlib import Path
import re
import unicodedata


INDEX = Path(__file__).resolve().parents[1] / "references" / "emotion-index.md"


def normalize(text):
    return unicodedata.normalize("NFKC", text).strip().casefold()


def read_entries():
    family = ""
    for line in INDEX.read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):
            family = line[3:]
        if not line.startswith("| ") or line.startswith("| 主词 "):
            continue
        word, aliases, direct, close, wide = (s.strip() for s in line.strip("|").split("|"))
        yield family, word, aliases.split("、"), direct, close, wide


def score(query, entry):
    family, word, aliases, direct, close, wide = entry
    if query == normalize(word):
        return 5
    terms = [normalize(term) for term in [word, *aliases]]
    if query in terms:
        return 4
    if any(query in term for term in terms):
        return 3
    if any(len(term) >= 2 and term in query for term in terms):
        return 2
    return int(any(query in normalize(field) for field in (family, direct, close, wide)))


def print_matches(query, entries, limit):
    ranked = sorted(((score(query, row), row) for row in entries),
                    key=lambda item: -item[0])
    hits = [row for weight, row in ranked if weight]
    for family, word, _, direct, close, wide in hits[:limit]:
        print(f"{family} / {word}\n面部或声音演法：{direct}，{close}。\n身体演法（{word}）：{wide}。\n")
    if not hits:
        print("未命中。按剧本找这一拍的触发、人物想做的事和可见反应。遇到抽象演技评语，查 references/script-to-performance.md 的「把抽象评语落实到当下的戏」。")


def emotion_parts(query):
    # Only decompose explicitly marked relationships. Leave ordinary negated
    # words such as “不甘” and idioms that already have an entry intact.
    forms = (
        (r"先(.+?)[,、\s]*(?:然后|随后|再|后)(.+)", ("先", "再")),
        (r"(?:既|又)(.+?)[,、\s]*又(.+)", ("同时", "也有")),
        (r"(?:表面上?|外表)(.+?)[,、\s]*(?:内心|心里|其实)(.+)", ("外显", "内心")),
        (r"不是(.+?)[,、\s]*(?:而是|只是|是)(.+)", ("排除", "采用")),
    )
    for pattern, labels in forms:
        match = re.fullmatch(pattern, query)
        if match:
            return list(zip(labels, (part.strip() for part in match.groups())))
    return []


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("terms", nargs="+", help="情绪、剧本口语或表演表达")
    parser.add_argument("--limit", type=int, default=4, help="每个检索词的候选数，默认 4")
    args = parser.parse_args()
    if args.limit < 1 or not all(normalize(q) for q in args.terms):
        parser.error("请输入非空词语及正数候选数")
    entries = list(read_entries())
    for term in args.terms:
        print(f"【{term}】")
        query = normalize(term)
        parts = emotion_parts(query)
        if parts and not any(score(query, row) >= 4 for row in entries):
            for stage, part in parts:
                print(f"{stage}：{part}")
                if stage != "排除":
                    print_matches(part, entries, args.limit)
        else:
            print_matches(query, entries, args.limit)


if __name__ == "__main__":
    main()
