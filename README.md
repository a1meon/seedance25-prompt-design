# seedance2.5提示词设计-v1.0

把剧本、分镜设想或已有提示词写成可直接提交的 Seedance 2.5 视频提示词。给出分镜时沿用原有设计；只有剧本时，按人物意图设计机位、切点和走位。每张可辨的脸都有符合前情的视线、情绪和表演。

## 【通过agent使用】

> 请从 https://gitee.com/a1meon_admin/seedance25_prompt.git 的 main 分支下载最新版，将仓库内容（不含 .git）作为 seedance25-prompt-design-v1-0 安装到你当前的个人技能目录，已有同名技能就原位更新（Windows 旧版报缺少 fcntl 时按本 README 的首次升级方法修复），并确认能发现 SKILL.md 并调用。

## 安装与使用

将上面一句话发给 Codex、Claude Code 或其他支持 `SKILL.md` 的 Agent。沿用当前工具已经发现的个人技能目录。Claude Code 默认为 `~/.claude/skills/`，本项目使用的 Codex 安装器默认为 `~/.codex/skills/`。同名文件夹下面应直接是 `SKILL.md`、`references/` 和 `scripts/`。更新器需要 Git 和 Python 3（Windows 使用 Python 3.8 或更高版本），可在安装目录运行以下命令。之后每次使用会自动执行同样的检查。

| 平台 | 命令 |
|---|---|
| Windows 原生 PowerShell 或命令提示符 | `py -3 scripts/update_from_gitee.py`，若已安装的 Python 3.8+ 命令是 `python`，使用 `python scripts/update_from_gitee.py` |
| macOS、支持目录交换的 Linux 或 WSL | `python3 scripts/update_from_gitee.py` |

可以直接说“用这个技能把下面的剧本写成视频提示词，保留我给的分镜”。在同一对话里也可以接着说“第二镜让她更委屈一点，目光不要移开”。

交付前会逐镜核对四件事：摄影机固定或移动的选择是否合乎剧情，每张可辨的脸是否演出了前情，画面句是否只写当时能看见的人物和物件，以及站位与视线是否从观众所在的机位说清。

## 怎样确认已更新

`v1.0` 是技能名称的一部分。常规安装用安装目录的 `.gitee-revision` 与 Gitee `main` 提交号比较，有变化就原位更新。`updated` 表示已更新，`current` 表示已与远端一致。Windows 常规安装会暂存已校验的完整版本，逐文件替换并清除旧文件，最后写入提交号。遇到文件占用或更新中断时，关闭占用文件的程序并重试同一命令，更新器会先补完暂存的版本。

若早期把仓库直接克隆进了个人 `skills/seedance25-prompt-design-v1-0/`，旧更新器会因目录含 `.git` 而提示“请从此技能的安装目录执行更新”。让 Agent 在该目录确认 `origin` 是本仓库、当前分支为 `main`、工作区干净，然后执行一次 `git pull --ff-only origin main`。此后的每次调用自动比较本地 `HEAD` 并快进更新。若有本地改动或分叉，更新器会保留现场，报告具体原因。

## 旧版首次升级

Windows 上运行旧脚本可能报 `No module named 'fcntl'`。让 Agent 从 Gitee 的 main 分支克隆到临时目录，再用临时目录里的**新版脚本**和 `--install-dir` 指向当前安装副本。这个操作只需一次。以下 PowerShell 示例按 Codex 默认路径编写，Claude Code 或自定义安装请将第一行改为 Agent 实际加载的目录。

```powershell
$skillDir = Join-Path $env:USERPROFILE '.codex\skills\seedance25-prompt-design-v1-0'
$sourceDir = Join-Path ([System.IO.Path]::GetTempPath()) ('sd25-' + [guid]::NewGuid())
try {
    git clone --quiet --depth 1 --branch main https://gitee.com/a1meon_admin/seedance25_prompt.git $sourceDir
    if ($LASTEXITCODE -ne 0) { throw '从 Gitee 下载更新器失败' }
    $updater = Join-Path $sourceDir 'scripts\update_from_gitee.py'
    if (Get-Command py -ErrorAction SilentlyContinue) { py -3 $updater --install-dir $skillDir }
    else { python $updater --install-dir $skillDir }
    if ($LASTEXITCODE -ne 0) { throw '更新未完成，请查看上方的具体原因' }
}
finally {
    if (Test-Path -LiteralPath $sourceDir) { Remove-Item -LiteralPath $sourceDir -Recurse -Force }
}
```

## 使用反馈

可以直接告诉 Agent 哪一拍看起来演错了。比如人物本该强忍委屈却一开始就哭，或两人同框时听者一直没有反应。这类演技、情绪问题，以及对白串人、画外人物误入画等提示词问题，都可以用来调优。Agent 会先对照原要求和实际表现，判断这个案例能帮助改进或检验什么，再查重。能说明这种落差的单个案例也值得上报，原因可以待查。日常换演法或缺少具体线索的偶发波动，在对话里处理。

值得上报时，Agent 会准备标题、问题简述、当时的完整提示词、当次输入的完整剧本和全部实际参考素材，保留每项素材的编号和用途，按你对完整材料的授权提交。

**第一次用 Gitee？** Issue 就是发给维护者的问题反馈。你愿意提交时，可以让 Agent 带你完成。先在 Gitee 注册或登录，再到仓库反馈页点“新建 Issue”，选择“提交技能调优案例”。Agent 会备好正文和附件，能使用已登录页面时也可代为提交。密码和验证码由你在 Gitee 页面填写。[注册](https://gitee.com/signup) · [登录](https://gitee.com/login) · [仓库反馈页](https://gitee.com/a1meon_admin/seedance25_prompt/issues)
