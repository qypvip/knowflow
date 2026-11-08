# KnowFlow 🧠

**Agent Knowledge Pipeline** — 存储无关、知识库无关、即装即用。

让 AI Agent 产出的数据自动走完：**写入 → 版本控制 → 多端同步 → 人类可读** 的全流程。

![CI](https://github.com/qypvip/knowflow/actions/workflows/ci.yml/badge.svg)
[![PyPI](https://img.shields.io/pypi/v/knowflow.svg)](https://pypi.org/project/knowflow/)
[![Python](https://img.shields.io/pypi/pyversions/knowflow.svg)](https://pypi.org/project/knowflow/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

```bash
pip install knowflow

# 从模板创建新项目
knowflow init football-prediction --dir my-football-bot
cd my-football-bot

# Agent写入数据 → 自动转 Markdown 文档
echo '{"match": "巴西vs阿根廷", "prediction": "巴西胜"}' > football/data/prediction.json
knowflow run

# 查看报告
cat output/football/prediction.md
```

## 🤔 这解决什么问题

如果你用 AI Agent 干活，大概率遇到过这三件事：

1. **数据散落** —— Agent 每跑一次就吐几个 JSON，几十次之后你根本找不到“上周三那次分析结果在哪”。
2. **机器看得懂，人看不懂** —— JSON 一行行挤在一起，想回顾得自己拼。
3. **越用越乱** —— 数据只增不减，几个月后目录里几千个文件，不敢删也不知道删哪个。

KnowFlow 干的就是这三件：**Agent 只管往固定目录写 JSON，剩下的（转成人类可读的 Markdown、
自动分热/温/冷三层归档、生成索引、Git 记录每次变更）全交给它。**

一句话：**Agent 负责产出，KnowFlow 负责让它留下来还有用。**

## ✨ 特性

| 特性 | 说明 | 状态 |
|------|------|------|
| 🔌 **存储无关** | Git / 本地 / S3 / 夸克网盘 / WebDAV | ✅ 已实现 |
| 📚 **知识库无关** | 本地目录 / Obsidian | ✅ 已实现 |
| 📦 **模板系统** | 足球预测、股票分析、日记、Wiki 等 **7 个** | ✅ 已实现 |
| 🗄️ **自动归档** | 热→温→冷三层，数据不会无限膨胀 | ✅ 已实现 |
| 🔄 **版本控制** | Git 后端自动记录每次变更 | ✅ 已实现 |
| 🧪 **测试** | 68 个单元测试 + GitHub Actions | ✅ 已实现 |
| 🔓 **开源** | MIT 协议，可商用可二次开发 | ✅ |

> 仅依赖 `pyyaml`（非"零依赖"）；Notion / IMA / MkDocs 后端**尚未实现**，欢迎 PR。

## 🚀 安装

```bash
pip install knowflow

# 可选后端
pip install "knowflow[s3]"       # S3 / MinIO / R2
pip install "knowflow[all]"      # 全部后端
```

从源码安装（开发用）：

```bash
git clone https://github.com/qypvip/knowflow.git
cd knowflow
pip install -e .
```

国内网络拉不动 GitHub 时，可用镜像前缀：

```bash
git clone https://ghproxy.net/https://github.com/qypvip/knowflow.git
# 或从 Gitee 克隆
git clone git@gitee.com:qypvip/knowflow.git
```

## ⚡ 快速开始

```bash
# 查看可用模板
knowflow list

# 初始化项目
knowflow init daily-journal --dir my-diary
cd my-diary

# 写入一些数据
mkdir -p diary/data/entries
cat > diary/data/entries/2026-10-02.json << 'EOF'
{
  "date": "2026-10-02",
  "title": "今天学习了 KnowFlow",
  "mood": "开心",
  "notes": "终于有了一个统一的知识管理工具"
}
EOF

# 运行管道（JSON → Markdown → 索引 → 归档）
knowflow run

# 查看输出
cat output/diary/2026-10-02.md
```

## 🧪 开发与测试

```bash
pip install -e . pytest
pytest -q            # 68 passed
python -m knowflow list
```

CI 在 Python 3.9 / 3.11 / 3.12 上跑全量测试，另有一个"零额外依赖"冒烟任务
验证核心模块在只装 `pyyaml` 时可 import、CLI 可用。

## 📦 模板

| 模板 | 命令 | 适用场景 |
|------|------|---------|
| ⚽ football-prediction | `knowflow init football-prediction` | 比赛预测+复盘闭环 |
| 📈 stock-analysis | `knowflow init stock-analysis` | 多策略股票分析 |
| 🏆 worldcup-tracker | `knowflow init worldcup-tracker` | 赛事名单追踪 |
| 📝 daily-journal | `knowflow init daily-journal` | 个人日记+归档 |
| 📚 project-wiki | `knowflow init project-wiki` | 项目文档自动化 |
| 🌐 web-monitor | `knowflow init web-monitor` | 网页内容监控 |
| 🔬 research-notes | `knowflow init research-notes` | 学术笔记管理 |

## 🔌 存储后端

| 后端 | 类 | 额外依赖 | 适用场景 |
|------|----|---------|---------|
| 🔄 `git`（默认） | `GitStorage` | git CLI | 本地 + 版本历史 |
| 📁 `local` | `LocalStorage` | 无 | 最简，无版本 |
| ☁️ `s3` | `S3Storage` | boto3 | AWS / MinIO / R2 |
| 🅰️ `quark` | `QuarkStorage` | kuake_cli | 夸克网盘 |
| 🌐 `webdav` | `WebDAVStorage` | requests | NextCloud / NAS |

```bash
knowflow init football-prediction --storage git
knowflow init football-prediction --storage local
```

## 📚 知识库后端

| 后端 | 类 |
|------|----|
| 📁 `local`（默认） | `LocalKB` |
| 📝 `obsidian` | `ObsidianKB` |

```bash
knowflow init football-prediction --kb obsidian
```

Python 侧用法：

```python
from knowflow.adapters.storage import create_storage
from knowflow.adapters.knowledge import create_knowledge   # create_kb 为别名

store = create_storage("git", path="~/my-data")            # 扁平参数
store = create_storage("git", config={"path": "~/my-data"})  # 或显式 config

kb = create_knowledge("local", path="~/my-output")
```

## 🧪 命令行

```bash
knowflow list          # 列出所有模板
knowflow init <name>   # 从模板创建项目
knowflow run           # 运行数据管道
knowflow status        # 查看仓库状态
knowflow commit "msg"  # 手动提交
knowflow archive       # 手动归档旧数据
knowflow version       # 查看版本
```

## 🏗️ 架构

```
Agent写入数据
    ↓
StorageAdapter ← 可插拔（Git/本地/S3/夸克/WebDAV）
    ↓
Pipeline (Markdown导出→归档→索引)
    ↓
KnowledgeAdapter ← 可插拔（本地/Obsidian）
```

### 加一个存储后端（两步）

```python
from knowflow.core.storage import StorageAdapter

class MyStorage(StorageAdapter):
    def read(self, path): ...
    def read_binary(self, path): ...
    def write(self, path, content): ...
    def write_binary(self, path, content): ...
    def delete(self, path): ...
    def exists(self, path): ...
    def list(self, prefix=""): ...
    def walk(self, prefix=""): ...

from knowflow.adapters.storage import register
register("mystorage", MyStorage)      # 完成
```

## 📄 协议

MIT

## 🔗 镜像

- GitHub: <https://github.com/qypvip/knowflow>
- Gitee: <https://gitee.com/qypvip/knowflow>
