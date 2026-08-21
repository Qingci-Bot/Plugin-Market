# Qingci-Bot 插件市场（索引仓库）

> **代码托管**：本仓库以 [GitHub](https://github.com/Qingci-Bot/Plugin-Market) 为权威主仓库，[Gitee](https://gitee.com/qingci-bot/Plugin-Market) 为自动同步的只读镜像（国内拉取更快，默认市场源）；贡献与提 PR 一律以 GitHub 为准。

Qingci-Bot 官方插件市场**索引仓库**。

本仓库**只维护插件索引**（元数据 + 插件仓库地址），**不托管插件源码**——插件代码留在作者自己的 git 仓库，作者只需在索引中登记地址。

## 结构

```
├── index.json              # 市场索引（清单）
├── scripts/
│   ├── validate_index.py   # 索引校验脚本（CI 使用，零第三方依赖）
│   └── bump_index.py       # 收录条目维护脚本（按插件名更新版本/日期/字段）
├── .github/workflows/ci.yml # 索引校验 CI
├── LICENSE                 # GPL-3.0
└── .gitignore
```

> 本仓库不含插件源码。插件模板见 [Plugins-SDK](https://github.com/Qingci-Bot/Plugins-SDK) 仓库 `plugins/_template/`，示例见独立仓库 [Qingci-Bot/hello](https://github.com/Qingci-Bot/hello)。

## 索引格式

`index.json` 描述市场中的全部插件：

```json
{
  "name": "Qingci-Bot 插件市场",
  "version": 1,
  "plugins": [
    {
      "name": "hello",            // 插件名（唯一，小写 slug）
      "title": "Hello 示例插件",    // 展示名
      "description": "简介",
      "version": "1.4.0",         // 版本（对比已安装版本判断可更新）
      "author": "Qingci-Bot",
      "type": "sdk",              // sdk / builtin
      "icon": "👋",               // 卡片图标（emoji，可选）
      "homepage": "https://...",  // 插件主页（可选）
      "source": "https://github.com/author/plugin.git",  // 插件仓库地址（必填，git 或归档 URL）
      "mirror": "https://gitee.com/author/plugin.git",   // 备用地址（可选，主地址拉取失败时回退）
      "tags": ["demo"],           // 标签（WebUI 可按标签筛选）
      "requirements": ["qingci-plugin-sdk>=1.0"],  // 依赖展示（可选；安装时以插件内 requirements.txt 为准）
      "python_requires": ">=3.10", // Python 版本约束（可选；缺省视为兼容任意版本）
      "updated_at": "2026-08-19"
    }
  ]
}
```

### 地址字段约定

- `source`（必填）：插件源码的 git 仓库地址（`https://...git` / `git@...` / `git+https://...`）或 HTTP 归档 URL（zip/tar）。安装时 Qingci-Bot 克隆/下载该仓库并自动定位插件目录（支持仓库根或 `plugins/<name>/` 嵌套布局）。
- `mirror`（可选）：备用地址。主地址拉取失败时 Qingci-Bot 自动回退到该地址（如国内 Gitee 镜像、反向代理等）。
- `python_requires`（可选）：PEP 440 版本约束字符串（如 `>=3.10`），声明插件要求的 Python 版本。缺省视为兼容任意版本；WebUI 市场页会据此标记「当前环境不兼容」的插件并禁用安装。
- `plugins` 数组按 `name` 升序排列，且 `updated_at` 不得晚于当前日期（CI 强制）。

## 添加插件（PR 流程）

插件作者**无需向本仓库提交源码**，只需登记索引条目：

1. 插件代码托管在自己的 git 仓库（确保仓库可被匿名克隆；插件目录含 `__init__.py`，推荐同时含 `plugin.json`）
2. 在 `index.json` 的 `plugins` 数组按 name 排序插入条目：`source` 填你的仓库地址，可选 `mirror` 填备用地址，`updated_at` 填当天日期
3. 提交 PR 到本仓库；CI 校验通过后合并

> 本地自检：`python scripts/validate_index.py`（零依赖，改完 index.json 先跑一遍再提 PR）。
> 发布新版本：`python scripts/bump_index.py <name> --version x.y.z`（自动更新版本号与更新日期并复跑校验；可用 `--title/--description/--tag` 等同步改字段）。
> 索引版本自动校准：`python scripts/sync_versions.py` 从各插件 `source` 仓库读取 `plugin.json` 的 `version` 并自动同步到 index.json（GitHub Actions 每日定时运行 `.github/workflows/sync-index.yml`，发版后无需手动改索引）。

> 没有独立仓库？可直接引用包含插件的既有仓库；官方示例 hello 即为独立插件仓库：[Qingci-Bot/hello](https://github.com/Qingci-Bot/hello)（仓库根即插件源码，可作新仓库模板）。

### 收录标准（建议）

- 仓库可匿名克隆；插件目录可被 Qingci-Bot 正常定位加载
- 依赖声明在插件目录的 `requirements.txt`（或 plugin.json 的 `requirements`）
- 声明与 Qingci-Bot 兼容的 SDK 版本约束（`qingci-plugin-sdk>=x.y`）
- 提供简介、版本号、更新日期；有截图/文档更佳

## 客户端

- 默认市场源（Qingci-Bot 运行时克隆，Gitee 镜像国内更快）：`https://gitee.com/qingci-bot/Plugin-Market.git`（`market.url` 可切回 GitHub 主仓库）
- 权威索引 raw 地址：`https://github.com/Qingci-Bot/Plugin-Market/raw/main/index.json`
- 缓存 TTL：默认 3600 秒，WebUI「刷新市场」可强制刷新
- 插件安装顺序：`source` → 失败回退 `mirror` → 均失败报错

## 许可

本仓库（索引与校验脚本）以 GPL-3.0 发布；各插件版权与许可归插件作者/各自仓库声明。
