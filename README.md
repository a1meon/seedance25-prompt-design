# seedance2.5提示词设计-v1.0

把剧本、分镜设想或已有提示词写成可直接提交的 Seedance 2.5 视频提示词。给出分镜时沿用原有设计；只有剧本时，按人物意图设计机位、切点和走位。每张可辨的脸都有符合前情的视线、情绪和表演。

## 【通过agent使用】

> 请从 https://gitee.com/a1meon_admin/seedance25_prompt.git 的 main 分支下载最新版，将仓库内容（不含 .git）作为 seedance25-prompt-design-v1-0 安装到你当前的个人技能目录，已有同名技能就用自带更新器原位更新，完成后确认能发现 SKILL.md 并调用该技能。

## 安装与使用

将上面一句话发给 Codex、Claude Code 或其他支持 `SKILL.md` 的 Agent。技能目录名为 `seedance25-prompt-design-v1-0`，其下一层就是 `SKILL.md`、`references/` 和 `scripts/`。沿用当前工具已经发现的个人技能目录。Claude Code 默认为 `~/.claude/skills/`，本项目使用的 Codex 安装器默认为 `~/.codex/skills/`。首次安装后从安装位置执行 `python3 scripts/update_from_gitee.py` 核对版本，之后每次使用都会先检查并原位更新。更新器需要 Git、Python 3，以及支持原子目录交换的 macOS 或 Linux 环境。

可以直接说“用这个技能把下面的剧本写成视频提示词，保留我给的分镜”。在同一对话里也可以接着说“第二镜让她更委屈一点，目光不要移开”。

交付前会逐镜核对四件事：摄影机固定或移动的选择是否合乎剧情，每张可辨的脸是否演出了前情，画面句是否只写当时能看见的人物和物件，以及站位与视线是否从观众所在的机位说清。

## 怎样确认已更新

`v1.0` 是技能名称的一部分。每次发布在 Gitee `main` 上产生新的提交号。常规安装从首次发布起就用安装目录的 `.gitee-revision` 与远端提交号比较，有变化就原位替换。运行 `python3 scripts/update_from_gitee.py` 后，`updated` 表示已更新，`current` 表示已与远端一致。

若早期把仓库直接克隆进了个人 `skills/seedance25-prompt-design-v1-0/`，旧更新器会因目录含 `.git` 而提示“请从此技能的安装目录执行更新”。让 Agent 在该目录确认 `origin` 是本仓库、当前分支为 `main`、工作区干净，然后执行一次 `git pull --ff-only origin main`。此后的每次调用自动比较本地 `HEAD` 并快进更新。若有本地改动或分叉，更新器会保留现场，报告具体原因。

## 使用反馈

安装、更新、写提示词或看完成片时都可以告诉 Agent 哪里出了问题。用于调优的 Issue 会带上问题简述、当时的完整提示词、当次输入的完整剧本，以及每个实际使用的图片、音频、视频等参考素材原件，并保留 `@编号 → 用途` 的对应关系。材料可放在 Issue 正文、附件或维护者能打开的原文件链接中。已有同类 Issue 时，新案例补在原帖下。提交依据使用者对这些完整材料的本次或持续授权。[仓库 Issues](https://gitee.com/a1meon_admin/seedance25_prompt/issues)
