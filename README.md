# Qingci-Bot 插件市场

> **代码托管**：本仓库以 [GitHub](https://github.com/Qingci-Bot/Plugin-Market) 为权威主仓库，[AtomGit](https://atomgit.com/Qingci-Bot/Plugin-Market) 为自动同步的只读镜像；贡献与提 PR 一律以 GitHub 为准。

Qingci-Bot 官方插件市场索引仓库。

## 结构

```
├── index.json              # 市场索引（清单）
└── plugins/                # 官方维护的插件源码
    └── hello/              # Hello 示例插件（SDK 式）
```

## 索引格式

`index.json` 描述市场中的全部插件：

```json
{
  "name": "Qingci-Bot 插件市场",
  "version": 1,
  "plugins": [
    {
      "name": "hello",            // 插件名（与插件内 name 一致，唯一）
      "title": "Hello 示例插件",    // 展示名
      "description": "简介",
      "version": "1.4.0",         // 版本（对比已安装版本判断可更新）
      "author": "Qingci-Bot",
      "type": "sdk",              // sdk / builtin
      "icon": "👋",               // 卡片图标（emoji，可选）
      "homepage": "https://...",  // 插件主页链接（可选）
      "source": "https://github.com/Qingci-Bot/Plugin-Market.git",  // 安装来源
      "tags": ["demo"],           // 标签（WebUI 可按标签筛选）
      "requirements": ["qingci-plugin-sdk>=1.0"],  // 依赖展示（可选；安装时以插件内 requirements.txt 为准）
      "updated_at": "2026-08-16"
    }
  ]
}
```

## 添加插件（PR 流程）

1. 插件源码放入 `plugins/<name>/`（含 `__init__.py`，推荐同时含 `plugin.json`）
2. 在 `index.json` 的 `plugins` 数组追加条目，`source` 指向插件源码所在 git 仓库
3. 提交 PR 到本仓库

> `source` 支持 git 仓库、HTTP 归档（zip/tar）、本地路径；
> 安装时 Qingci-Bot 会克隆/下载 → 定位插件目录 → 隔离安装依赖 → 加载。

## 客户端

- 默认索引地址（raw）：`https://github.com/Qingci-Bot/Plugin-Market/raw/main/index.json`
- 缓存 TTL：默认 3600 秒，WebUI「刷新市场」可强制刷新
