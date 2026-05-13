# AltStore Source Generator

这个项目用于从 GitHub Releases 中匹配直接发布的 `.ipa` 资产，读取 IPA 内部 `Info.plist` 元数据，并生成 AltStore 可用的静态 source JSON。

## 配置

编辑 `config.yml`：

- `source`：AltStore source 顶层信息，例如 `name`、`identifier`、`subtitle`、`description`、`iconURL`、`website`。
- `apps`：要生成的 app 列表。
- `repo`：GitHub 仓库，格式为 `owner/name`。
- `assetPattern`：用于匹配 release asset 名称的正则表达式。
- `includePrerelease`：是否包含 prerelease。
- `keepVersions`：最多保留几个历史版本。
- `metadata`：覆盖或补充 app 展示信息，例如 `name`、`developerName`、`localizedDescription`、`category`、`iconURL`、`tintColor`。

仓库内已经提供 PiliPlus 示例：

```yaml
apps:
  - id: piliplus
    repo: bggRGjQaUbCoE/PiliPlus
    assetPattern: 'PiliPlus_ios_.*\.ipa$'
```

## 本地运行

安装依赖并生成：

```bash
uv sync
uv run python scripts/update.py
```

只更新某个 app：

```bash
uv run python scripts/update.py --app piliplus
```

生成结果会写入：

```text
dist/apps.json
```

如果设置了 `GITHUB_TOKEN`，生成器会使用 token 访问 GitHub API；未设置时会匿名请求，但更容易触发 rate limit。

## GitHub Actions

`.github/workflows/update.yml` 支持：

- 手动触发 `workflow_dispatch`。
- 输入 `app`：只更新某个 app，留空则更新全部。
- 输入 `force`：第一版仅预留，不实现复杂缓存。
- 每 6 小时自动运行一次。
- 当配置、脚本或源码变更时自动运行。

生成后如果 `dist/apps.json` 有变化，workflow 会自动提交并推送。

## AltStore Source URL

把这个仓库发布到 GitHub 后，可以使用 raw 文件地址作为 AltStore source URL：

```text
https://raw.githubusercontent.com/<owner>/<repo>/<branch>/dist/apps.json
```

如果启用 GitHub Pages，也可以使用 Pages 上的 `dist/apps.json` 地址。
