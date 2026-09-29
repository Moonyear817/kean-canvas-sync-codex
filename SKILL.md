---
name: canvas-sync
description: |
  把 Kean/WKU Canvas（kean.instructure.com）上还没下载的课件自动下载到本地「学习/<学期>/<课程代码>」文件夹（Codex 版）。Use this skill whenever the user says 同步 Canvas、下载课件、Canvas 有没有新课件、把 Canvas 上的 PPT/PDF 下下来、更新课件, or any request to pull course materials/slides/readings from Canvas to their Mac — even if they don't say "sync". Also used by a scheduled Canvas check automation.
---

# Canvas 课件同步（Codex 版）

把 Canvas 上所有在修课程里（「文件」页 + 「单元/Modules」）本地还没有的课件，下载并归档到：

```
<root>/<学期文件夹>/<课程代码>/
```

设置在本 skill 目录的 `config.json`（没有就用 `config.example.json`）：`root` 课件根目录、`canvas_url`、`entry_year` 入学年份（秋季入学）、`max_mb` 大文件阈值。下文的 `<root>`、`<canvas_url>` 都指这里的值。

- 学期文件夹由课程名前缀推出：`2026FAW*...` → `2026FA` → 若 entry_year=2025 则为 **大二秋季**（秋季 Y 年 = 大(Y-entry_year+1)，春/夏季 Y 年 = 大(Y-entry_year)）。新学期文件夹、新课程文件夹不存在就直接建。
- 课程代码：`ACCT*2200*W05` → `ACCT2200`。

脚本都在本 skill 的 `scripts/` 下（下文写作 `$S`，即 `~/.codex/skills/canvas-sync/scripts`）。

## 规则

- **直接下载，不用先给清单确认。** 下完给报告。
- **大于 max_mb（默认 20 MB）的先问用户**要不要。用户说不要的，把 `学期/课程/文件名` 追加到 `<root>/.canvas_sync_ignore`，以后不再问。自动化（无人值守）运行时不问，只在报告里列出来。
- 同一份课件同时有 pdf 和 pptx 时只要 pptx（例如教材配套的 Pajo_2e_PPT_01.pdf / .pptx）。扫描脚本已处理。
- 课程文件夹里任何子文件夹中已有同名文件/文件夹 = 已下载（用户会把文件挪进 hw/、week 2 data/ 等）。zip 已被解压成同名文件夹也算已下载。
- 老师锁住的文件下不了，报告里提一句即可。
- 不删用户的任何文件；不上传、不提交作业；不替用户输入密码。

## 浏览器：要用「已登录 Canvas 的 Chrome」

学校不给学生开 Canvas API 令牌，所以所有 Canvas 访问都借用浏览器里的登录状态。用 Codex 能控制的 Chrome（Codex 的 Chrome 扩展 / 浏览器工具）来做。需要这个浏览器里已经登录了 Canvas；没登录就请用户自己在那个浏览器里登录（不要替用户输密码）。

在 Claude 版上实测过、走不通的办法，不要浪费时间重试：
- **Canvas API 令牌**：学校不给学生开放。
- **每个下载都要用户点确认的浏览器**（例如 Claude 桌面 app 的内置浏览器）：太烦，用户不接受。
- **在页面里用 fetch 拿 blob 再 `a.click()`、隐藏 iframe 下载**：静默无效，不会落盘。
- **把 Canvas 签名的 CDN 链接拿到 curl 里下**：离开浏览器返回 401。
- **网页往 localhost 发数据**：会被浏览器拦截。

**能用的办法**：把 `<canvas_url>/files/<id>/download?download_frd=1` 当作**页面导航**在标签页里打开（不是 fetch）。Chrome 会直接存进 `~/Downloads`，然后用脚本挪进课程文件夹。

> Codex 版的浏览器步骤是从 Claude 版改写的，还没在 Codex 里完整跑过。第一次用时先只下 1 个文件，确认它真的落到了 `~/Downloads`、且没有逐个弹确认框，再批量下载。如果 Codex 打开的是一个没有用户 Canvas 登录态的独立浏览器，先请用户在那个浏览器里登录一次。

## 流程

### 1. 打开 Canvas 标签页

用 Codex 的浏览器能力在用户的 Chrome 里新开一个标签页，打开 `<canvas_url>`。浏览器连不上时，告诉用户打开 Chrome 并确认 Codex 扩展可用，然后停下。

### 2. 本地索引 + 扫描 Canvas

```bash
python3 $S/local_index.py > /tmp/canvas_local.json
```

读取 `$S/canvas_scan.js`，把 `const DATA = __DATA__;` 里的 `__DATA__` 替换成 `/tmp/canvas_local.json` 的内容，整段放在 Canvas 标签页的页面上下文里执行（它需要同源 fetch，带着登录 cookie）。脚本用到了顶层 `await`，最后一行 `result;` 是返回值；如果你的执行工具不支持顶层 await，就把整段包成 `(async () => { ...; return result; })()` 再执行。

返回：
- `NOT_LOGGED_IN`：请用户在这个浏览器里登录 Canvas，然后停下。自动化运行时就直接结束并报告"未登录"。
- 否则返回 JSON 摘要 `{todo, todoMB, big, skipped, unknownCourses}`。完整列表存在页面的 `window.__todo / __big / __skipped` 里。

`todo` 为 0 且 `big` 为 0 时，直接告诉用户"没有新课件"，关掉标签页，结束。

### 3. 取出待下载列表

在同一个页面里执行下面这段，分段取（返回值可能被截断，每次 12 条），直到取完：

```js
window.__todo.slice(0,12).map(r=>[r.key,r.id,r.size,r.name].join('\t')).join('\n')
```

把所有行写进 `/tmp/canvas_todo.tsv`（每行 `key<TAB>id<TAB>size<TAB>name`）。`window.__big` 用同样的方法取出来，按上面的规则处理：问用户；用户要的就追加进 todo，不要的就写进 ignore 文件。

### 4. 下载

先记下开始时间：`date +%s`。然后在自己的标签页里依次导航到每个 `<canvas_url>/files/<id>/download?download_frd=1`，一个接一个。

### 5. 归档

```bash
python3 $S/file_downloads.py /tmp/canvas_todo.tsv <开始时间>
```

脚本会做这些事：
- 等 Chrome 下完；
- 按「文件名（含 Chrome 的 ` (1)` 重名形式）+ 字节数」匹配，并且只认开始时间之后的新文件，所以用户放在「下载」里的旧版本不会被动；
- 挪进课程文件夹，缺的学期/课程文件夹会自动建；
- zip 解压成同名文件夹。

输出 JSON 报告。如果有 `missing`，就用它们的 id 重新导航一次，再跑一遍脚本。第二次还缺的，写进报告。

### 6. 收尾

关掉自己开的标签页，删掉 `/tmp/canvas_*.json|tsv`，然后给用户报告，格式如下：

```
Canvas 同步完成：新增 N 个文件
- ACCT2200（2）：Topic 4.pdf、Topic 4 Practice Questions.pdf
- MGS2150（1）：26SP2150 L6.pptx
大文件待定：…（仅当有时）
下载不了：ECON1020 Syllabus（老师锁定）
```

没有新文件时就一句话："Canvas 上没有新课件。"

## 自动化（定时运行）

如果是被 Codex 自动化调用的，无人可问，所以：
- 大文件只列出来，不下载；
- Chrome 没开或没登录时，报告一句就结束，不要反复重试。
