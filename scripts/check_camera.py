"""检查中文成稿中的素材映射、称名与逐镜拍法。裸镜头输入可用独占一行的 --- 分隔。"""

import argparse
import re
import sys


SPOKEN = re.compile(r"\{[^}]*\}|<[^>]*>|〖[^〗]*〗", re.S)
NUMBER = r"[0-9０-９一二三四五六七八九十百〇零两]+"
SHOT = re.compile(r"^\s*(?:#{1,6}\s*|\*\*)?[【\[]?\s*(?:(?:镜头|镜)\s*" + NUMBER
                  + r"|第\s*" + NUMBER + r"\s*(?:个镜头|镜头|镜)|\d+(?:\.\d+)?\s*[s秒]?\s*"
                    r"[-–—~至]\s*\d+(?:\.\d+)?\s*[s秒])")
SECTION = re.compile(r"^\s*【([^】]+)】\s*(.*)$")
TAG = r"@(?:图片|图像|图|视频|音频|Image|Video|Audio)\s*\d+"
BINDING = re.compile(r"(" + TAG + r")\s*(?:是|为)\s*([^@，,。；;：:\n、]+?)参考[。.]?", re.I)
PRONOUN = re.compile(r"(?<![其吉利排])(?:他|她|它)(?:们)?")
STOP = r"[^，,。；;！？!?\n]"
SUBJECT = r"(?:摄影机|相机|镜头|机位)"
SIZE = r"[单双三多两人面部手胸上过肩背侧平俯仰视角大中小远全近略低正反]{0,10}(?:景|特写)"
FIXED = re.compile(r"(?:固定|锁定)(?:机位|镜头|构图|俯拍|仰拍|侧拍|平拍|" + SIZE + r")|"
                   + SUBJECT + r"(?:全程|始终|保持)?(?:不动|固定|静止|保持原位|留在原位)")
INHERITED = re.compile(r"(?:沿用|保留|继承|复现)" + STOP + r"{1,30}(?:运镜|镜头运动|摄影机运动)")
MOVE = (r"推近|推进|前推|缓推|轻推|推向|推到|推至|后撤|拉远|拉开|后拉|后退|跟移|跟进|跟随|跟着|跟拍|"
        r"横移|侧移|平移|短移|移向|移到|移至|右移|左移|前移|后移|移动|靠近|绕过|环绕|绕行|摇向|摇到|摇至|"
        r"[上下左右]摇|摇摄|升起|升高|上升|下降|降低|俯冲|抬升|转向")
# Only camera-led phrases or an explicit cinematography verb start a move.
MOTION = re.compile(r"(?<!朝)(?<!向)(?<!对着)" + SUBJECT +
                    r"(?:[从由沿随跟向朝往绕在以贴]" + STOP + r"{0,32}?)?"
                    r"(?:同步|缓缓|缓慢|慢慢|快速|短距离|平稳|轻轻|逐渐|略微|开始|轻微|持续|平行|稍稍|小幅|顺势|也)*"
                    r"(?P<verb>" + MOVE + r")"
                    r"|(?<!不)(?P<standalone>跟拍|摇摄|移摄|推镜|拉镜)")
BARE = re.compile(r"^(?:同步|缓慢|快速|轻轻|小幅|平稳|持续|缓缓|慢慢|稍稍|略微|逐渐|顺势|开始|也|轻微)*$")
LANDING = re.compile(r"^[，,。；;\s]*(?:随后|最后|最终|直到|直至)?(?:停在|停到|收在|落在|收至|停稳在|带出|露出|让|把)")
NEGATED = re.compile(r"(?:不要|没有|避免|禁止|无需|不必|不用|不能|不再|不得|不)(?:使用|采用)?$")


def before_match(visual, match):
    return re.split(r"[，,。；;！？!?\n]", visual[:match.start()])[-1].strip()


