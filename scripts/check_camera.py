"""逐镜提示中文成稿中可能遗漏的摄影机选择。标准输入每镜以独占一行的 --- 分隔。"""

import re
import sys


CAMERA = re.compile(
    r"(?:固定|锁定)(?:机位|镜头|构图|俯拍|仰拍|侧拍|平拍|[单双三多两人面部手胸上过肩背侧平俯仰视角大中小远全近略低正反]{0,10}(?:景|特写))"
    r"|(?:镜头|摄影机|相机|机位)(?:全程|始终|保持)?(?:不动|固定|静止)"
    r"|(?:摄影机|相机|镜头)(?!里|内|中|前景|外|[一二三四五六七八九十\d])"
    r"[^，。；！？\n]{0,32}(?:推近|推进|前推|缓推|轻推|推向|推到|推至|拉远|拉开|后拉|后退|跟移|跟进|跟随|跟着|"
    r"横移|侧移|平移|移向|移到|移至|环绕|绕行|摇向|摇到|摇至|[上下左右]摇|升起|升高|下降|降低|俯冲)"
    r"|跟拍|摇摄|移摄|推镜|拉镜|手持拍摄|手持跟|肩扛跟"
    r"|(?:沿用|保留|保持|继承|复现)[^，。；！？\n]{0,36}(?:运镜|镜头运动|摄影机运动)"
)


def missing_camera(text):
    shots = re.split(r"(?m)^[ \t]*---[ \t]*\r?$", text)
    missing = []
    for number, shot in enumerate(shots, 1):
        visual = re.sub(r"\{[^}]*\}|<[^>]*>", "", shot)
        if not CAMERA.search(visual):
            missing.append(number)
    return missing


if __name__ == "__main__":
    missing = missing_camera(sys.stdin.read())
    if missing:
        sys.exit("请回读以下镜序的摄影机选择：" + "、".join(map(str, missing)))
    print("各镜均找到摄影机表达；继续核对其动机、表演、可见范围和观众方位。")
