# Codex Provider Switcher：切换 provider 也不丢会话历史

[![测试](https://github.com/RomaCredit/codex-provider-switcher/actions/workflows/test.yml/badge.svg)](https://github.com/RomaCredit/codex-provider-switcher/actions/workflows/test.yml)
[![PyPI](https://img.shields.io/pypi/v/codex-provider-switcher)](https://pypi.org/project/codex-provider-switcher/)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/)

[English](https://github.com/RomaCredit/codex-provider-switcher/blob/main/README.md) |
[版本发布](https://github.com/RomaCredit/codex-provider-switcher/releases) |
[更新记录](https://github.com/RomaCredit/codex-provider-switcher/blob/main/CHANGELOG.md)

Codex Desktop 用量达到限制后，切换到第三方 OpenAI 兼容 API，常见结果是项目侧边栏变空，或者原来的对话显示在错误项目下。本工具的核心不是改几行 `config.toml`，而是同步 Codex Desktop 的会话索引和元数据，让切换 provider 后仍能看到原有项目会话。

## 适用范围

适用于本地 provider 配置切换，以及切换后 Codex Desktop 的项目索引与会话元数据
不一致的问题。不能恢复已删除的会话文件，不能迁移 ChatGPT 云端对话，也不会增加
订阅额度或远程修复另一台电脑。第三方 API 单独计费，协议与模型仍须兼容你的
Codex 版本。本项目是社区工具，与 OpenAI 无官方隶属关系。

## 问题根因

Codex Desktop 的会话列表同时依赖 `state_5.sqlite` 和
`sessions/rollout-*.jsonl` 第一行的 `session_meta`。如果配置文件里的
provider 已经切换，但这些文件中的 `model_provider` 没有同步，可能导致
侧边栏空白或会话归属异常。这只是可能的原因之一，并非所有历史问题的统一解释。

## 工具做什么

切换前自动备份 Codex 状态，然后更新 SQLite 线程索引、JSONL 会话元数据和
项目 workspace hints。Windows 下还会去掉 `\\?\` 工作目录前缀。`repair-history`
只修复历史，不切换当前 profile。

## 安装

需要 **Python 3.10 或更高版本**。请使用平时运行 Codex 的系统用户操作，避免
root 和普通用户读到不同的配置及历史目录。

### Linux / macOS：独立安装脚本

Ubuntu 服务器可以直接用下面的命令安装，无须先创建虚拟环境。脚本从 GitHub
下载发布版本的 Python 源文件，不调用 pip，也不修改系统 Python 的包，因此
不会触发 `externally-managed-environment`。机器上仍需已有 Python 3.10+
和 `curl` 或 `wget`；它不是自带 Python 的二进制程序。

```bash
curl -fsSL https://raw.githubusercontent.com/RomaCredit/codex-provider-switcher/v0.3.2/install.sh | sh
cps --version
```

安装后同时提供 `cps` 和 `codex-provider-switcher`，不需要手动创建软链接。
重复运行会重装指定版本；升级时使用新版本的安装脚本地址即可。
安装过程不会切换 provider，也不会修改 Codex 配置或历史。

| 执行用户 | 命令目录 | 程序目录 |
| --- | --- | --- |
| 普通用户 | `~/.local/bin/` | `~/.local/share/codex-provider-switcher/` |
| root | `/usr/local/bin/` | `/usr/local/lib/codex-provider-switcher/` |

普通用户安装后若提示 `cps: command not found`，先执行：

```bash
export PATH="$HOME/.local/bin:$PATH"
cps --version
```

确认能运行后，把 PATH 设置加入对应 shell 的配置文件，以便下次登录生效。
安装器只输出提示，不会擅自修改 `.bashrc` 或 `.zshrc`。

可通过 `CODEX_SWITCHER_BIN_DIR` 和 `CODEX_SWITCHER_DATA_DIR` 自定义目录。
需要安装其他 tag 时，注意版本变量应传给管道右侧的 **`sh`**：

```bash
curl -fsSL https://raw.githubusercontent.com/RomaCredit/codex-provider-switcher/v0.3.2/install.sh | CODEX_SWITCHER_VERSION=v0.3.0 sh
```

### PyPI

在虚拟环境或允许 pip 管理的 Python 环境中，直接安装即可：

```bash
python -m pip install --upgrade codex-provider-switcher
```

如果 Ubuntu/Debian 提示 `externally-managed-environment`，这是系统 Python
的 PEP 668 保护，并非包不支持安装。改用上面的独立安装脚本、pipx 或虚拟环境；
`pip install --user` 同样可能受限，不建议用 `--break-system-packages` 强行绕过。

### Homebrew

```bash
brew tap RomaCredit/codex
brew install codex-provider-switcher
```

### pipx

机器已安装 pipx 时：

```bash
pipx install codex-provider-switcher
```

### 源码安装

```bash
git clone https://github.com/RomaCredit/codex-provider-switcher.git
cd codex-provider-switcher
python3 -m venv .venv
.venv/bin/python -m pip install .
.venv/bin/cps --version
```

### Windows PowerShell

```powershell
irm https://raw.githubusercontent.com/RomaCredit/codex-provider-switcher/v0.3.2/install.ps1 | iex
```

Linux 服务器上的安装只处理该服务器能访问的 Codex 数据，不会远程修复另一台
Windows/macOS 电脑上的 Desktop 侧边栏。

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

## 实现与兼容性边界

| 本地文件 | 关键字段 | 处理范围 |
| --- | --- | --- |
| `config.toml` | `model_provider`、`model`、provider 配置块 | 设置端点、模型和协议 |
| `state_5.sqlite` | `threads.model_provider`、`threads.cwd` | 对齐线程索引 |
| `sessions/**/rollout-*.jsonl` | 首条 `session_meta` 中的 provider 和 cwd | 同步元数据，不改消息正文 |
| `.codex-global-state.json` | `thread-workspace-root-hints` | 重建项目提示信息 |

API profile 使用 profile 名作为 provider ID，订阅模式使用 `openai`。
Windows 的 `\\?\D:\work\app` 会规范化为 `D:\work\app`。这些是本版本处理的
本地存储格式，不是上游承诺稳定的公开接口。

默认 `wire_api` 为 `responses`；客户端支持时也可配置 `wire_api = "chat"`。
“OpenAI 兼容”或 `/models` 探测成功，不等于已验证 Responses、流式输出、
工具调用或任意模型都能使用。

## 故障排查

### 切换后历史消失，但会话文件还在

遇到 “codex desktop sidebar empty”、`codex model_provider mismatch`，或者
切换 provider 后出现 “codex conversations missing after switching provider”，
请完全退出 Codex Desktop 后执行：

```bash
cps repair-history
```

### 修复后侧边栏仍为空

先确认运行用户和 Codex 数据目录与 Desktop 一致，再重启 Desktop。
文件已删除、数据目录不同、客户端格式变化都需单独排查；不要反复修复未知格式，
也不要把真实会话、数据库或凭据上传到公开 issue。

### 额度用完后，切换能增加订阅额度吗？

不能。`codex usage limit reached` 是订阅额度问题，切换只是改用独立计费的 API。
本工具不提供免费密钥、不绕过额度限制，也不保证第三方模型的可用性。

### API 探测失败

检查 `base_url`、凭据，以及网关是否提供 models 列表接口：

```bash
cps profile test openrouter
cps status
```

网络探测只会访问用户明确配置的 provider 的 `/v1/models`，不会上传本地文件。

## 安全

修改前会生成带时间戳的备份；不会删除对话正文，不会输出完整 API key，不会收集
任何遥测数据，也不会向第三方发送请求，唯一例外是用户主动执行的 `/v1/models`
连通性探测。

## 验证范围与相关项目

[CI](https://github.com/RomaCredit/codex-provider-switcher/actions/workflows/test.yml)
覆盖 Windows、macOS、Linux 的 Python 3.10 和 3.13，使用临时测试数据；
POSIX 安装器在 Linux/macOS 验证。CI 通过不代表所有 Desktop 版本和真实网关均兼容。

Claude Code 用户可使用
[Claude Provider Switcher](https://github.com/RomaCredit/claude-provider-switcher)。
两者协议和历史机制不同，不共享密钥，也不相互迁移会话。

[贡献指南](https://github.com/RomaCredit/codex-provider-switcher/blob/main/CONTRIBUTING.md) |
[提交问题](https://github.com/RomaCredit/codex-provider-switcher/issues/new/choose) |
[安全说明](https://github.com/RomaCredit/codex-provider-switcher/blob/main/SECURITY.md)

## 许可证

MIT，见 [LICENSE](https://github.com/RomaCredit/codex-provider-switcher/blob/main/LICENSE)。
