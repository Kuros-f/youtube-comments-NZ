<div align="center">

# YouTube Comments & Replies Collector

### Collect, organize, and analyze public YouTube discussions

<picture><img src="https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white" alt="Python 3.10+"></picture>
<picture><img src="https://img.shields.io/badge/YouTube_Data_API-v3-FF0033?logo=youtube&logoColor=white" alt="YouTube Data API v3"></picture>
<picture><img src="https://img.shields.io/badge/Auto_Resume-Enabled-2DA44E" alt="Auto Resume Enabled"></picture>
<picture><img src="https://img.shields.io/badge/Exports-CSV_%7C_JSONL_%7C_SQLite-0969DA" alt="CSV JSONL SQLite"></picture>

**COLLECT · PRESERVE · RESUME · EXPORT**

A Python tool for collecting publicly accessible YouTube comments and replies using the **YouTube Data API v3**. It preserves conversation relationships, saves structured datasets, and resumes interrupted collections from the last saved checkpoint.

</div>

---

## <picture><img src="https://img.shields.io/badge/01-OVERVIEW-2563EB?style=for-the-badge" alt="01 Overview"></picture>

This project helps researchers and analysts collect YouTube discussions without losing the context of replies.

**At a glance**

- 🔵 **Source:** Public comments and replies accessible through the YouTube Data API v3.
- 🟣 **Structure:** Parent comments remain connected to their replies.
- 🟢 **Continuity:** Collection progress is saved for automatic resumption.
- 🟠 **Results:** Structured files for inspection, storage, and analysis.

---

## <picture><img src="https://img.shields.io/badge/02-KEY_FEATURES-8B5CF6?style=for-the-badge" alt="02 Key Features"></picture>

| Capability | What it does |
|:---|:---|
| 💬 **Parent comments & replies** | Collects public parent comments and their replies. |
| 🔗 **Thread relationships** | Preserves the link between a reply and its parent comment. |
| 👤 **Comment metadata** | Saves text, author information, likes, timestamps, and unique IDs. |
| 🔄 **Automatic resume** | Continues an interrupted collection from its saved checkpoint. |
| 🛡️ **Duplicate prevention** | Avoids duplicate records in the database. |
| 🎯 **Flexible target** | Accepts different YouTube video URLs or video IDs. |
| 📊 **Research exports** | Produces CSV, JSONL, SQLite, and readable text outputs. |

---

## <picture><img src="https://img.shields.io/badge/03-HOW_IT_WORKS-0891B2?style=for-the-badge" alt="03 How It Works"></picture>

The collector checks for existing collection data before requesting more comments.

```text
YouTube Video URL or ID
           |
           v
   YouTube Data API v3
           |
           v
    Parent Comments
           |
           v
      Replies
           |
           v
  SQLite + Checkpoints
           |
           v
  CSV / JSONL / TXT / Report
```

### Collection status guide

| Status | Action |
|:---|:---|
| <picture><img src="https://img.shields.io/badge/NEW-START-2563EB?style=flat-square" alt="New: start"></picture> | No previous collection: starts a new collection. |
| <picture><img src="https://img.shields.io/badge/INCOMPLETE-RESUME-F59E0B?style=flat-square" alt="Incomplete: resume"></picture> | Saved but unfinished collection: resumes from the latest checkpoint. |
| <picture><img src="https://img.shields.io/badge/COMPLETE-SKIP-16A34A?style=flat-square" alt="Complete: skip"></picture> | Completed collection: avoids unnecessary re-downloading. |

---

## <picture><img src="https://img.shields.io/badge/04-QUICK_START-16A34A?style=for-the-badge" alt="04 Quick Start"></picture>

### Step 1 — Requirements

- **Python 3.10+**
- **YouTube Data API v3 key**
- **Internet connection**

### Step 2 — Configure the script

Open `youtube_comments.NZ.py` and set these two values:

| Setting | What to enter |
|:---|:---|
| `API_KEY` | Your own YouTube Data API v3 key. |
| `VIDEO_URL_OR_ID` | The YouTube video URL or video ID to collect. |

> [!IMPORTANT]
> Keep your real API key private. Do not commit credentials to a public GitHub repository.

### Step 3 — Run

In PowerShell, from the directory containing the script:

```powershell
py youtube_comments.NZ.py
```

### Step 4 — Check the results

When data has been saved, inspect the files listed in **Output Files** below. If the collection is interrupted, rerun the same command to let the program check its saved progress.

---

## <picture><img src="https://img.shields.io/badge/05-OUTPUT_FILES-0D9488?style=for-the-badge" alt="05 Output Files"></picture>

| File | Contents | Useful for |
|:---|:---|:---|
| `collection.sqlite3` | Collected records and progress information. | Storage and resumption. |
| `comments_flat.csv` | One structured record per comment or reply. | Spreadsheets and analytics. |
| `comments_raw.jsonl` | Raw comment records. | Programmatic processing. |
| `threads.jsonl` | Parent comments grouped with replies. | Conversation analysis. |
| `threads_readable.txt` | Human-readable discussion threads. | Manual review. |
| `collection_report.json` | Collection statistics and summary. | Monitoring and reporting. |

**Organization:** Collected data is organized by video ID and collection session.

---

## <picture><img src="https://img.shields.io/badge/06-AUTOMATIC_RESUME-F59E0B?style=for-the-badge" alt="06 Automatic Resume"></picture>

The resume mechanism is designed to reduce repeated collection work after an interruption.

- 🟠 **Internet interruption:** Restart the script when the connection is available.
- 🔵 **Computer shutdown:** Run the script again using the same target.
- 🟣 **Manual stop:** Restart the program to continue from its saved checkpoint.
- 🟢 **Previously completed collection:** Avoid downloading the same dataset again unnecessarily.

