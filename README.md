# seedance2.5提示词设计-v1.0

把剧本、分镜设想或已有提示词写成可直接提交的 Seedance 2.5 视频提示词。给出分镜时沿用原有设计；只有剧本时，按人物意图设计机位、切点和走位。每张可辨的脸都有符合前情的视线、情绪和表演。

## 【通过agent使用】

> 请从 [GitHub](https://github.com/a1meon/seedance25-prompt-design.git) 或 [Gitee](https://gitee.com/a1meon_admin/seedance25_prompt.git) 的 main 分支安装 seedance25-prompt-design-v1-0 到当前 Agent 的个人技能目录，已有同名技能就用新版更新器原位更新，并确认能调用 SKILL.md。

## 安装与使用

将上面一句话发给 Codex、Claude Code 或其他支持 `SKILL.md` 的 Agent。沿用当前工具已经发现的个人技能目录。Claude Code 默认为 `~/.claude/skills/`，本项目使用的 Codex 安装器默认为 `~/.codex/skills/`。同名文件夹下面应直接是 `SKILL.md`、`references/` 和 `scripts/`。更新器需要 Git 和 Python 3（Windows 使用 Python 3.8 或更高版本），可在安装目录运行以下命令。之后每次使用会自动执行同样的检查。

| 平台 | 命令 |
|---|---|
| Windows 原生 PowerShell 或命令提示符 | `py -3 scripts/update_from_gitee.py`，若已安装的 Python 3.8+ 命令是 `python`，使用 `python scripts/update_from_gitee.py` |
| macOS、支持目录交换的 Linux 或 WSL | `python3 scripts/update_from_gitee.py` |

可以直接说“用这个技能把下面的剧本写成视频提示词，保留我给的分镜”。在同一对话里也可以接着说“第二镜让她更委屈一点，目光不要移开”。

人物参考按首次出场安排，已有上传编号照用。【参考素材职责】每行只写一句，如「@图片1是林岚的人物参考。」镜头里优先用同一个名字，说清谁看谁、谁把什么交给谁。原台词照录。对白在实际开口处出现。「无bgm，无字幕。」跟在生成目标正文末尾，同一行写一次。只有跨镜、剪辑点或母版编辑确有需要承接的具体内容时，才在末尾写【保持一致】。

升格、移轴、移焦等专业词会写成镜头中的实际变化。抽象的表演要求会结合人物前情、视线和回应时机落实到动作。遇到成片偏差或素材报错，可直接描述现象让 Agent 排查。[术语与镜头写法](references/shot-terms.md) · [官方常见问题的处理办法](references/seedance-faq.md)

交付前会逐镜核对四件事：每镜是否写清摄影机何时动、往哪儿动、在哪里停，采用固定时原构图具体留住了什么，每张可辨的脸是否演出了前情，画面句是否只写当时能看见的人物和物件，以及站位与视线是否从观众所在的机位说清。

## 怎样确认已更新

`v1.0` 是技能名称的一部分。两个官方仓库共享 `main` 的发布历史，普通安装用原目录里的 `.gitee-revision` 记录提交号。早期只认识 Gitee 的安装会从原入口收到双源版本，之后沿用原目录和更新命令。

默认并行查询 GitHub 和 Gitee，查询超时为 6 秒。两端一致且本地已是最新版时立即返回 `current`。只有版本不同时才下载，两个源共用 20 秒网络下载预算。一个源不可达或下载失败时可从另一个源更新；一边落后时，按 Git 历史选已获取的较新快进提交。`updated` 表示原位更新成功。两端均不可达时返回 `offline`。若可达版本比本机旧、无法证明是本机的后续提交或发现分叉，返回 `retained`，继续使用本机版本。并发调用遇锁立即返回；普通 macOS/Linux 安装可在 `busy` 时继续，Windows 或 Git 检出目录会提示另一进程正在更新。

要单独用一个源，在原命令后加 `--source gitee` 或 `--source github`。例如 Windows 用 `py -3 scripts/update_from_gitee.py --source gitee`，macOS/Linux 用 `python3 scripts/update_from_gitee.py --source github`。也可在启动 Agent 的环境中设置 `SEEDANCE25_UPDATE_SOURCE=gitee` 或 `github`；默认是 `auto`。单源不可达时沿用本机版本。

只读沙盒也可以查询版本。只有查到新版才会返回 `needs-write`，表示安装新版本需要写入权限。Windows 常规安装逐文件替换并清除旧文件，最后写入提交号。若上次中断，更新器会先补完本地暂存的版本。此时远端不可用会返回 `updated-offline`，仍可使用刚恢复的版本。

若早期把仓库直接克隆进了个人 `skills/seedance25-prompt-design-v1-0/`，旧更新器会因目录含 `.git` 而提示“请从此技能的安装目录执行更新”。让 Agent 在该目录确认 `origin` 是本仓库、当前分支为 `main`、工作区干净，然后执行一次 `git pull --ff-only origin main`。此后的每次调用自动比较本地 `HEAD` 并快进更新。有未提交的改动时提示处理；有独立提交时保留当前版本。

## 旧版首次升级

能访问 Gitee 的旧安装，只需照常使用一次即可取得双源更新器。如果旧安装所在网络完全无法连接 Gitee，可以从本项目的 GitHub 仓库下载到临时目录，用其中的 `scripts/update_from_gitee.py --install-dir 原安装目录` 引导升级。脚本从临时副本读取发布地址，核对同一项目后在原路径更新；即使旧版从未收到过渡包也适用。

Windows 上运行旧脚本可能报 `No module named 'fcntl'`。让 Agent 从任一官方仓库的 main 分支克隆到临时目录，再用临时目录里的**新版脚本**和 `--install-dir` 指向当前安装副本。这个操作只需一次。以下 PowerShell 示例按 Codex 默认路径编写，Claude Code 或自定义安装请将第一行改为 Agent 实际加载的目录。

```powershell
$skillDir = Join-Path $env:USERPROFILE '.codex\skills\seedance25-prompt-design-v1-0'
$sourceDir = Join-Path ([System.IO.Path]::GetTempPath()) ('sd25-' + [guid]::NewGuid())
try {
    git clone --quiet --depth 1 --branch main https://gitee.com/a1meon_admin/seedance25_prompt.git $sourceDir
    if ($LASTEXITCODE -ne 0) { throw '下载更新器失败；也可以改用上方的 GitHub 仓库再运行' }
    $updater = Join-Path $sourceDir 'scripts\update_from_gitee.py'
    if (Get-Command py -ErrorAction SilentlyContinue) { py -3 $updater --install-dir $skillDir }
    else { python $updater --install-dir $skillDir }
    if ($LASTEXITCODE -ne 0) { throw '更新未完成，请查看上方的具体原因' }
}
finally {
    if (Test-Path -LiteralPath $sourceDir) { Remove-Item -LiteralPath $sourceDir -Recurse -Force }
}
```

## 发布更新

维护者在 `main` 提交改动后运行 `python3 -B scripts/publish.py`（Windows 用 `py -3 -B scripts/publish.py`）。脚本将同一提交快进推送到两个仓库，并逐一读回 `main` 的提交号。若只有一边发布成功，修复后从同一提交重跑即可补齐另一边。两个提交号均核对成功才算发布完成。

## 使用反馈

可以直接告诉 Agent 哪一拍看起来演错了。比如人物本该强忍委屈却一开始就哭，或两人同框时听者一直没有反应。这类演技、情绪问题，以及对白串人、画外人物误入画等提示词问题，都可以用来调优。Agent 会先对照原要求和实际表现，判断这个案例能帮助改进或检验什么，再查重。能说明这种落差的单个案例也值得上报，原因可以待查。日常换演法或缺少具体线索的偶发波动，在对话里处理。

值得上报时，Agent 会准备标题、问题简述、当时的完整提示词、当次输入的完整剧本和全部实际参考素材，保留每项素材的编号和用途，按你对完整材料的授权提交。

**第一次用 Gitee？** Issue 就是发给维护者的问题反馈。你愿意提交时，可以让 Agent 带你完成。先在 Gitee 注册或登录，再到仓库反馈页点“新建 Issue”，选择“提交技能调优案例”。Agent 会备好正文和附件，能使用已登录页面时也可代为提交。密码和验证码由你在 Gitee 页面填写。[注册](https://gitee.com/signup) · [登录](https://gitee.com/login) · [仓库反馈页](https://gitee.com/a1meon_admin/seedance25_prompt/issues)
