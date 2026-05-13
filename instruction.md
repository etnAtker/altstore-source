# Codex 提示词：实现一个 GitHub Releases 到 AltStore Source 的最小 Python 生成器

请帮我在当前仓库中实现一个干净、最小但相对完整的 Python 项目，用于把指定 GitHub 仓库的 release 资产转换成 AltStore 可用的 source JSON。示例目标仓库使用 `bggRGjQaUbCoE/PiliPlus`，它的 release 中包含 iOS `.ipa` 资产，例如命名形态类似 `PiliPlus_ios_版本号+构建号.ipa`。项目先聚焦个人自用，不需要做成服务端，也不需要实时监听。

## 目标

实现一个静态生成器：读取本地配置，访问 GitHub Releases API，找到匹配的 `.ipa` release asset，提取 IPA 内部元数据，生成 AltStore source JSON，并通过 GitHub Actions 支持手动触发更新。

## 技术路线

- 使用 uv + Python 3.12。
- 不依赖 `altparse`，从头实现核心逻辑。
- 使用标准库优先；必要时可使用小而常见的依赖，例如 HTTP 请求、YAML 解析、数据校验相关库。
- 代码结构清晰，便于以后扩展多个 app、缓存、更多压缩格式和更完整的 AltStore schema。
- 第一版只要求支持 GitHub release asset 中的直接 `.ipa` 文件，不需要支持 zip 内嵌 IPA。

## 输入配置

设计一个简单的 YAML 配置文件，至少包含：

- source 级别信息：名称、identifier、subtitle、description、iconURL、website 等。
- apps 列表。
- 每个 app 至少包含：
  - 内部 id。
  - GitHub repo，例如 `bggRGjQaUbCoE/PiliPlus`。
  - asset 匹配规则，例如只匹配 `PiliPlus_ios_.*\.ipa`。
  - 是否包含 prerelease。
  - 最多保留几个历史版本。
  - 可选 metadata overrides，例如 name、developerName、localizedDescription、category、iconURL、tintColor 等。

请在仓库中提供一个示例配置，示例 app 使用 PiliPlus。

## 生成流程

实现一个命令行入口，例如 `python -m <package>` 或 `python scripts/update.py`。执行后完成以下流程：

1. 读取配置文件。
2. 对每个 app 调用 GitHub Releases API。
3. 过滤 draft release；默认排除 prerelease，除非配置允许。
4. 从 release assets 中按配置的正则选择 `.ipa` 文件。
5. 下载匹配到的 `.ipa` 到临时目录。
6. 打开 IPA，读取 `Payload/*.app/Info.plist`。
7. 提取必要元数据：
   - `CFBundleIdentifier`
   - `CFBundleShortVersionString`
   - `CFBundleVersion`
   - `CFBundleDisplayName` 或 `CFBundleName`
   - `MinimumOSVersion`
   - `UIDeviceFamily`（如果存在）
8. 将提取结果和配置中的 overrides 合并。
9. 为每个匹配 release 生成一个 AltStore version 条目，包含版本号、buildVersion、date、downloadURL、size。
10. 对版本按发布时间倒序排序，只保留配置指定数量。
11. 合并所有 app，输出格式稳定、可读的 `dist/apps.json`。
12. 如有 app 失败，不要让整个任务失败；记录错误摘要。只有配置错误、输出失败等全局错误才应使流程失败。

## 输出要求

生成的 JSON 应该尽量贴近 AltStore source schema，至少包含：

- source 顶层信息。
- apps 数组。
- 每个 app 的基础信息。
- 每个 app 的 versions 数组。

输出应稳定：字段顺序固定、缩进固定、版本排序固定，这样 Git diff 清晰。

## 错误处理和日志

请实现清晰的日志和最终摘要，包括：

- 成功更新了哪些 app。
- 每个 app 找到几个版本。
- 哪些 release 没有匹配到 IPA。
- 哪些 IPA 下载或解析失败。
- 最终输出文件路径。

要求单个 app 或单个 release 失败时继续处理其他项目。

## GitHub API

支持通过环境变量读取 token，例如 `GITHUB_TOKEN`。如果没有 token，也允许匿名请求，但日志中提示可能受到 rate limit 影响。

不要使用网页爬取。只使用 GitHub REST API 的 releases 数据。

## GitHub Actions

添加一个 GitHub Actions workflow，用于手动触发生成。

触发方式至少包括：

- `workflow_dispatch`。
- 可选输入：
  - `app`：只更新某个 app；为空则更新全部。
  - `force`：预留给未来忽略缓存；第一版可以读取但不实现复杂缓存。
- `push` 到配置文件或脚本时自动运行。

workflow 做这些事：

1. checkout 仓库。
2. 设置 Python 3.12。
3. 安装依赖。
4. 执行更新脚本。
5. 如果 `dist/apps.json` 有变化，则自动 commit 并 push。

## 项目结构建议

请设计一个简洁结构，例如：

- `config.yml`
- `dist/apps.json`
- `src/` 或一个清晰的 Python package
- `scripts/update.py` 或模块入口
- `requirements.txt` 或 `pyproject.toml`
- `.github/workflows/update.yml`
- `README.md`

README 需要说明：

- 项目用途。
- 如何配置 PiliPlus 示例。
- 如何本地运行。
- 如何在 GitHub Actions 手动运行。
- 生成的 `dist/apps.json` 如何作为 AltStore source URL 使用。

## 设计边界

第一版不要实现以下内容：

- 不做实时监听。
- 不做 GitHub App。
- 不做服务端 API。
- 不做 RSS 监听。
- 不做 zip 内嵌 IPA 支持。
- 不做网页 UI。
- 不做复杂权限解析。
- 不做完整图标/截图提取。
- 不支持非 GitHub 来源。

但代码结构要为未来扩展留出接口，尤其是 asset resolver、IPA inspector、source builder 三块不要全部写成一个巨大函数。

## 质量要求

- 代码可读、模块边界清楚。
- 配置解析有基础校验。
- 网络请求有超时和明确错误信息。
- 下载文件应有大小限制或至少预留限制配置。
- 处理 IPA/zip 时避免不安全解压；只读取需要的 `Info.plist`。
- 生成文件前先构建完整对象，校验基本字段后再写入。
- 尽量提供类型标注。
- 不要在代码中硬编码 PiliPlus，PiliPlus 只作为配置示例。

请直接在仓库中完成这一版实现，并保持变更尽量小而干净。