def camera_choice(shot):
    visual = SPOKEN.sub("", shot)
    for match in MOTION.finditer(visual):
        # Neither a quoted/negated move nor the bare word “跟拍” supplies a shot design.
        previous = before_match(visual, match)
        if NEGATED.search(previous):
            continue
        if match.group("standalone") and previous and not re.fullmatch(r"(?:手持|肩扛|同速|平行|侧面|低位|向[左右前后])*", previous):
            continue
        verb = match.group("verb") or match.group("standalone")
        prefix = match.group().split(verb)[0]
        prefix = re.sub("^" + SUBJECT, "", prefix)
        if re.search(r"不要|不再|不必|避免|禁止|没有|不会|不能|不得|拍到|拍着|看见|看到|只见|记录", prefix):
            continue
        rest = visual[match.end():]
        end = re.split(r"[，,。；;！？!?\n]", rest, maxsplit=1)[0].strip()
        if not BARE.fullmatch(prefix) or (end and not BARE.fullmatch(end)) or LANDING.match(rest):
            return "运动"
    for pattern, kind in ((INHERITED, "沿用"), (FIXED, "固定")):
        if any(not NEGATED.search(before_match(visual, m)) for m in pattern.finditer(visual)):
            return kind
    return None


def separated(text):
    return re.split(r"(?m)^[ \t]*---[ \t]*\r?$", text)


def check_prompt_format(text, errors, reviews):
    # Ignore quoted speech and literal on-screen text when checking authoring instructions.
    prose = SPOKEN.sub("", text)
    lines = [line.strip() for line in prose.splitlines() if line.strip()]
    if not any(line.startswith(("【生成目标】", "【参考素材职责】", "【事件脚本】", "【保持一致】", "【约束】"))
               for line in lines):
        return  # Existing callers can also submit just the shot text.
    lines.append("")  # An empty final section has no following content.
    suffix = "无bgm，无字幕。"
    goal = ""
    if lines[0].startswith("【生成目标】"):
        goal = lines[0][len("【生成目标】"):].strip() or lines[1]
    if not goal.endswith(suffix) or not goal[:-len(suffix)].strip() or goal.startswith("【"):
        errors.append("把“无bgm，无字幕。”接在【生成目标】的正文句末，同一行写完。")
    if len(re.findall(r"无\s*bgm\s*[,，、]\s*无字幕", prose, re.I)) > 1:
        errors.append("每个提交段只在生成目标写一次声音与字幕要求。")
    if any(line.startswith("【约束】") for line in lines):
        errors.append("清理旧约束栏；有承接依据的内容才移入【保持一致】。")
    for i, line in enumerate(lines):
        if line.startswith("【保持一致】"):
            content = line[len("【保持一致】"):].strip() or lines[i+1]
            if not content or content.startswith("【") or content.rstrip("。.") in ("无", "无须", "保持一致"):
                errors.append("没有具体承接内容时省去【保持一致】整栏。")
            elif re.fullmatch(r"(?:保持|确保)?(?:(?:人物身份|人物数量|角色|人物|服装|场景|道具|站位|光线|画质)[、，和与及 ]*)+"
                              r"(?:均|始终|前后)?(?:保持)?(?:一致|稳定|连续)[。.]?", content):
                reviews.append("保持项只列了类别。核对本段究竟要承接哪个对象的什么状态，缺少依据就删去。")
    if re.search(r"(?:无|没有|不(?:得|要)?(?:出现|新增|添加))\s*(?:其他|其它|额外|多余)(?:的)?(?:人物|人员|人|角色|道具|物品)", prose):
        reviews.append("核对排除项的剧本或素材依据。如果已写清入镜内容，删去这项。")


def prompt_parts(text):
    shots, reference_lines, outside = [], [], []
    section, current, numbered = "", None, False
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if section == "保持一致" and not SECTION.match(line):
            outside.append(line)
            continue
        if SHOT.match(line):
            section, numbered = "镜头", True
            current = []
            shots.append(current)
        else:
            heading = SECTION.match(line)
            if heading:
                section, line = heading.groups()
                current, numbered = None, False
                if not line:
                    continue
            if section == "参考素材职责":
                reference_lines.append(line)
                continue
            if section not in ("事件脚本", "镜头", "分镜", "镜头脚本", "分镜脚本", "分镜设计", "画面", ""):
                outside.append(line)
                continue
            if not numbered and current is None:
                current = []
                shots.append(current)
        current.append(line)
    return ["\n".join(lines) for lines in shots], reference_lines, outside


