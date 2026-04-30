#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
爬取 forum-7 版块中陈版主(chenyiwei)的所有回复
- 自动登录，Cookie 过期后自动重新登录
- 两遍扫描，完整保留对话链（回复/点评/评分/引用）
- 断点续爬（全量模式）
- 增量模式：--incremental，按最后回复时间过滤
- 输出 JSON 到 data/import/chenyiwei.json，可直接用 import_data.py 导入
"""

import requests
import json
import time
import re
import os
import sys
import random
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
from bs4 import BeautifulSoup

load_dotenv()

# ============================================================
# 配置区
# ============================================================
USERNAME        = os.getenv("FORUM_USERNAME")
PASSWORD        = os.getenv("FORUM_PASSWORD")
BASE_URL        = "https://bbs.esnai.com"
FORUM_ID        = 7
TARGET_USERNAME = "chenyiwei"
TARGET_UID      = 102042
DELAY           = 3
RANDOM_EXTRA    = 1.5
MAX_PAGE        = 1000
INC_STOP_PAGES  = 3

OUTPUT_JSON     = Path("./data/import/chenyiwei.json")
CHECKPOINT_FILE = Path("./data/import/checkpoint.json")
# ============================================================

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36 Edg/146.0.0.0",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9",
}

session = requests.Session()
session.headers.update(HEADERS)


def sleep():
    time.sleep(DELAY + random.uniform(0, RANDOM_EXTRA))


def login():
    print("  [登录] 正在登录...")
    if not USERNAME or not PASSWORD:
        print("  [登录] 未设置 FORUM_USERNAME / FORUM_PASSWORD，请检查 .env")
        return False
    try:
        r = session.get(f"{BASE_URL}/member.php?mod=logging&action=login", timeout=15)
        r.encoding = "gbk"
        fh = re.search(r'name="formhash" value="([^"]+)"', r.text)
        if not fh:
            print("  [登录] 获取 formhash 失败")
            return False
        login_data = {
            "formhash": fh.group(1),
            "referer": f"{BASE_URL}/",
            "loginfield": "username",
            "username": USERNAME,
            "password": PASSWORD,
            "questionid": "0",
            "answer": "",
            "cookietime": "2592000",
        }
        r2 = session.post(
            f"{BASE_URL}/member.php?mod=logging&action=login&loginsubmit=yes&handlekey=login",
            data=login_data, timeout=15
        )
        r2.encoding = "gbk"
        if USERNAME in r2.text or "退出" in r2.text:
            print("  [登录] 登录成功")
            return True
        print("  [登录] 登录失败")
        return False
    except Exception as e:
        print(f"  [登录] 异常: {e}")
        return False


def get(url, retry_login=True):
    for attempt in range(3):
        try:
            r = session.get(url, timeout=20)
            r.encoding = "gbk"
            if "您需要登录才能继续本操作" in r.text or (r.url and "mod=logging" in r.url):
                if retry_login:
                    print("  [Cookie过期] 自动重新登录...")
                    if login():
                        return get(url, retry_login=False)
                return None
            return r.text
        except Exception as e:
            print(f"  [重试 {attempt+1}/3] {e}")
            time.sleep(5)
    return None


def load_json(path, default):
    path = Path(path)
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return default


def save_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def parse_time(time_str):
    if not time_str:
        return None
    try:
        time_str = time_str.strip()
        if len(time_str) <= 10:
            return datetime.strptime(time_str, "%Y-%m-%d")
        return datetime.strptime(time_str, "%Y-%m-%d %H:%M")
    except Exception:
        return None


def get_forum_thread_list(page):
    url = f"{BASE_URL}/forum-{FORUM_ID}-{page}.html"
    html = get(url)
    if not html:
        return [], False

    soup = BeautifulSoup(html, "html.parser")
    page_title = soup.title.get_text(strip=True) if soup.title else ""
    if "登录" in page_title and "会计视野" not in page_title:
        print("  [警告] 页面疑似未登录")
        return [], False

    threads = []
    seen = set()
    for tbody in soup.find_all("tbody", id=re.compile(r"^normalthread_")):
        a = tbody.find("a", class_="s xst")
        if not a:
            continue
        href = a.get("href", "")
        m = re.search(r"thread-(\d+)-", href)
        if not m:
            continue
        tid = m.group(1)
        if tid in seen:
            continue
        seen.add(tid)
        title_text = a.get_text(strip=True)
        if not title_text:
            continue
        # Discuz! uses two td.by cells: author and last-reply; use the last one
        last_reply_time = None
        td_by_list = tbody.select("td.by")
        if len(td_by_list) >= 2:
            time_span = td_by_list[-1].select_one("span[title]")
            if time_span:
                last_reply_time = parse_time(time_span.get("title", ""))
        if last_reply_time is None:
            spans = tbody.find_all("span", title=True)
            if spans:
                last_reply_time = parse_time(spans[-1].get("title", ""))
        threads.append({
            "tid": tid,
            "url": f"{BASE_URL}/thread-{tid}-1-1.html",
            "title": title_text,
            "last_reply_time": last_reply_time,
        })

    has_next = bool(soup.select("a.nxt"))
    return threads, has_next


def extract_text(td):
    NL = "@@NL@@"
    for tag in td.find_all("font"):
        tag.unwrap()
    for br in td.find_all("br"):
        br.replace_with(NL)
    for tag in td.find_all(["div", "p", "li", "tr"]):
        tag.append(NL)
    text = td.get_text(separator="", strip=False)
    text = text.replace(NL, "\n")
    text = re.sub(r"\n{2,}", "\n", text)
    text = re.sub(r" {2,}", " ", text)
    return text.strip()


def get_thread_conversation(tid, thread_url, thread_title):
    raw_floors = []
    extra_items = []
    page = 1
    first_author = None

    while True:
        url = f"{BASE_URL}/thread-{tid}-{page}-1.html"
        html = get(url)
        if not html:
            break

        soup = BeautifulSoup(html, "html.parser")
        page_title = soup.title.get_text(strip=True) if soup.title else ""
        if "提示信息" in page_title:
            break

        floor_num = (page - 1) * 10

        for post_div in soup.select("div[id^='post_']"):
            pid_m = re.fullmatch(r"post_(\d+)", post_div.get("id", ""))
            if not pid_m:
                continue
            pid = pid_m.group(1)
            floor_num += 1

            author_a = post_div.select_one(".authi a")
            if not author_a:
                continue
            author = author_a.get_text(strip=True)
            author_href = author_a.get("href", "")

            if first_author is None:
                first_author = author

            is_expert = (
                f"uid-{TARGET_UID}" in author_href or
                f"space-uid-{TARGET_UID}" in author_href or
                author.lower() == TARGET_USERNAME.lower()
            )
            is_questioner = (author == first_author)
            expert_rated = bool(soup.select_one(f"p[id='rate_{pid}_{TARGET_UID}']"))

            post_time = ""
            t_elem = post_div.select_one(f"em[id='authorposton{pid}']")
            if t_elem:
                span = t_elem.select_one("span[title]")
                post_time = span["title"] if span else t_elem.get_text(strip=True)
            post_time = re.sub(r"^发表于\s*", "", post_time).strip()

            content_td = post_div.select_one(f"td#postmessage_{pid}")
            if not content_td:
                continue

            quoted_pid = ""
            quote_block = content_td.select_one(".quote, blockquote")
            if quote_block:
                q_link = quote_block.select_one("a[href*='pid=']")
                if q_link:
                    qm = re.search(r"pid=(\d+)", q_link.get("href", ""))
                    if qm:
                        quoted_pid = qm.group(1)

            for q in content_td.select(".quote, blockquote, .pstatus"):
                q.decompose()
            text = extract_text(content_td)

            cm_div = soup.select_one(f"#comment_{pid}")
            if cm_div:
                for psta in cm_div.select("div.psta"):
                    cm_a = psta.select_one("a")
                    if not cm_a:
                        continue
                    cm_href = cm_a.get("href", "")
                    if f"uid-{TARGET_UID}" not in cm_href and f"space-uid-{TARGET_UID}" not in cm_href:
                        continue
                    psti = psta.find_next_sibling("div", class_="psti")
                    if not psti:
                        continue
                    cm_time_span = psti.select_one("span[title]")
                    cm_time = cm_time_span["title"] if cm_time_span else ""
                    for s in psti.select("span.xg1"):
                        s.decompose()
                    cm_text = psti.get_text(strip=True)
                    if len(cm_text) >= 1:
                        extra_items.append({
                            "pid": f"{pid}_comment",
                            "floor": floor_num,
                            "after_pid": pid,
                            "author": TARGET_USERNAME,
                            "role": "expert",
                            "type": "comment",
                            "time": cm_time,
                            "content": cm_text,
                        })

            if len(text) >= 2:
                raw_floors.append({
                    "pid": pid,
                    "floor": floor_num,
                    "author": author,
                    "is_expert": is_expert,
                    "is_questioner": is_questioner,
                    "expert_rated": expert_rated,
                    "quoted_pid": quoted_pid,
                    "expert_commented": False,
                    "type": "post",
                    "time": post_time,
                    "content": text,
                })

        if not soup.select("a.nxt"):
            break
        page += 1
        sleep()

    if not raw_floors:
        return None

    comment_target_pids = {item["after_pid"] for item in extra_items}
    for f in raw_floors:
        if f["pid"] in comment_target_pids:
            f["expert_commented"] = True

    expert_quoted_pids = {f["quoted_pid"] for f in raw_floors if f["is_expert"] and f["quoted_pid"]}

    directly_kept_pids = set()
    for f in raw_floors:
        if (f["is_expert"] or f["is_questioner"] or
                f["expert_rated"] or f["expert_commented"] or
                f["pid"] in expert_quoted_pids):
            directly_kept_pids.add(f["pid"])

    kept_authors = {f["author"] for f in raw_floors if f["pid"] in directly_kept_pids}
    final_kept_pids = {f["pid"] for f in raw_floors if f["author"] in kept_authors}

    if not any(f["is_expert"] for f in raw_floors if f["pid"] in final_kept_pids):
        return None

    pid_to_comments = {}
    for item in extra_items:
        pid_to_comments.setdefault(item["after_pid"], []).append(item)

    conversation = []
    for f in raw_floors:
        if f["pid"] not in final_kept_pids:
            continue
        floor_obj = {
            "pid": f["pid"],
            "floor": f["floor"],
            "author": f["author"],
            "role": "expert" if f["is_expert"] else ("questioner" if f["is_questioner"] else "other"),
            "type": "post",
            "time": f["time"],
            "content": f["content"],
        }
        if f["expert_rated"]:
            floor_obj["rated_by_expert"] = True
        if f["expert_commented"]:
            floor_obj["commented_by_expert"] = True
        if f["pid"] in expert_quoted_pids:
            floor_obj["quoted_by_expert"] = True
        conversation.append(floor_obj)
        for comment in pid_to_comments.get(f["pid"], []):
            c = {k: v for k, v in comment.items() if k != "after_pid"}
            conversation.append(c)

    return {
        "tid": tid,
        "thread_title": thread_title,
        "thread_url": thread_url,
        "conversation": conversation,
    }


def run_full(cp, done_tids, results):
    start_page = cp.get("last_page", 1)
    print(f"【全量模式】从第 {start_page} 页继续，已完成 {len(done_tids)} 帖\n")

    page = start_page
    total_checked = 0

    while True:
        print(f"[列表页 {page}/{MAX_PAGE}]")
        threads, has_next = get_forum_thread_list(page)
        if not threads:
            print("列表为空，停止")
            break

        print(f"  找到 {len(threads)} 个帖子")
        for t in threads:
            tid = t["tid"]
            if tid in done_tids:
                continue
            total_checked += 1
            result = get_thread_conversation(tid, t["url"], t["title"])
            if result:
                results.append(result)
                print(f"  ✓ tid={tid} 《{t['title'][:35]}》 -> {len(result['conversation'])} 条")
            else:
                print(f"  - tid={tid} 《{t['title'][:35]}》 -> 无陈版主参与")

            done_tids.add(tid)
            cp["done_tids"] = list(done_tids)
            cp["last_page"] = page
            save_json(CHECKPOINT_FILE, cp)
            save_json(OUTPUT_JSON, results)
            sleep()

        if not has_next or page >= MAX_PAGE:
            if total_checked > 0:
                cp["last_full_crawl_time"] = datetime.now().strftime("%Y-%m-%d %H:%M")
            save_json(CHECKPOINT_FILE, cp)
            print("\n全量爬取完成！")
            break

        page += 1
        cp["last_page"] = page
        save_json(CHECKPOINT_FILE, cp)
        sleep()

    return total_checked


def run_incremental(cp, done_tids, results):
    last_time_str = cp.get("last_full_crawl_time") or cp.get("last_incremental_time")
    if not last_time_str:
        print("【增量模式】未找到上次爬取时间，请先跑全量模式")
        return 0

    last_time = parse_time(last_time_str)
    print(f"【增量模式】上次爬取时间: {last_time_str}，只处理此后有新回复的帖子\n")

    page = 1
    total_checked = 0
    old_pages_count = 0

    while True:
        print(f"[列表页 {page}]")
        threads, has_next = get_forum_thread_list(page)
        if not threads:
            break

        new_threads = []
        all_old = True
        for t in threads:
            lrt = t.get("last_reply_time")
            # lrt is None means unparseable time → treat as old to avoid stale scraping
            if lrt is None or (last_time and lrt <= last_time):
                continue
            all_old = False
            new_threads.append(t)

        print(f"  找到 {len(new_threads)} 个新/更新帖子（共{len(threads)}个）")

        for t in new_threads:
            tid = t["tid"]
            total_checked += 1
            result = get_thread_conversation(tid, t["url"], t["title"])
            if result:
                existing = next((i for i, r in enumerate(results) if r["tid"] == tid), None)
                if existing is not None:
                    results[existing] = result
                    print(f"  ↻ tid={tid} 《{t['title'][:35]}》 -> 已更新")
                else:
                    results.append(result)
                    done_tids.add(tid)
                    print(f"  ✓ tid={tid} 《{t['title'][:35]}》 -> 新增")
            else:
                print(f"  - tid={tid} 《{t['title'][:35]}》 -> 无陈版主参与")

            save_json(OUTPUT_JSON, results)
            sleep()

        if all_old:
            old_pages_count += 1
            print(f"  [连续第 {old_pages_count}/{INC_STOP_PAGES} 页全为旧帖]")
            if old_pages_count >= INC_STOP_PAGES:
                print("连续多页均为旧帖，增量完成！")
                break
        else:
            old_pages_count = 0

        if not has_next:
            break
        page += 1
        sleep()

    cp["last_incremental_time"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    cp["done_tids"] = list(done_tids)
    save_json(CHECKPOINT_FILE, cp)
    return total_checked


def main():
    incremental = "--incremental" in sys.argv

    print("=" * 60)
    print(f"陈版主答疑爬取 - {'增量模式' if incremental else '全量模式'}")
    print("=" * 60)

    if not login():
        print("登录失败，退出")
        return

    cp = load_json(CHECKPOINT_FILE, {"done_tids": [], "last_page": 1})
    done_tids = set(cp.get("done_tids", []))
    results = load_json(OUTPUT_JSON, [])

    print(f"已有数据: {len(done_tids)} 帖已处理，{len(results)} 条有效对话\n")

    if incremental:
        total = run_incremental(cp, done_tids, results)
    else:
        total = run_full(cp, done_tids, results)

    print(f"\n{'='*60}")
    print(f"完成！本次处理 {total} 帖，共 {len(results)} 个有效对话")
    print(f"数据已保存至 {OUTPUT_JSON}")
    print(f"运行 python import_data.py 更新搜索索引")


if __name__ == "__main__":
    main()
