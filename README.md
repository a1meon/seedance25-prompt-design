# seedance2.5提示词设计-v1.0

把剧本、分镜设想或已有提示词写成可直接提交的 Seedance 2.5 视频提示词。给出分镜时沿用原有设计；只有剧本时，按人物意图设计机位、切点和走位。每张可辨的脸都有符合前情的视线、情绪和表演。

## 【通过agent使用】

> 请从 https://gitee.com/a1meon_admin/seedance25_prompt.git 的 main 分支下载最新版，将仓库内容（不含 .git）作为 seedance25-prompt-design-v1-0 安装到你当前的个人技能目录，已有同名技能就用自带更新器原位更新，完成后确认能发现 SKILL.md 并调用该技能。

## 安装与使用

将上面一句话发给 Codex、Claude Code 或其他支持 `SKILL.md` 的 Agent。技能目录名为 `seedance25-prompt-design-v1-0`，其下一层就是 `SKILL.md`、`references/` 和 `scripts/`。沿用当前工具已经发现的个人技能目录。Claude Code 默认为 `~/.claude/skills/`，本项目使用的 Codex 安装器默认为 `~/.codex/skills/`。首次安装后从安装位置执行 `python3 scripts/update_from_gitee.py` 核对版本，之后每次使用都会先检查并原位更新。更新器需要 Git、Python 3，以及支持原子目录交换的 macOS 或 Linux 环境。

可以直接说“用这个技能把下面的剧本写成视频提示词，保留我给的分镜”。在同一对话里也可以接着说“第二镜让她更委屈一点，目光不要移开”。

## 使用反馈

安装、更新、写提示词或看完成片时都可以直接告诉 Agent 遇到了什么。能定位到技能的问题，Agent 会先查已有 Issue，在获得本次或持续授权后，用去除项目素材的最小例子提交。授权必要时自动反馈后，后续同范围的问题可以直接处理。支持已连接的 Gitee 工具、已登录的仓库页面，也支持给内置脚本配置 `GITEE_ACCESS_TOKEN`。[仓库 Issues](https://gitee.com/a1meon_admin/seedance25_prompt/issues)