**Remember:** Resumption depends on the existence and integrity of the saved checkpoint and database files.

---

## <picture><img src="https://img.shields.io/badge/07-RESEARCH_APPLICATIONS-7C3AED?style=for-the-badge" alt="07 Research Applications"></picture>

The exports can be used as input datasets for:

- 📈 **Engagement analysis** — Explore likes, replies, and discussion activity.
- 💬 **Conversation analysis** — Examine exchanges within comment threads.
- 🧠 **Sentiment research** — Prepare comment text for subsequent sentiment analysis.
- 🌐 **Digital media studies** — Study public discussions around online videos.
- 🔬 **Academic research** — Build structured datasets for further investigation.

**Note:** This project collects data; it does not claim to perform sentiment classification or other advanced analyses by itself.

---

## <picture><img src="https://img.shields.io/badge/08-LIMITATIONS_%26_SECURITY-DC2626?style=for-the-badge" alt="08 Limitations and Security"></picture>

> [!WARNING]
> **API key security:** Never upload an active API key, access token, or private credential to GitHub. If a key has been exposed, revoke or restrict it in the relevant Google Cloud project.

- 🔴 **Public access only:** Private, deleted, disabled, or unavailable comments may not be returned by the API.
- 🟠 **API quotas:** Requests are subject to YouTube Data API quotas and limitations.
- 🔵 **Dataset coverage:** Output reflects what the API makes available during collection; it is not a guarantee of every comment ever posted.

---

## <picture><img src="https://img.shields.io/badge/09-PROJECT_PURPOSE-475569?style=for-the-badge" alt="09 Project Purpose"></picture>

**YouTube Comments & Replies Collector** is intended to make public YouTube discussion data easier to collect, preserve, and prepare for research. Its focus is **reliable data collection, relationship preservation, structured exports, and checkpoint-based continuity**.

---

<div align="center">

<picture><img src="https://img.shields.io/badge/LANGUAGE-PERSIAN-7B2CBF?style=for-the-badge" alt="Persian language section"></picture>

</div>

<div dir="rtl" align="right">

<h2>🇮🇷 ۱۰ ـ معرفی فارسی</h2>

<h3>🔵 معرفی برنامه</h3>

<p><strong>جمع‌آوری نظرات و پاسخ‌های یوتیوب</strong> ابزاری است که با پایتون و رابط رسمی YouTube Data API v3، نظرات عمومی کاربران و پاسخ‌های مربوط به آن‌ها را دریافت و در فایل‌های ساخت‌یافته ذخیره می‌کند.</p>

<h3>🟣 قابلیت‌های اصلی</h3>

<ul>
<li>💬 دریافت نظرات اصلی و پاسخ‌های مرتبط</li>
<li>🔗 حفظ ارتباط میان هر نظر و پاسخ‌های آن</li>
<li>👤 ذخیره متن، اطلاعات نویسنده، لایک، زمان انتشار و شناسه‌های یکتا</li>
<li>🔄 ادامه خودکار جمع‌آوری از آخرین نقطه ذخیره‌شده</li>
<li>🛡️ جلوگیری از ثبت اطلاعات تکراری</li>
<li>📊 تهیه خروجی در قالب‌های CSV، JSONL، SQLite و متن خوانا</li>
</ul>

<h3>🟢 روش اجرا</h3>

<ol>
<li>پایتون نسخه ۳٫۱۰ یا بالاتر را آماده کنید.</li>
<li>کلید دسترسی رابط رسمی یوتیوب را دریافت کنید.</li>
<li>در فایل برنامه، مقدارهای <code>API_KEY</code> و <code>VIDEO_URL_OR_ID</code> را تنظیم کنید.</li>
<li>فرمان اجرای برنامه را که در بخش <strong>Quick Start</strong> آمده است، در PowerShell اجرا کنید.</li>
</ol>

<h3>🟠 ادامه دانلود پس از توقف</h3>

<p>اگر اینترنت قطع شود، کامپیوتر خاموش شود یا برنامه متوقف شود، در اجرای بعدی ابتدا داده‌ها و نقطه ذخیره‌شده بررسی می‌شوند. در صورت سالم‌بودن اطلاعات ذخیره‌شده، جمع‌آوری از همان نقطه ادامه پیدا می‌کند.</p>

<h3>🔵 فایل‌های خروجی</h3>

<p>خروجی‌ها شامل پایگاه داده، جدول نظرات، داده‌های خام، رشته‌گفت‌وگوها، نسخه متنی قابل خواندن و گزارش جمع‌آوری هستند. نام دقیق فایل‌ها در بخش <strong>Output Files</strong> مشخص شده است.</p>

<h3>🔴 محدودیت و امنیت</h3>

<p>برنامه فقط داده‌های عمومی قابل دریافت از رابط رسمی یوتیوب را جمع‌آوری می‌کند. نظرات خصوصی، حذف‌شده یا غیرفعال ممکن است قابل دریافت نباشند. همچنین کلید API را هرگز در مخزن عمومی گیت‌هاب قرار ندهید.</p>

<h3>🟣 کاربرد پژوهشی</h3>

<p>این ابزار برای جمع‌آوری داده‌های لازم در پژوهش‌های دانشگاهی، تحلیل گفت‌وگوهای آنلاین، بررسی تعامل کاربران و مطالعات رسانه‌های دیجیتال طراحی شده است.</p>

</div>

---

<div align="center">

**YouTube Comments & Replies Collector**

*Designed for structured collection and research-ready exports*

</div>
