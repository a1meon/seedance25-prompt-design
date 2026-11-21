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

可以直接告诉 Agent 哪一拍看起来演错了。比如人物本该强忍委屈却一开始就哭，或两人同框时听者一直没有反应。这类演技、情绪问题，以及对白串人、画外人物误入画等提示词问题，都可以用来调优。Agent 会先对照原要求和实际表现，判断这个案例能帮助改进或检验什么，再查重。能说明这种落差的单个案例也值得上报，原因可以待查。日常换演法或缺少具体线索的偶发波动，在对话里处理。

值得上报时，Agent 会准备标题、问题简述、当时的完整提示词、当次输入的完整剧本和全部实际参考素材，保留每项素材的编号和用途，按你对完整材料的授权提交。

**第一次用 Gitee？** Issue 就是发给维护者的问题反馈。你愿意提交时，可以让 Agent 带你完成。先在 Gitee 注册或登录，再到仓库反馈页点“新建 Issue”，选择“提交技能调优案例”。Agent 会备好正文和附件，能使用已登录页面时也可代为提交。密码和验证码由你在 Gitee 页面填写。[注册](https://gitee.com/signup) · [登录](https://gitee.com/login) · [仓库反馈页](https://gitee.com/a1meon_admin/seedance25_prompt/issues)
