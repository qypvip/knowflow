# KnowFlow 🧠

**Agent Knowledge Pipeline** — 存储无关、知识库无关、即装即用。

让 AI Agent 产出的数据自动走完：**写入 → 版本控制 → 多端同步 → 人类可读** 的全流程。

```bash
pip install knowflow

# 从模板创建新项目
knowflow init football-prediction --dir my-football-bot
cd my-football-bot

# Agent写入数据 → 自动转Obsidian文档
echo '{"match": "巴西vs阿根廷", "prediction": "巴西胜"}' > football/data/prediction.json
knowflow run

# 查看漂亮的Markdown报告
cat output/football/prediction.md
```

## ✨ 特性

| 特性 | 说明 |
|------|------|
| 🔌 **存储无关** | Git / 本地 / S3 / 夸克网盘 / WebDAV — 随意换 |
| 📚 **知识库无关** | Obsidian / Notion / IMA / MkDocs — 多端同步 |
| 📦 **模板系统** | 足球预测、股票分析、日记、Wiki等6+模板 |
| 🗄️ **自动归档** | 热→温→冷三层，数据不会无限膨胀 |
| 🔄 **版本控制** | Git后端自动记录每次变更 |
| 🎯 **零依赖** | 核心纯Python标准库，装完即用 |
| 🔓 **开源** | MIT协议，可商用可二次开发 |

## 🚀 快速开始

```bash
# 安装
pip install knowflow

# 查看可用模板
knowflow list

# 初始化项目
knowflow init daily-journal --dir my-diary
cd my-diary

# 写入一些数据
mkdir -p diary/data/entries
cat > diary/data/entries/2026-05-18.json << 'EOF'
{
  "date": "2026-05-18",
  "title": "今天学习了KnowFlow",
  "mood": "开心",
  "notes": "终于有了一个统一的知识管理工具"
}
EOF

# 运行管道
knowflow run

# 查看输出
cat output/diary/2026-05-18.md
```

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

```bash
# Git（默认）— 推荐，有版本历史
knowflow init football-prediction --storage git

# 本地文件 — 最简单，无版本
knowflow init football-prediction --storage local

# S3/MinIO/R2 — 需安装: pip install knowflow[s3]
knowflow init football-prediction --storage s3
```

## 📚 知识库后端

```bash
# 本地目录（默认）
knowflow init football-prediction --kb local

# Obsidian vault
knowflow init football-prediction --kb obsidian
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
StorageAdapter ← 可插拔（Git/本地/S3/夸克...）
    ↓
Pipeline (Markdown导出→归档→索引)
    ↓
KnowledgeAdapter ← 可插拔（Obsidian/Notion/IMA...）
```

## 📄 协议

MIT
# Gitee Mirror
