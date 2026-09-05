# Codex Provider Switcher：切换 provider 也不丢会话历史

[English](README.md)

Codex Desktop 用量达到限制后，切换到第三方 OpenAI 兼容 API，常见结果是项目侧边栏变空，或者原来的对话显示在错误项目下。本工具的核心不是改几行 `config.toml`，而是同步 Codex Desktop 的会话索引和元数据，让切换 provider 后仍能看到原有项目会话。

## 问题根因

Codex Desktop 的会话列表同时依赖 `state_5.sqlite` 和
`sessions/rollout-*.jsonl` 第一行的 `session_meta`。如果配置文件里的
provider 已经切换，但这些文件中的 `model_provider` 没有同步，就会出现
“codex desktop history disappeared”“codex conversations missing after
switching provider”“codex usage limit reached”之后侧边栏空白等现象。

## 工具做什么

切换前自动备份 Codex 状态，然后更新 SQLite 线程索引、JSONL 会话元数据和
项目 workspace hints。Windows 下还会去掉 `\\?\` 工作目录前缀。`repair-history`
只修复历史，不切换当前 profile。

## 安装

PyPI：

```bash
python -m pip install codex-provider-switcher
```

pipx：

```bash
pipx install codex-provider-switcher
```

Homebrew（tap 发布后）：

```bash
brew tap RomaCredit/codex
brew install codex-provider-switcher
```

源码安装：

```bash
git clone https://github.com/RomaCredit/codex-provider-switcher.git
cd codex-provider-switcher
python3 -m pip install .
```

Windows PowerShell：

```powershell
irm https://raw.githubusercontent.com/RomaCredit/codex-provider-switcher/main/install.ps1 | iex
```

## 快速开始

操作前请完全退出 Codex Desktop：

```bash
cps profile list
cps status
cps use openrouter
cps use official
cps repair-history
```

`codex-provider-switcher` 仍然是等价的命令名。

## Profiles 配置

首次运行会创建：

```text
macOS/Linux: ~/.codex-provider-switcher/profiles.toml
Windows:     %USERPROFILE%\.codex-provider-switcher\profiles.toml
```

默认包含三个普通 profile：

```toml
[profiles.official]
type = "subscription"

[profiles.apimaster]
type = "api"
base_url = "https://apimaster.ai/v1"
default_model = "gpt-5.6-sol"

[profiles.openrouter]
type = "api"
base_url = "https://openrouter.ai/api/v1"
default_model = "anthropic/claude-sonnet-4.6"
```

它们和用户自己添加的 profile 使用同一套逻辑，都可以修改或删除：

```bash
cps profile add local
cps profile remove local
cps profile test openrouter
```

API key 不写入 `profiles.toml`。macOS 优先使用 Keychain，Windows 优先使用
Credential Manager；系统密钥库不可用时回退到 `credentials.toml`，POSIX 下权限
为 `0600`。
任意 OpenAI 兼容端点都可以写成 API profile；OpenRouter 和 APIMaster 只是随包
提供的两个普通预设，没有额外的代码分支。

## 命令

```text
cps use <profile>              切换 profile 并修复历史
cps status                     显示当前 profile、模型和凭据状态
cps profile list               列出 profile
cps profile add <name>         交互式添加
cps profile remove <name>      删除 profile
cps profile test <name>        请求该 API 的 /v1/models
cps repair-history             只修复历史
```

旧命令仍可用，但会提示迁移：

```bash
cps apimaster   # 等价于 cps use apimaster
cps official    # 等价于 cps use official
```

## 故障排查

遇到 “codex desktop sidebar empty”、`codex model_provider mismatch`，或者
切换 provider 后出现 “codex conversations missing after switching provider”，
请完全退出 Codex Desktop 后执行：

```bash
cps repair-history
```

API 探测失败时检查 `base_url` 和凭据：

```bash
cps profile test openrouter
cps status
```

网络探测只会访问用户明确配置的 provider 的 `/v1/models`，不会上传本地文件。

## 安全

修改前会生成带时间戳的备份；不会删除对话正文，不会输出完整 API key，不会收集
任何遥测数据，也不会向第三方发送请求，唯一例外是用户主动执行的 `/v1/models`
连通性探测。

## 许可证

MIT，见 [LICENSE](LICENSE)。
