import os
import json
import hashlib
import re
from pathlib import Path
import meilisearch
from dotenv import load_dotenv

load_dotenv()

meili = meilisearch.Client(
    os.getenv("MEILI_HOST", "http://localhost:8800"),
    os.getenv("MEILI_MASTER_KEY")
)

IMPORT_DIR = Path("./data/import")

def make_id(text):
    return hashlib.md5(text.encode()).hexdigest()[:12]

def parse_date_to_sortable(time_str):
    if not time_str:
        return 0
    try:
        time_str = time_str.strip().replace("/", "-")
        date_part = time_str.split(" ")[0]
        time_part = time_str.split(" ")[1] if " " in time_str else "00:00:00"
        y, m, d = date_part.split("-")
        h, mi, s = (time_part + ":0:0").split(":")[:3]
        return int(f"{int(y):04d}{int(m):02d}{int(d):02d}{int(h):02d}{int(mi):02d}{int(s):02d}")
    except:
        return 0

def format_date_ymd(time_str):
    if not time_str:
        return ""
    try:
        time_str = time_str.strip().replace("/", "-")
        date_part = time_str.split(" ")[0]
        y, m, d = date_part.split("-")
        return f"{int(y):04d}-{int(m):02d}-{int(d):02d}"
    except:
        return time_str

# ========== 专家问答 JSON 解析 ==========
def parse_expert_qa_json(filepath):
    records = []
    try:
        with open(filepath, encoding="utf-8") as f:
            threads = json.load(f)
    except Exception as e:
        print(f"  JSON 解析失败 {filepath.name}: {e}")
        return []

    if not isinstance(threads, list):
        threads = [threads]

    source = filepath.stem

    for thread in threads:
        tid = str(thread.get("tid", ""))
        title = thread.get("thread_title", "").strip()
        url = thread.get("thread_url", "")
        conversation = thread.get("conversation", [])

        if not title or not conversation:
            continue

        expert_times = [
            item.get("time", "")
            for item in conversation
            if item.get("role") == "expert" and item.get("time", "")
        ]
        expert_last_time = expert_times[-1] if expert_times else ""
        expert_last_date = format_date_ymd(expert_last_time)
        expert_last_sort = parse_date_to_sortable(expert_last_time)

        question_text = ""
        expert_text = ""
        for item in conversation:
            if item.get("role") == "questioner" and item.get("floor") == 1 and not question_text:
                question_text = item.get("content", "")[:200]
            if item.get("role") == "expert" and item.get("type") == "post" and not expert_text:
                expert_text = item.get("content", "")[:200]

        all_content = " ".join(item.get("content", "") for item in conversation)

        records.append({
            "id": make_id(tid or title),
            "tid": tid,
            "module": "expert_qa",
            "title": title,
            "url": url,
            "source": source,
            "source_type": "expert",
            "question": question_text,
            "answer": expert_text,
            "expert_last_date": expert_last_date,
            "expert_last_sort": expert_last_sort,
            "full_text": all_content[:3000],
            "conversation": conversation,
            "file": filepath.stem,
        })

    return records

