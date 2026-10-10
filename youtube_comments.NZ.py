#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""دریافت کامنت‌های یک ویدئوی یوتیوب با ادامهٔ خودکار دانلود ناتمام.

اجرای عادی: py youtube_comments.NZ.py
  - برداشت ناتمامِ همین ویدئو پیدا شود: از آخرین checkpoint ثبت‌شده ادامه می‌دهد.
  - برای یافتن دیتابیس، پوشهٔ فایل و پوشهٔ ترمینال و همسایه‌های نزدیک بررسی می‌شوند.
  - هیچ برداشت قبلی وجود نداشته باشد: یک برداشت جدید آغاز می‌شود.
  - فقط برداشت کامل وجود داشته باشد: پیام تکمیل می‌دهد؛ دوباره دانلود نمی‌کند.
  - چند برداشت ناتمام باشد: پیشرفته‌ترین دیتابیس را انتخاب می‌کند؛ چیزی ادغام/حذف نمی‌شود.
  - دادهٔ موجود خراب یا ناقص باشد: به‌جای شروع بی‌سروصدا از صفر، خطا می‌دهد.

گزینه‌های کمکی اختیاری: --status / --resume-run NAME / --start-new
پایتون 3.10 یا بالاتر؛ بدون نیاز به نصب پکیج خارجی.
"""

from __future__ import annotations

# ============================================================================
# ۱) تنها دو مقداری که برای هر ویدئو باید تنظیم کنید.
# کلید API را خصوصی نگه دارید؛ این فایلِ حاوی کلید را عمومی منتشر نکنید.
# ============================================================================
API_KEY = "AIzaSyBlmwWwNwC9GlSwGdfdXPVYsocGcgYY2oU"  # Your own private key, or YOUTUBE_API_KEY env var
VIDEO_URL_OR_ID = "https://www.youtube.com/watch?v=25AUCNZKEnY"

# ============================================================================
# ۲) کتابخانه‌های داخلی پایتون؛ به نصب پکیج اضافه نیاز نیست.
# ============================================================================
import argparse
import contextlib
import csv
import os
import datetime as datetime
import json
import random
import re
import sqlite3
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

# ============================================================================
# ۳) تنظیمات فنی ثابت؛ تعداد کامنت‌ها و Replyها هیچ سقف برنامه‌ای ندارد.
# هر برداشت داخل پوشهٔ youtube_data در کنار همین فایل ذخیره می‌شود.
# ============================================================================
# برای جلوگیری از گم شدن دیتابیس، پوشهٔ برنامه و ترمینال و پوشه‌های مجاور بررسی می‌شوند.
# مسیر صریح YOUTUBE_DATA_FOLDER بر جست‌وجوی خودکار اولویت دارد.
DATA_FOLDER = Path(os.environ["YOUTUBE_DATA_FOLDER"]).expanduser().resolve() if os.environ.get("YOUTUBE_DATA_FOLDER") else Path(__file__).resolve().parent / "youtube_data"
API_BASE = "https://www.googleapis.com/youtube/v3"
TIMEOUT_SECONDS = 40
QUOTA_RETRY_SECONDS = 3600  # مکث یک‌ساعته در صورت اتمام سهمیهٔ روزانهٔ API
BACKOFF_MAX_SECONDS = 240  # حداکثر مکث برای خطای موقت شبکه/سرور
VIDEO_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{11}$")


def now_utc() -> str:
    # ساعت را با UTC و منطقهٔ زمانی مشخص ذخیره می‌کنیم تا تحلیل تاریخ‌ها دقیق باشد.
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="microseconds")


def get_video_id(value: str) -> str:
    # شناسهٔ ۱۱ کاراکتری یا لینک‌های معمول watch، shorts، live و youtu.be را می‌پذیریم.
    value = value.strip()
    if VIDEO_ID_PATTERN.fullmatch(value):
        return value
    url = urllib.parse.urlparse(value if "://" in value else "https://" + value)
    hostname = (url.hostname or "").lower()
    path = [part for part in url.path.split("/") if part]
    video_id = ""
    if hostname in ("youtu.be", "www.youtu.be") and path:
        video_id = path[0]
    elif hostname in ("youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com"):
        if path and path[0] == "watch":
            video_id = urllib.parse.parse_qs(url.query).get("v", [""])[0]
        elif len(path) >= 2 and path[0] in ("shorts", "live", "embed"):
            video_id = path[1]
    if not VIDEO_ID_PATTERN.fullmatch(video_id):
        raise ValueError("شناسه یا لینک ویدئوی یوتیوب معتبر نیست.")
    return video_id


class APIRequestError(Exception):
    # خطاهای API را با نوع و شمارهٔ HTTP مشخص می‌کنیم تا خطا پنهان نشود.
    def __init__(self, status: int, reason: str, message: str):
        self.status = status
        self.reason = reason
        super().__init__(f"HTTP {status} ({reason}): {message[:250]}")


def read_api_error(error: urllib.error.HTTPError, key: str) -> APIRequestError:
    # پاسخ خطا را می‌خوانیم؛ کلید محرمانه از متن گزارش حذف می‌شود.
    try:
        document = json.loads(error.read().decode("utf-8", errors="replace"))
        detail = document.get("error", {})
        reasons = detail.get("errors", [])
        reason = str(reasons[0].get("reason", "")) if reasons else ""
        reason = reason or str(detail.get("status", "unknown"))
        message = str(detail.get("message", ""))
    except (ValueError, TypeError, AttributeError, IndexError):
        reason, message = "unknown", "متن خطای API قابل‌خواندن نبود"
    return APIRequestError(error.code, reason, message.replace(key, "[HIDDEN_API_KEY]"))


class YouTubeAPI:
    # فقط از درخواست HTTP GET استفاده می‌کنیم؛ هیچ محتوایی در حساب یوتیوب تغییر نمی‌کند.
    def __init__(self, key: str, opener=None, sleeper=None):
        self.key = key
        self.opener = opener or urllib.request.urlopen
        self.sleep = sleeper or time.sleep
        self.successful_calls = 0

    def get(self, resource: str, params: dict) -> dict:
        # تا هنگام رفع خطای موقت شبکه یا سهمیه صبر می‌کنیم؛ خطاهای دائمی را گزارش می‌کنیم.
        retry_number = 0
        while True:
            query = dict(params)
            query["key"] = self.key
            url = f"{API_BASE}/{resource}?{urllib.parse.urlencode(query)}"
            request = urllib.request.Request(url, headers={"Accept": "application/json"})
            try:
                with self.opener(request, timeout=TIMEOUT_SECONDS) as response:
                    payload = json.load(response)
                if not isinstance(payload, dict) or not isinstance(payload.get("items"), list):
                    raise RuntimeError("پاسخ API ساختار معتبر items ندارد؛ دانلود متوقف شد.")
                self.successful_calls += 1
                return payload
            except urllib.error.HTTPError as error:
                parsed = read_api_error(error, self.key)
                reason = parsed.reason.lower()
                if parsed.status == 403 and reason in ("quotaexceeded", "dailylimitexceeded"):
                    print("[QUOTA] سهمیه API تمام شده؛ یک ساعت دیگر دوباره تلاش می‌کنم.", flush=True)
                    self.sleep(QUOTA_RETRY_SECONDS)
                    continue
                if parsed.status not in (429, 500, 502, 503, 504) and reason not in (
                    "ratelimitexceeded", "userratelimitexceeded", "backenderror"
                ):
                    raise parsed
                retry_number += 1
                wait = min(BACKOFF_MAX_SECONDS, 2 ** min(retry_number, 8)) + random.uniform(0, 1)
                print(f"[RETRY] خطای موقت API؛ {wait:.1f} ثانیه انتظار.", flush=True)
                self.sleep(wait)
            except (urllib.error.URLError, ConnectionError, TimeoutError, OSError) as error:
                retry_number += 1
                wait = min(BACKOFF_MAX_SECONDS, 2 ** min(retry_number, 8)) + random.uniform(0, 1)
                print(f"[NETWORK] خطای {type(error).__name__}؛ {wait:.1f} ثانیه انتظار.", flush=True)
                self.sleep(wait)


# ============================================================================
# ۴) دیتابیس فقط برای همین برداشت است؛ داده‌های کامنت فقط INSERT می‌شوند.
# جدول checkpoints صرفاً نگه‌دارندهٔ توکن صفحهٔ بعدی برای ادامهٔ دانلود ناتمام است.
# هیچ DELETE، DROP یا UPDATE برای کامنت‌ها و فایل‌های خروجی نداریم.
# ============================================================================
DATABASE_SCHEMA = """
CREATE TABLE IF NOT EXISTS metadata (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS comments (
  comment_id TEXT PRIMARY KEY,
  video_id TEXT NOT NULL,
  parent_id TEXT,
  kind TEXT NOT NULL CHECK(kind IN ('parent', 'reply')),
  author_name TEXT,
  author_channel_id TEXT,
  author_channel_url TEXT,
  text_original TEXT,
  text_display TEXT,
  published_at TEXT,
  updated_at TEXT,
  like_count INTEGER,
  collected_at TEXT NOT NULL,
  reported_reply_count INTEGER NOT NULL DEFAULT 0,
  raw_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_comments_kind_parent ON comments(kind, parent_id);
CREATE TABLE IF NOT EXISTS checkpoints (
  seq INTEGER PRIMARY KEY AUTOINCREMENT,
  section TEXT NOT NULL CHECK(section IN ('parents', 'replies')),
  parent_id TEXT NOT NULL DEFAULT '',
  next_page_token TEXT NOT NULL DEFAULT '',
  finished INTEGER NOT NULL,
  saved_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_checkpoints_section ON checkpoints(section, parent_id, seq);
"""


def connect_database(file_path: Path) -> sqlite3.Connection:
    # تراکنش SQLite باعث می‌شود ثبت کامنت‌ها و ثبت توکن بعدی با هم کامل شوند.
    # اگر وسط ذخیره برق برود، صفحهٔ نصفه ثبت نمی‌شود و دوباره دریافت خواهد شد.
    connection = sqlite3.connect(str(file_path), timeout=60)
    connection.row_factory = sqlite3.Row
    connection.executescript(DATABASE_SCHEMA)
    return connection


def record_metadata(db: sqlite3.Connection, video_id: str):
    # این اطلاعات یک بار هنگام ایجاد دیتابیس تازه ثبت می‌شوند.
    with db:
        db.execute("INSERT OR IGNORE INTO metadata(key, value) VALUES (?, ?)", ("video_id", video_id))
        db.execute("INSERT OR IGNORE INTO metadata(key, value) VALUES (?, ?)", ("started_at", now_utc()))


def last_checkpoint(db: sqlite3.Connection, section: str, parent_id: str = ""):
    # جدیدترین توکنِ ذخیره‌شده را بدون تغییر اطلاعات قبلی می‌خوانیم.
    return db.execute(
        """SELECT next_page_token, finished FROM checkpoints
           WHERE section=? AND parent_id=? ORDER BY seq DESC LIMIT 1""",
        (section, parent_id),
    ).fetchone()


def insert_comment(db: sqlite3.Connection, resource: dict, video_id: str,
                   kind: str, parent_id: str | None = None, reported_replies: int = 0):
    # تمام اطلاعات لازم برای تحلیل (و پاسخ خام API) را بدون اصلاح یا برچسب AI ذخیره می‌کنیم.
    snippet = resource.get("snippet", {})
    comment_id = resource.get("id")
    if not isinstance(comment_id, str) or not comment_id:
        raise RuntimeError("کامنت بدون شناسه است؛ صفحه ذخیره نشد.")
    author_id = snippet.get("authorChannelId") or {}
    if not isinstance(author_id, dict):
        author_id = {}
    db.execute(
        """INSERT OR IGNORE INTO comments (
             comment_id, video_id, parent_id, kind, author_name, author_channel_id,
             author_channel_url, text_original, text_display, published_at, updated_at,
             like_count, collected_at, reported_reply_count, raw_json
           ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            comment_id, video_id, parent_id, kind,
            snippet.get("authorDisplayName"), author_id.get("value"),
            snippet.get("authorChannelUrl"),
            snippet.get("textOriginal", snippet.get("textDisplay", "")),
            snippet.get("textDisplay", ""), snippet.get("publishedAt"),
            snippet.get("updatedAt"), snippet.get("likeCount", 0), now_utc(),
            reported_replies if kind == "parent" else 0,
            json.dumps(resource, ensure_ascii=False),
        ),
    )


def save_page(db: sqlite3.Connection, section: str, parent_id: str, page: dict, video_id: str):
    # کامنت‌های همین صفحه و توکنِ صفحهٔ بعدی را در یک تراکنش واحد ثبت می‌کنیم.
    # اطلاعات صفحه‌های قبلی حذف یا بازنویسی نمی‌شوند.
    next_token = str(page.get("nextPageToken") or "")
    with db:
        for item in page["items"]:
            if section == "parents":
                snippet = item.get("snippet", {})
                original = snippet.get("topLevelComment")
                if not isinstance(original, dict):
                    raise RuntimeError("Parent نامعتبر است؛ صفحه ذخیره نشد.")
                insert_comment(db, original, video_id, "parent", reported_replies=int(snippet.get("totalReplyCount", 0)))
            else:
                # پاسخ همیشه به شناسهٔ Parent متصل می‌ماند.
                insert_comment(db, item, video_id, "reply", parent_id=parent_id)
        db.execute(
            """INSERT INTO checkpoints(section, parent_id, next_page_token, finished, saved_at)
               VALUES (?, ?, ?, ?, ?)""",
            (section, parent_id, next_token, int(not next_token), now_utc()),
        )
    return next_token


def count_comments(db: sqlite3.Connection):
    # برای گزارش زنده، فقط رکوردهای واقعاً ذخیره‌شده را می‌شماریم.
    result = dict(db.execute("SELECT kind, COUNT(*) FROM comments GROUP BY kind").fetchall())
    return result.get("parent", 0), result.get("reply", 0)


def collect_parent_pages(db: sqlite3.Connection, api: YouTubeAPI, video_id: str):
    # بدون تعیین سقف صفحات، تا وقتی nextPageToken وجود داشته باشد جلو می‌رویم.
    checkpoint = last_checkpoint(db, "parents")
    if checkpoint and checkpoint["finished"]:
        return
    token = checkpoint["next_page_token"] if checkpoint else ""
    while True:
        params = {"part": "snippet", "videoId": video_id, "maxResults": 100,
                  "order": "time", "textFormat": "plainText"}
        if token:
            params["pageToken"] = token
        page = api.get("commentThreads", params)
        previous_token = token
        token = save_page(db, "parents", "", page, video_id)
        parents, replies = count_comments(db)
        print(f"[PARENTS] {parents:,} parent | {replies:,} replies", flush=True)
        if not token:
            break
        if token == previous_token:
            raise RuntimeError("YouTube همان pageToken را برگرداند؛ برای جلوگیری از حلقه متوقف شدم.")


def next_reply_parent(db: sqlite3.Connection):
    # Parentهایی را پیدا می‌کنیم که طبق اطلاعات یوتیوب Reply دارند اما دریافتشان کامل نشده.
    return db.execute(
        """SELECT c.comment_id, c.reported_reply_count FROM comments AS c
           WHERE c.kind='parent' AND c.reported_reply_count > 0
             AND NOT EXISTS (
               SELECT 1 FROM checkpoints AS cp
               WHERE cp.section='replies' AND cp.parent_id=c.comment_id AND cp.finished=1
             )
           ORDER BY c.published_at, c.comment_id LIMIT 1"""
    ).fetchone()


def collect_reply_pages(db: sqlite3.Connection, api: YouTubeAPI, video_id: str):
    # برای هر Parent، همهٔ صفحات Reply را جداگانه دریافت می‌کنیم؛ فقط نمونهٔ محدود نمی‌گیریم.
    while True:
        parent = next_reply_parent(db)
        if parent is None:
            break
        parent_id = parent["comment_id"]
        checkpoint = last_checkpoint(db, "replies", parent_id)
        token = checkpoint["next_page_token"] if checkpoint else ""
        while True:
            params = {"part": "snippet", "parentId": parent_id,
                      "maxResults": 100, "textFormat": "plainText"}
            if token:
                params["pageToken"] = token
            page = api.get("comments", params)
            previous_token = token
            token = save_page(db, "replies", parent_id, page, video_id)
            if not token:
                break
            if token == previous_token:
                raise RuntimeError("توکن Reply تکرار شد؛ برای جلوگیری از حلقه متوقف شدم.")
        parents, replies = count_comments(db)
        print(f"[REPLIES] {parents:,} parent | {replies:,} replies", flush=True)


# ============================================================================
# ۵) خروجی‌ها: فقط پس از دریافت همهٔ صفحات، در یک پوشهٔ جدید ایجاد می‌شوند.
# حالت بازکردن فایل با x اجازهٔ بازنویسی فایل موجود را نمی‌دهد.
# ============================================================================
CSV_COLUMNS = [
    "comment_id", "video_id", "parent_id", "kind", "author_name", "author_channel_id",
    "author_channel_url", "text_original", "text_display", "published_at", "updated_at",
    "like_count", "collected_at", "reported_reply_count"
]


def export_record(row: sqlite3.Row) -> dict:
    # ستون‌های یکسان در CSV و JSONL دسترسی دوباره به داده را آسان می‌کنند.
    return {key: row[key] for key in CSV_COLUMNS}


def export_files(db: sqlite3.Connection, run_folder: Path, video_id: str) -> Path:
    # برای محافظت از فایل‌ها، هر تلاش خروجی‌گیری پوشهٔ تازه و یکتا می‌سازد.
    # اگر زمان خروجی‌گیری برق برود، پوشهٔ ناقص باقی می‌ماند، اما حذف یا بازنویسی نمی‌شود.
    export_folder = run_folder / ("export_" + uuid.uuid4().hex)
    export_folder.mkdir(parents=False, exist_ok=False)

    def rows():
        return db.execute("SELECT * FROM comments ORDER BY published_at, comment_id")

    def parents():
        return db.execute("SELECT * FROM comments WHERE kind='parent' ORDER BY published_at, comment_id")

    def replies(parent_id: str):
        return db.execute(
            "SELECT * FROM comments WHERE kind='reply' AND parent_id=? ORDER BY published_at, comment_id",
            (parent_id,),
        )

    # خروجی Flat برای تحلیل آماری و پیوند بر اساس parent_id.
    with (export_folder / "comments_flat.csv").open("x", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        for comment in rows():
            writer.writerow(export_record(comment))

    # خروجی JSONL خام: متن اصلی API همراه سایر خصوصیاتِ هر کامنت.
    with (export_folder / "comments_raw.jsonl").open("x", encoding="utf-8") as file:
        for comment in rows():
            file.write(json.dumps({
                "comment_id": comment["comment_id"],
                "raw_comment": json.loads(comment["raw_json"]),
                "collected_at": comment["collected_at"],
            }, ensure_ascii=False) + "\n")

    # خروجی رشتهٔ گفتگو برای AI: هر Parent همراه تمام Replyهای همان Parent.
    with (export_folder / "threads.jsonl").open("x", encoding="utf-8") as file:
        for parent in parents():
            file.write('{"parent":')
            file.write(json.dumps(export_record(parent), ensure_ascii=False))
            file.write(',"replies":[')
            first = True
            for reply in replies(parent["comment_id"]):
                if not first:
                    file.write(",")
                file.write(json.dumps(export_record(reply), ensure_ascii=False))
                first = False
            file.write("]}\n")

    # خروجی انسان‌خوان: Replyها با تورفتگی زیر Parent نمایش داده می‌شوند.
    with (export_folder / "threads_readable.txt").open("x", encoding="utf-8") as file:
        file.write(f"Video: https://www.youtube.com/watch?v={video_id}\n\n")
        for parent in parents():
            file.write(f"PARENT {parent['comment_id']} | likes={parent['like_count']} | "
                       f"date={parent['published_at']} | author={parent['author_name']}\n")
            file.write((parent["text_original"] or "") + "\n")
            for reply in replies(parent["comment_id"]):
                file.write(f"  REPLY {reply['comment_id']} -> {parent['comment_id']} | "
                           f"likes={reply['like_count']} | date={reply['published_at']} | "
                           f"author={reply['author_name']}\n")
                file.write("  " + (reply["text_original"] or "").replace("\n", "\n  ") + "\n")
            file.write("\n" + "=" * 72 + "\n\n")

    # گزارش پایانی تعداد کامنت‌ها و احتمال اختلاف با شمار Reply اعلام‌شدهٔ یوتیوب.
    parent_count, reply_count = count_comments(db)
    expected = db.execute("SELECT COALESCE(SUM(reported_reply_count),0) FROM comments WHERE kind='parent'").fetchone()[0]
    report = {
        "video_id": video_id,
        "video_url": f"https://www.youtube.com/watch?v={video_id}",
        "started_at_utc": db.execute("SELECT value FROM metadata WHERE key='started_at'").fetchone()[0],
        "finished_at_utc": now_utc(),
        "parent_comments_collected": parent_count,
        "replies_collected": reply_count,
        "total_comments_collected": parent_count + reply_count,
        "replies_reported_by_youtube_at_collection": expected,
        "reported_reply_count_differs": reply_count != expected,
        "api_scope": "Public comments accessible through YouTube Data API",
        "note": "No periodic refresh; no automatic deletion; one collection per completed run",
    }
    with (export_folder / "collection_report.json").open("x", encoding="utf-8") as file:
        json.dump(report, file, ensure_ascii=False, indent=2)
    return export_folder


def discover_data_folders() -> list[Path]:
    """Look for youtube_data near script and terminal; never search unrelated drives.

    Existing projects are usually one folder away if the .py file was moved.
    An explicit environment variable overrides automatic discovery.
    """
    configured = os.environ.get("YOUTUBE_DATA_FOLDER")
    if configured:
        return [Path(configured).expanduser().resolve()]

    script_dir = Path(__file__).resolve().parent
    cwd = Path.cwd().resolve()
    candidates: list[Path] = [DATA_FOLDER]
    anchors = [script_dir, cwd, script_dir.parent, cwd.parent]
    seen_anchors: set[Path] = set()
    for anchor in anchors:
        if anchor in seen_anchors:
            continue
        seen_anchors.add(anchor)
        candidates.append(anchor / "youtube_data")
        # محدود به یک سطح زیرپوشه برای جلوگیری از جست‌وجوی بی‌پایان در دیسک.
        if anchor.is_dir() and anchor.parent != anchor:
            try:
                for child in anchor.iterdir():
                    if child.is_dir() and not child.is_symlink() and child.name not in (
                        ".git", ".venv", "venv", "node_modules", "__pycache__"
                    ):
                        candidate = child / "youtube_data"
                        if candidate.is_dir():
                            candidates.append(candidate)
            except OSError:
                pass
    result: list[Path] = []
    seen: set[Path] = set()
    for folder in candidates:
        folder = folder.resolve()
        if folder not in seen:
            result.append(folder)
            seen.add(folder)
    return result


def list_collection_folders(video_id: str) -> list[Path]:
    # هیچ فولدر جدیدی هنگام جست‌وجو ساخته نمی‌شود.
    folders: list[Path] = []
    for root in discover_data_folders():
        base = root / video_id
        if not base.is_dir():
            continue
        folders.extend(p for p in base.iterdir()
                       if p.is_dir() and p.name.startswith("collection_"))
    return sorted(folders, key=lambda p: (str(p.parent), p.name))


def open_existing_database_readonly(db_file: Path) -> sqlite3.Connection:
    # Opening with mode=ro prevents accidentally creating an empty database.
    if not db_file.is_file():
        raise ValueError(f"Missing existing database: {db_file}")
    address = urllib.parse.quote(db_file.resolve().as_posix(), safe="/:")
    conn = sqlite3.connect(f"file:{address}?mode=ro", uri=True, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def check_resume_folder(folder: Path, video_id: str) -> Path:
    if not folder.is_dir() or not folder.name.startswith("collection_"):
        raise ValueError(f"Existing collection folder not found: {folder}")
    if (folder / "FINISHED.txt").exists():
        raise ValueError(f"This run is already finished (will not restart it): {folder}")
    try:
        with open_existing_database_readonly(folder / "collection.sqlite3") as db:
            meta = db.execute("SELECT value FROM metadata WHERE key='video_id'").fetchone()
            if meta is None or meta[0] != video_id:
                raise ValueError(f"Video ID mismatch in existing database: {folder}")
            db.execute("SELECT COUNT(*) FROM comments").fetchone()
            db.execute("SELECT COUNT(*) FROM checkpoints").fetchone()
    except sqlite3.Error as err:
        raise ValueError(f"Existing database cannot be read; download not started: {err}") from err
    return folder


def show_status(video_id: str) -> None:
    # Read-only. Does not create a database, folder or network request.
    base = DATA_FOLDER / video_id
    print(f"[STATUS] Video ID: {video_id}")
    print(f"[STATUS] Default data folder: {base}")
    print("[STATUS] Searching nearby youtube_data folders automatically...")
    folders = list_collection_folders(video_id)
    if not folders:
        print("[STATUS] No collection folders found in this location. No download started.")
        return
    for folder in folders:
        state = "FINISHED" if (folder / "FINISHED.txt").is_file() else "INCOMPLETE"
        db_file = folder / "collection.sqlite3"
        try:
            with open_existing_database_readonly(db_file) as db:
                counts = count_comments(db)
                meta = db.execute("SELECT value FROM metadata WHERE key='video_id'").fetchone()
                db_video = meta[0] if meta else "UNKNOWN"
                checkpoints = db.execute("SELECT COUNT(*) FROM checkpoints").fetchone()[0]
            print(f"[{state}] {folder} | parents={counts[0]:,} | replies={counts[1]:,} | "
                  f"checkpoints={checkpoints} | video={db_video}")
        except (sqlite3.Error, ValueError) as err:
            print(f"[{state}] {folder.name} | DATABASE ERROR: {err}")
    print("[STATUS] No download started.")


class VideoDownloadLock:
    """Cross-platform OS lock, automatically released even after a power failure.

    Do not run two copies for the same video. The lock file itself is harmless
    and may remain, but Windows/Linux release its OS lock when a process exits.
    """
    def __init__(self, base: Path):
        self.base = base
        self.handle = None

    def __enter__(self):
        self.base.mkdir(parents=True, exist_ok=True)
        self.handle = (self.base / ".collector.lock").open("a+b")
        try:
            self.handle.seek(0, 2)
            if self.handle.tell() == 0:
                self.handle.write(b"0")
                self.handle.flush()
            self.handle.seek(0)
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(self.handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as err:
            self.handle.close()
            self.handle = None
            raise ValueError(
                "Another collector may be running for this video; close it before continuing."
            ) from err
        return self

    def __exit__(self, exc_type, exc, tb):
        if self.handle is not None:
            try:
                self.handle.seek(0)
                if os.name == "nt":
                    import msvcrt
                    msvcrt.locking(self.handle.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(self.handle.fileno(), fcntl.LOCK_UN)
            finally:
                self.handle.close()
        return False


def inspect_incomplete_run(folder: Path, video_id: str) -> tuple[int, int, str]:
    """اعتبارسنجیِ غیرتغییردهنده و امتیازدهی به میزان دادهٔ ذخیره‌شده."""
    check_resume_folder(folder, video_id)
    with open_existing_database_readonly(folder / "collection.sqlite3") as db:
        parents, replies = count_comments(db)
        last_parents = last_checkpoint(db, "parents")
        if (parents or replies) and last_parents is None:
            raise ValueError(f"Saved comments exist but checkpoint is missing: {folder}")
        latest = db.execute("SELECT COALESCE(MAX(saved_at), '') FROM checkpoints").fetchone()[0]
    return parents, replies, latest or ""


def choose_collection_folder(video_id: str, *, start_new: bool = False,
                             resume_run: str | None = None) -> tuple[Path | None, bool]:
    base = DATA_FOLDER / video_id
    if start_new:
        base.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
        fresh = base / (f"collection_{timestamp}_{uuid.uuid4().hex[:6]}")
        fresh.mkdir(exist_ok=False)
        return fresh, False

    runs = list_collection_folders(video_id)
    if resume_run is not None:
        if not re.fullmatch(r"collection_[A-Za-z0-9_-]+", resume_run):
            raise ValueError("Invalid collection name. Use only collection_...")
        matches = [f for f in runs if f.name == resume_run]
        if len(matches) != 1:
            raise ValueError(f"Expected exactly one matching saved run; found {len(matches)} for {resume_run}")
        return check_resume_folder(matches[0], video_id), True

    unfinished = [p for p in runs if not (p / "FINISHED.txt").is_file()]
    if unfinished:
        ranked = []
        for folder in unfinished:
            # ناتمام/خراب را هیچ‌وقت به برداشت جدید تبدیل نکن.
            parents, replies, timestamp = inspect_incomplete_run(folder, video_id)
            ranked.append((parents + replies, parents, replies, timestamp, str(folder), folder))
        best = max(ranked)
        if len(ranked) > 1:
            print(f"[AUTO] Found {len(ranked)} unfinished downloads; chose most saved comments: "
                  f"{best[-1]} (parents={best[1]}, replies={best[2]}).", flush=True)
            print("[AUTO] Other runs are kept separately, never deleted or merged.", flush=True)
        return best[-1], True

    if runs:
        print("[DONE] All found collections are already finished. Nothing to resume. "
              "Use --start-new only if you want another collection.", flush=True)
        return None, False

    print("[AUTO] Searched near script/terminal, found no saved collection for this video.", flush=True)
    print(f"[AUTO] Starting NEW collection in: {base}", flush=True)
    return choose_collection_folder(video_id, start_new=True)


def main(argv: list[str] | None = None) -> int:
    try:
        parser = argparse.ArgumentParser(description="YouTube comments collector: auto-resume, or start new if none exists")
        group = parser.add_mutually_exclusive_group()
        group.add_argument("--status", action="store_true", help="show all local runs, no downloads")
        group.add_argument("--start-new", action="store_true", help="force a NEW collection even if old ones exist")
        group.add_argument("--resume-run", metavar="NAME", help="resume the specified collection_... folder")
        args = parser.parse_args(argv)
        video_id = get_video_id(VIDEO_URL_OR_ID)
        if args.status:
            show_status(video_id)
            return 0

        # Check key before making even a new folder. No key is shipped in this file.
        key = (os.environ.get("YOUTUBE_API_KEY") or API_KEY).strip()
        if not key or key == "PASTE_YOUR_YOUTUBE_API_KEY_HERE":
            raise ValueError("Set API_KEY at top of file (or environment variable YOUTUBE_API_KEY). "
                             "No download started.")

        with VideoDownloadLock(DATA_FOLDER / video_id):
            folder, resumed = choose_collection_folder(video_id,
                                                        start_new=args.start_new,
                                                        resume_run=args.resume_run)
            if folder is None:
                return 0  # همهٔ برداشت‌های پیدا شده کامل هستند.
            print(f"[START] {'RESUMING EXISTING' if resumed else 'NEW COLLECTION'}: {folder}", flush=True)
            # If the saved collection is in a neighboring folder, lock that location too.
            secondary_lock = (VideoDownloadLock(folder.parent) if folder.parent.resolve() !=
                              (DATA_FOLDER / video_id).resolve() else contextlib.nullcontext())
            with secondary_lock:
                db_file = folder / "collection.sqlite3"
                if resumed and not db_file.is_file():
                    raise ValueError(f"Resume DB missing, refusing to create it: {db_file}")
                db = connect_database(db_file)
                try:
                    record_metadata(db, video_id)
                    api = YouTubeAPI(key)
                    collect_parent_pages(db, api, video_id)
                    collect_reply_pages(db, api, video_id)
                    export_folder = export_files(db, folder, video_id)
                    # FINISHED only after all exports are written.
                    with (folder / "FINISHED.txt").open("x", encoding="utf-8") as file:
                        file.write(f"Complete: {now_utc()}\nExport folder: {export_folder.name}\n")
                    parents, replies = count_comments(db)
                    expected = db.execute(
                        "SELECT COALESCE(SUM(reported_reply_count),0) "
                        "FROM comments WHERE kind='parent'"
                    ).fetchone()[0]
                    print(f"[DONE] Parents={parents:,} | Replies={replies:,} | Total={parents+replies:,}", flush=True)
                    if replies != expected:
                        print(f"[WARNING] YouTube reported {expected:,} replies but API returned {replies:,}. "
                              "See collection_report.json.", flush=True)
                    print(f"[FILES] {export_folder}", flush=True)
                    return 0
                finally:
                    db.close()
    except KeyboardInterrupt:
        print("\n[PAUSED] Stopped. Already-committed pages remain saved.", flush=True)
        return 130
    except (ValueError, RuntimeError, sqlite3.Error, APIRequestError, OSError) as err:
        print(f"[ERROR] {err}", file=sys.stderr, flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
