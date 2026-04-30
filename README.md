# FinWise · 财务知识库

陈版主（chenyiwei）在中国会计视野论坛多年专业答疑的检索系统，支持全文搜索和弹窗查看完整对话。

---

## 技术架构

```
浏览器
    ↓ http://<host>:8801
Flask 后端（Python，直接运行）
    └── /api/expert_qa/search   → MeiliSearch

MeiliSearch（Docker，端口 8800）
    └── expert_qa 索引
```

---

## 目录结构

```
finwise/
├── data/
│   └── import/             导入数据目录（JSON/MD，内容不提交 git）
├── meilisearch_data/       MeiliSearch 数据持久化（自动生成，不提交 git）
├── logs/                   运行日志（自动生成）
├── app.py                  Flask 后端
├── index.html              前端页面
├── import_data.py          数据导入脚本
├── scrape_full.py          论坛爬虫脚本
├── sync.sh                 每日自动同步脚本（爬取 + 导入）
├── docker-compose.yml      MeiliSearch 容器配置
├── .env                    环境变量（不提交 git）
└── .env.example            环境变量模板
```

---

## 快速开始

**1. 配置环境变量**

```bash
cp .env.example .env
# 编辑 .env，填入三个变量
```

`.env` 内容：

```
MEILI_MASTER_KEY=你的密钥（至少16位）
FORUM_USERNAME=会计视野论坛账号
FORUM_PASSWORD=会计视野论坛密码
```

**2. 创建数据目录并启动 MeiliSearch**

```bash
mkdir -p meilisearch_data data/import
docker compose up -d
```

**3. 安装 Python 依赖**

```bash
pip install -r requirements.txt
```

**4. 爬取数据**

首次运行全量爬取（时间较长）：

```bash
python scrape_full.py
```

后续只需增量爬取：

```bash
python scrape_full.py --incremental
```

增量模式分两阶段：先扫描所有列表页统计待更新帖子数，再逐帖抓取，连续 3 页全为旧帖时自动停止。

**5. 导入数据到搜索索引**

```bash
# 全量导入（首次或修复时使用，会清空重建索引）
python import_data.py

# 增量导入（日常使用，直接 upsert，搜索不中断）
python import_data.py --incremental
```

**6. 启动后端**

```bash
python app.py
```

浏览器打开 `http://localhost:8801`。

---

## 每日自动同步

`sync.sh` 封装了"增量爬取 + 增量导入"两步，日志保存至 `logs/sync_YYYYMMDD.log`，自动清理 30 天前旧日志。

```bash
bash sync.sh
```

**Synology NAS 定时任务设置：**

控制面板 → 任务计划 → 新增 → 计划的任务 → 用户定义的脚本

- 用户：`root`，时间：每天 `01:00`
- 脚本：`/bin/bash /volume1/script/finwise/sync.sh`

---

## 部署为系统服务（Synology NAS）

**创建 systemd 服务文件：**

```bash
cat > /etc/systemd/system/finwise-app.service << 'EOF'
[Unit]
Description=FinWise Flask Backend
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/volume1/script/finwise
ExecStart=/volume1/@appstore/python313/bin/python3 app.py
Restart=on-failure
RestartSec=10
StandardOutput=append:/volume1/script/finwise/logs/app.log
StandardError=append:/volume1/script/finwise/logs/app.log

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
```

**设置开机自启（任务计划 → 触发的任务 → 开机）：**

```bash
/bin/systemctl restart finwise-app.service > /volume1/script/finwise/logs/app.log 2>&1
```

**日常管理：**

```bash
systemctl start finwise-app
systemctl stop finwise-app
systemctl restart finwise-app
journalctl -u finwise-app -f     # 实时日志
```

---

## 数据格式

`data/import/` 下支持两种格式，**文件名即来源标签**（如 `chenyiwei.json` 显示为 `chenyiwei`）。

### JSON 格式（专家问答）

```json
[
  {
    "tid": "5491716",
    "thread_title": "集团内股权交易的处理",
    "thread_url": "https://bbs.esnai.com/thread-5491716-1-1.html",
    "conversation": [
      {
        "pid": "9371068",
        "floor": 1,
        "author": "questioner_name",
        "role": "questioner",
        "type": "post",
        "time": "2025-03-18 13:00",
        "content": "问题内容..."
      },
      {
        "pid": "9371174",
        "floor": 2,
        "author": "chenyiwei",
        "role": "expert",
        "type": "post",
        "time": "2025-03-20 06:42",
        "content": "解答内容..."
      }
    ]
  }
]
```

| 字段 | 说明 |
|------|------|
| `tid` | 帖子 ID |
| `thread_title` | 帖子标题 |
| `thread_url` | 原帖链接 |
| `conversation[].role` | `expert` / `questioner` / `other` |
| `conversation[].type` | `post`（独立楼层）/ `comment`（点评） |

### MD 格式（实务案例）

按 `## 问题N 标题` 分隔，用 `**问题：**`、`**背景：**`、`**解答：**` 标记各部分。

---

## 搜索说明

- **排序**：始终按专家最后回复时间倒序
- **搜索字段**：标题、问题摘要、回答摘要、全文（前 3000 字）
- **搜索策略**：多词 AND，精准匹配
- **分页上限**：100000 条

---

## 常用命令

```bash
# MeiliSearch
docker compose up -d
docker compose down
docker logs finwise-meilisearch

# 访问 MeiliSearch 管理后台
# 浏览器打开 http://localhost:8800，输入 MEILI_MASTER_KEY 登录
```