# ========== 实务案例 Markdown 解析（用于 .md 文件） ==========
def parse_case_study_md(filepath):
    records = []
    text = filepath.read_text(encoding="utf-8")
    source_name = filepath.stem

    blocks = re.split(r'\n## 问题', text)
    for block in blocks[1:]:
        full_block = "## 问题" + block
        title_match = re.match(r'## 问题[\d\-]+ (.+?)(?:\n|$)', full_block)
        if not title_match:
            continue
        title = title_match.group(1).strip()
        if not title:
            title = "实务案例"

        def extract_section(pattern, content):
            match = re.search(pattern, content, re.DOTALL | re.IGNORECASE)
            if match:
                return match.group(1).strip()
            return ""

        question_section = extract_section(r'\*\*问题：?\*\*\s*(.*?)(?=\n\*\*背景：|\n\*\*解答：|\Z)', full_block)
        background_section = extract_section(r'\*\*背景：?\*\*\s*(.*?)(?=\n\*\*解答：|\Z)', full_block)
        answer_section = extract_section(r'\*\*解答：?\*\*\s*(.*?)(?=\n---|\n##|\Z)', full_block)

        full_question = f"【问题】{question_section}\n\n【背景】{background_section}" if background_section else question_section
        full_answer = answer_section

        conversation = []
        if full_question:
            conversation.append({
                "pid": make_id(title + "_q"),
                "floor": 1,
                "author": "实务案例",
                "role": "questioner",
                "type": "post",
                "time": "",
                "content": full_question
            })
        if full_answer:
            conversation.append({
                "pid": make_id(title + "_a"),
                "floor": 2,
                "author": source_name,
                "role": "expert",
                "type": "post",
                "time": "",
                "content": full_answer
            })

        full_text = f"{title} {full_question} {full_answer}"[:3000]

        records.append({
            "id": make_id(source_name + title),
            "tid": "",
            "module": "expert_qa",
            "title": title,
            "url": "",
            "source": source_name,
            "source_type": "case",
            "question": full_question[:200],
            "answer": full_answer[:200],
            "expert_last_date": "",
            "expert_last_sort": 0,
            "full_text": full_text,
            "conversation": conversation,
            "file": source_name,
        })

    return records

# ========== 旧版专家问答 Markdown 解析（如果需要的话） ==========
def parse_expert_qa_md(filepath):
    # 如果你的 expert_qa 目录下还有旧的 .md 格式问答，可以在这里实现
    # 这里留空，因为目前没有这种文件
    return []

# ========== 主导入函数 ==========
def init_index():
    """全量模式：删除并重建索引及全部设置"""
    try:
        meili.delete_index("expert_qa")
    except:
        pass

    meili.create_index("expert_qa", {"primaryKey": "id"})

    meili.index("expert_qa").update_searchable_attributes([
        "title", "question", "answer", "full_text"
    ])
    meili.index("expert_qa").update_filterable_attributes([
        "expert_last_date", "expert_last_sort", "file", "tid", "source", "source_type"
    ])
    meili.index("expert_qa").update_sortable_attributes([
        "expert_last_sort"
    ])
    meili.index("expert_qa").update_displayed_attributes([
        "id", "tid", "title", "url", "source", "source_type", "question", "answer",
        "expert_last_date", "expert_last_sort", "conversation", "file"
    ])
    meili.index("expert_qa").update_ranking_rules([
        "sort", "words", "typo", "proximity", "attribute", "exactness",
    ])

    import requests
    meili_host = os.getenv("MEILI_HOST", "http://localhost:8800")
    meili_key = os.getenv("MEILI_MASTER_KEY")
    requests.patch(
        f"{meili_host}/indexes/expert_qa/settings/pagination",
        json={"maxTotalHits": 100000},
        headers={"Authorization": f"Bearer {meili_key}"}
    )
    print("索引初始化完成")


def load_records():
    all_records = []
    if IMPORT_DIR.exists():
        for f in sorted(IMPORT_DIR.glob("*")):
            if f.suffix == ".json":
                records = parse_expert_qa_json(f)
                print(f"  [专家] {f.name}: {len(records)} 条")
                all_records.extend(records)
            elif f.suffix == ".md":
                records = parse_case_study_md(f)
                if records:
                    print(f"  [案例] {f.name}: {len(records)} 条")
                    all_records.extend(records)
                else:
                    print(f"  [跳过] {f.name}: 未识别为实务案例格式")
    return all_records


def upsert_records(all_records):
    batch_size = 200
    for i in range(0, len(all_records), batch_size):
        meili.index("expert_qa").add_documents(all_records[i:i + batch_size])
    print(f"\n总计导入 {len(all_records)} 条记录")


def import_all(incremental=False):
    if incremental:
        print("【增量模式】直接 upsert，索引全程可用")
    else:
        init_index()

    all_records = load_records()
    upsert_records(all_records)


if __name__ == "__main__":
    import sys
    import_all(incremental="--incremental" in sys.argv)