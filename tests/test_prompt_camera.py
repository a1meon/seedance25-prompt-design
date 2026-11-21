"""Regression cases for checking the actual text delivered to a user."""
from pathlib import Path
import sys
import unittest

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE / "scripts"))
import check_camera as camera


class PromptChecks(unittest.TestCase):
    def test_neither_another_shot_nor_a_reference_can_supply_the_move(self):
        text = """【生成目标】
摄影机随周遥向右横移。无bgm，无字幕。
【参考素材职责】
@视频1是走廊跟拍的运镜参考。
【事件脚本】
镜头一，摄影机随周遥向画右横移，周遥停步时停在侧脸。
镜头二，手持拍摄。林岚向画右走近，焦点由车票转到林岚的脸上。
镜头三，切中景。林岚对周遥说 {她说过，摄影机跟着你后退。}
【保持一致】
门边停步的镜头沿用母版的固定机位。"""
        errors, reviews = camera.inspect(text, True, 3)
        self.assertEqual(len(errors), 2)
        self.assertTrue(errors[0].startswith("第2镜"))
        self.assertTrue(errors[1].startswith("第3镜"))
        self.assertFalse(reviews)

    def test_simple_binding_reused_name_and_original_dialogue(self):
        text = """【生成目标】
林岚把车票还给周遥。无bgm，无字幕。
【参考素材职责】
@图片2是林岚的人物参考。
@图片5是车票的道具参考。
@Audio 3 为林岚的音色参考。
【事件脚本】
【镜头1】林岚从画左递出车票，摄影机沿桌边向右短移，停在周遥接住车票的手上。
【镜头2】固定双人中景。林岚松手时，周遥已经收起车票。林岚台词 {她说这是他的。}"""
        self.assertEqual(camera.inspect(text, True, 2, [2]), ([], []))
        verbose = text.replace("的人物参考。", "的人物参考，保留原服装。")
        self.assertTrue(camera.inspect(verbose, True, 2, [2])[0])
        leakage = text.replace("林岚松手时", "@图片2松手时")
        self.assertTrue(camera.inspect(leakage, True, 2, [2])[0])
        pronoun = text.replace("周遥已经收起车票", "她已经收起它")
        self.assertTrue(camera.inspect(pronoun, True, 2, [2])[1])
        garment = text.replace("车票的道具参考。", "礼服的服装参考。")
        self.assertEqual(camera.inspect(garment, True, 2, [2]), ([], []))

    def test_fixed_is_a_deliberate_per_shot_choice(self):
        text = "0–2秒，固定双人中景，两人同时望向画右。\n2–4秒，固定单人近景，林岚等到笑意消失才移开眼。"
        self.assertEqual(len(camera.inspect(text, True, 2)[0]), 2)
        self.assertFalse(camera.inspect(text, True, 2, [1, 2])[0])
        self.assertTrue(camera.inspect(text, True, 3, [1, 2])[0])
        self.assertFalse(camera.inspect("沿用走廊母版的运镜。", expected=1)[0])

    def test_optional_continuity_and_inline_goal_suffix(self):
        prompt = ("【生成目标】\n拍出周遥等答复时的迟疑。无bgm，无字幕。\n"
                  "【事件脚本】\n镜头一，摄影机推近周遥，停在周遥抿住的嘴角。")
        self.assertEqual(camera.inspect(prompt, True, 1), ([], []))
        for bad in (prompt.replace("。无bgm", "。\n无bgm"), prompt + "\n【保持一致】",
                    prompt + "\n【约束】\n无bgm，无字幕。", prompt + "\n无bgm，无字幕。"):
            self.assertTrue(camera.inspect(bad, True, 1)[0])
        edit = prompt + "\n【保持一致】\n镜头一的原对白沿用母版的停顿时点。"
        self.assertEqual(camera.inspect(edit, True, 1), ([], []))
        unnecessary = prompt + "\n【保持一致】\n无其他人物。"
        self.assertTrue(camera.inspect(unnecessary, True, 1)[1])
        categories = prompt + "\n【保持一致】\n人物、服装和场景保持一致。"
        self.assertTrue(camera.inspect(categories, True, 1)[1])
        quoted = prompt + "\n周遥台词 {没有其他人。}"
        self.assertEqual(camera.inspect(quoted, True, 1), ([], []))

    def test_support_actor_action_and_bare_or_negated_moves_do_not_pass(self):
        for phrase in ("手持拍摄。", "镜头缓推。", "切近景，镜头里林岚向前移动。",
                       "林岚举起手机跟拍周遥。", "不要固定机位。", "摄影机不要跟随林岚。",
                       "摄影机在窗边拍着林岚向外移动。", "焦点移向林岚。"):
            with self.subTest(phrase=phrase):
                self.assertIsNone(camera.camera_choice(phrase))
        for phrase in ("摄影机随周遥向画右横移，停在门边。", "摄影机顺势拉远到双人中景。",
                       "摄影机沿桌面短移，在手指碰到车票时停下。", "镜头缓推，停在林岚的脸上。"):
            with self.subTest(phrase=phrase):
                self.assertEqual(camera.camera_choice(phrase), "运动")

    def test_published_examples_pass_as_complete_prompts(self):
        # Shot counts and the justified holds are editorial choices in the
        # briefs and their examples, independent of the parser's classifications.
        samples = (PACKAGE / "references/scenes.md").read_text(encoding="utf-8").split("> 【生成目标】")[1:]
        plans = [(4, [2, 4]), (1, [1]), (1, [1]), (3, [2]), (3, [3]), (1, [1]),
                 (3, [2]), (3, [2]), (1, []), (3, [1, 3])]
        self.assertEqual(len(samples), len(plans))
        for sample, (count, fixed) in zip(samples, plans):
            lines = ["【生成目标】"]
            for line in sample.lstrip("\n").splitlines():
                if not line.startswith(">"):
                    break
                lines.append(line[1:].lstrip())
            with self.subTest(goal=lines[1]):
                self.assertFalse(camera.inspect("\n".join(lines), True, count, fixed)[0])