def inspect(text, prompt=False, expected=None, allowed_fixed=()):
    errors, reviews = [], []
    if prompt:
        check_prompt_format(text, errors, reviews)
        shots, bindings, outside = prompt_parts(text)
        seen = set()
        for line in bindings:
            match = BINDING.fullmatch(line)
            if not match or re.search(r"(?:用于|用作|包括|负责|保持一致|保留原|严格还原)", match[2]):
                errors.append("素材行只留“标签是名称的用途参考。”：" + line)
                continue
            if re.search(r"穿着|身穿|摆放|左侧有|右侧有|结构为|布局为|衣服颜色", match[2]):
                reviews.append("核对素材名称；衣着或布局描述应移出绑定行：" + line)
            tag = re.sub(r"\s+", "", match[1]).lower()
            if tag in seen:
                errors.append("同一素材重复绑定：" + match[1])
            seen.add(tag)
        for line in outside + shots:
            if re.search(TAG, SPOKEN.sub("", line), re.I):
                errors.append("素材标签应移回【参考素材职责】：" + line.splitlines()[0][:32])
        if any(PRONOUN.search(SPOKEN.sub("", line)) for line in outside):
            reviews.append("镜头以外的说明出现代词，核对绑定名或省主语。")
    else:
        shots = separated(text)
    if expected is not None and len(shots) != expected:
        errors.append(f"应逐镜检查 {expected} 镜，实际识别 {len(shots)} 镜。按真实切点分开原文再验。")
    if not shots:
        errors.append("没有识别出镜头正文。")
    fixed = set()
    for index, shot in enumerate(shots, 1):
        choice = camera_choice(shot)
        if not choice:
            errors.append(f"第{index}镜缺少可辨的拍法或运动对象、方向、落幅。")
        elif choice == "固定":
            fixed.add(index)
        elif choice == "运动" and not re.search(
                r"停|收在|收到|收至|落在|落幅|落到|推到|推至|拉远到|摇到|露出|带出|同框|同速|始终|保持|仍能|直至|直到",
                SPOKEN.sub("", shot)):
            reviews.append(f"第{index}镜核对落幅：最后看清什么，或跟拍中保持什么构图？")
        if PRONOUN.search(SPOKEN.sub("", shot)):
            reviews.append(f"第{index}镜有第三人称代词，优先用名称或省主语。")
    if prompt or expected is not None:
        for index in sorted(fixed - set(allowed_fixed)):
            errors.append(f"第{index}镜用了固定：先核对为何必须保持这个画框。有具体依据才将镜序列入 --fixed，否则改写运动。")
        for index in sorted(set(allowed_fixed) - fixed):
            errors.append(f"--fixed 中的第{index}镜与成稿中识别的固定镜不符。")
    return errors, list(dict.fromkeys(reviews))


def missing_camera(text):
    return [n for n, shot in enumerate(separated(text), 1) if not camera_choice(shot)]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prompt", action="store_true", help="逐段传入含各栏的最终提示词")
    parser.add_argument("--shots", type=int, help="分镜实际镜数")
    parser.add_argument("--fixed", nargs="+", type=int, default=[], metavar="N", help="逐镜确认有依据的固定镜序，从 1 起算")
    args = parser.parse_args()
    errors, reviews = inspect(sys.stdin.read(), args.prompt, args.shots, args.fixed)
    for message in errors + reviews:
        print(message)
    if not errors and not reviews:
        print("各镜均找到摄影机表达。请继续核对拍法与表演是否符合本场戏。")
    sys.exit(1 if errors else 0)
