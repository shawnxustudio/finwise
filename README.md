# FinWise · 财务知识库

陈版主（chenyiwei）在中国会计视野论坛多年专业答疑的检索系统，支持全文搜索和弹窗查看完整对话。

---

## 技术架构

```
浏览器
    ↓ http://localhost:8801
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
│   ├── source/             原始源数据（备份，不直接导入）
│   └── import/             整理后的数据（JSON/MD，import_data.py 读取此目录）
├── meilisearch_data/       MeiliSearch 数据持久化（自动生成）
├── app.py                  Flask 后端
├── index.html              前端
├── import_data.py          数据导入脚本
├── docker-compose.yml      MeiliSearch 容器配置
├── .env                    环境变量（不提交 git）
├── .env.example            环境变量模板
└── requirements.txt        Python 依赖
```

---

## 快速开始

**1. 配置环境变量**

```bash
cp .env.example .env
# 编辑 .env，设置 MEILI_MASTER_KEY
```

**2. 启动 MeiliSearch**

```bash
docker compose up -d
```

**3. 安装依赖 & 启动后端**

```bash
pip install -r requirements.txt
python app.py
```

**4. 导入数据**

把整理好的 JSON 文件放入 `data/import/`，然后：

```bash
python import_data.py
```

浏览器打开 `http://localhost:8801`。

---

## 数据格式

`data/import/` 下支持两种格式，**文件名即来源标签**（如 `chenyiwei.json` 显示为 `chenyiwei`）。

### JSON 格式（推荐）

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
        "author": "周庆123",
        "role": "questioner",
        "type": "post",
        "time": "2025-3-18 13:00:46",
        "content": "背景：..."
      },
      {
        "pid": "9371174",
        "floor": 2,
        "author": "chenyiwei",
        "role": "expert",
        "type": "post",
        "time": "2025-3-20 06:42:10",
        "content": "该交易的两个..."
      }
    ]
  }
]
```

**字段说明：**

| 字段 | 说明 |
|------|------|
| `tid` | 帖子 ID |
| `thread_title` | 帖子标题 |
| `thread_url` | 原帖链接 |
| `conversation[].role` | `expert` / `questioner` / `other` |
| `conversation[].type` | `post`（独立楼层）/ `comment`（点评） |
| `conversation[].time` | 发帖时间，格式 `2025-3-18 13:00:46` |

### MD 格式（实务案例）

按 `## 问题N 标题` 分隔，用 `**问题：**`、`**背景：**`、`**解答：**` 标记各部分。

---

## 索引说明

`import_data.py` 对 `expert_qa` 索引的配置：

- **排序**：始终按专家最后回复时间倒序
- **搜索字段**：`title`、`question`、`answer`、`full_text`（前 3000 字）
- **搜索策略**：多词 AND，每个词加引号精准匹配
- **分页上限**：`maxTotalHits = 100000`

---

## 常用操作

```bash
# 启动 MeiliSearch
docker compose up -d

# 停止 MeiliSearch
docker compose down

# 重新导入数据
python import_data.py

# 查看 MeiliSearch 日志
docker logs finwise-meilisearch

# 访问 MeiliSearch 管理后台
# 浏览器打开 http://localhost:8800，输入 MEILI_MASTER_KEY 登录
```

---

## 新增数据

1. 把 JSON 文件放入 `data/import/`，文件名即来源标签
2. 重新运行 `python import_data.py`
3. 前端自动显示新来源，无需改代码
