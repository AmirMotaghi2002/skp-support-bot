import json
import logging
import os
import sys
import threading
import urllib.request
import uuid
from collections import defaultdict
from datetime import datetime, timedelta

if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.constants import ChatType
from telegram.ext import (
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

TOKEN = os.getenv("BOT_TOKEN")
STATE_FILE = "support_state.json"
MEDIA_DIR = "media"
DEFAULT_GROUP_CHAT_ID = os.environ.get("TELEGRAM_GROUP_ID")
ADMIN_IDS_RAW = os.environ.get("ADMIN_IDS", "162879965")
ADMIN_IDS = set(int(x.strip()) for x in ADMIN_IDS_RAW.split(",") if x.strip().isdigit())
REMINDER_INTERVAL_HOURS = 6

os.makedirs(MEDIA_DIR, exist_ok=True)

COURSES = [
    "نقشه خوانی", "نتظیم موتور", "پارامتر خوانی",
    "مالتی پلکس ایران خودرو", "مالتی پلکس فرانسه", "مالتی پلکس سایپا",
    "کولر و تهویه مطبوع", "استارت و دینام", "هیوندا و کیا",
    "ایسیو ۱", "ایسیو ۲", "تعمیرات نود مالتی پلکس",
    "جک و لیفان", "ریمپ با TNM", "کاربری TNM",
    "ایمو بلایزر و تعریف ریموت", "وینولز",
]

STUDENT_MAIN_KEYBOARD = ReplyKeyboardMarkup(
    [
        ["❓ سوال جدید", "📋 وضعیت سوالم"],
        ["📂 تاریخچه سوالات", "ℹ️ راهنما"],
    ],
    resize_keyboard=True,
    persistent=True,
)

MESSAGES = {
    "welcome": (
        "🔧 به ربات پشتیبانی آموزشی آکادمی SKP خوش آمدید\n\n"
        "این سامانه با هدف ارائه پشتیبانی تخصصی و پاسخگویی به سوالات کارآموزان دوره‌های آموزشی مکانیک و برق خودرو راه‌اندازی شده است.\n\n"
        "📚 نحوه استفاده از ربات:\n\n"
        "1️⃣ ابتدا شماره تلفن خود را ثبت نمایید.\n\n"
        "2️⃣ سپس دوره آموزشی مورد نظر خود را از لیست دوره‌ها انتخاب کنید.\n\n"
        "3️⃣ سوال خود را ارسال کنید. می‌توانید چند پیام، عکس، ویدیو یا ویس پشت سر هم بفرستید.\n\n"
        "4️⃣ وقتی سوال کامل شد دکمه «📨 ارسال سوال» را بزنید.\n\n"
        "5️⃣ پس از بررسی، جواب استاد از طریق همین ربات برای شما ارسال می‌شود.\n\n"
        "💡 برای دریافت پاسخ دقیق‌تر، مدل خودرو، سال ساخت، نوع سیستم و کد خطا را ذکر کنید.\n\n"
        "⏱ زمان پاسخگویی از چند دقیقه تا حداکثر ۲۴ ساعت کاری متغیر است.\n\n"
        "☎️ تلفن شرکت:\n021-63002000\n\n"
        "🌐 وب‌سایت:\nhttps://skppart.com/\n\n"
        "از اعتماد شما به آکادمی SKP سپاسگزاریم.\n\n"
    ),
    "group_set": "گروه پشتیبانی ثبت شد.\nID گروه: {group_id}",
    "setgroup_private": "این دستور را داخل گروه پشتیبانی اجرا کنید.",
    "course_selected": (
        "دوره انتخاب شده: {course}\n\n"
        "حالا سوال خود را ارسال کن.\n"
        "می‌توانی چند پیام، عکس، ویدیو یا ویس پشت سر هم بفرستی.\n"
        "وقتی تمام شد دکمه «📨 ارسال سوال» را بزن."
    ),
    "need_course": "ابتدا باید دوره را انتخاب کنید.",
    "group_not_set": "گروه پشتیبانی تنظیم نشده است. ابتدا /setgroup را در گروه اجرا کنید.",
    "question_sent": "✅ سوال شما ({count} پیام) ثبت شد و به گروه اساتید ارسال شد.",
    "question_send_failed": "ارسال سوال به گروه موفق نبود.",
    "part_received": "پیام {index} دریافت شد ✔️",
    "selected_answer": "✅ این سوال توسط {teacher} انتخاب شد. لطفاً جواب را در چت خصوصی با ربات ارسال کنید.",
    "teacher_private_question": (
        "شما سوال را برای پاسخ انتخاب کردید:\n"
        "👨‍🎓 دانشجو: {student_name}\n"
        "📚 دوره: {course}\n\n"
        "سوال در {count} پیام ارسال شده. پیام‌ها در ادامه می‌آیند.\n\n"
        "لطفاً پاسخ خود را در این چت ارسال کنید."
    ),
    "teacher_private_error": "خطا: ربات نمی‌تواند به استاد پیام خصوصی ارسال کند.",
    "not_related_post": "❌ این سوال مربوط به دوره انتخاب‌شده نیست.",
    "student_not_related": "سلام! یکی از اساتید اعلام کرده این سوال مربوط به دوره انتخاب‌شده نیست.",
    "no_pending_question": "شما در حال حاضر سوالی برای پاسخ دادن ندارید.",
    "question_not_found": "سوال پیدا نشد یا قبلاً بسته شده است.",
    "answer_sent": "پاسخ شما با موفقیت به دانشجو ارسال شد.",
    "answer_send_failed": "خطا در ارسال پاسخ به دانشجو.",
    "unknown": "از منوی پایین گزینه مورد نظر را انتخاب کنید.",
    "question_answered_group": "✅ این سوال توسط {teacher} پاسخ داده شد.",
    "ask_again_prompt": "از منوی پایین می‌توانید سوال جدید ثبت کنید.",
    "no_permission": "⛔ شما دسترسی به این دستور را ندارید.",
    "no_parts": "هنوز پیامی ارسال نکرده‌اید. ابتدا سوال خود را بنویسید.",
    "status_open": "🟡 در انتظار بررسی استاد",
    "status_assigned": "🔄 استاد در حال بررسی",
    "status_answered": "✅ پاسخ داده شده",
    "status_not_related": "❌ نامرتبط با دوره",
    "announce_prompt": "متن اطلاعیه‌ای که می‌خواهید به همه دانشجوها ارسال شود را بنویسید:",
    "announce_sent": "📢 اطلاعیه با موفقیت به {count} نفر ارسال شد.",
    "announce_cancelled": "ارسال اطلاعیه لغو شد.",
    "announce_confirm": "📢 پیش‌نمایش اطلاعیه:\n\n{text}\n\nآیا ارسال شود؟",
}

SUBMIT_QUESTION_BTN = "submit_question"
STUDENT_PHONE, STUDENT_COURSE, STUDENT_QUESTION = range(3)
ANNOUNCE_TEXT, ANNOUNCE_CONFIRM_STATE = range(3, 5)

MENU_BUTTONS = {"❓ سوال جدید", "📋 وضعیت سوالم", "📂 تاریخچه سوالات", "ℹ️ راهنما"}

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.DEBUG,
)
logger = logging.getLogger(__name__)

status = {
    "start_time": None,
    "connected": False,
    "disconnect_count": 0,
    "last_check": None,
    "last_error": None,
}


def format_timedelta(delta: timedelta) -> str:
    total_seconds = int(delta.total_seconds())
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours:
        return f"{hours}h {minutes:02d}m {seconds:02d}s"
    if minutes:
        return f"{minutes}m {seconds:02d}s"
    return f"{seconds}s"


def clear_console() -> None:
    if os.name == "nt":
        os.system("cls")
    else:
        sys.stdout.write("\033[2J\033[H")
        sys.stdout.flush()


def get_connection_status() -> tuple[bool, str | None]:
    url = f"https://api.telegram.org/bot{TOKEN}/getMe"
    try:
        with urllib.request.urlopen(url, timeout=10) as response:
            data = json.load(response)
        return bool(data.get("ok")), None
    except Exception as e:
        return False, str(e)


def display_status(final: bool = False) -> None:
    clear_console()
    now = datetime.now()
    uptime = format_timedelta(now - (status["start_time"] or now))
    print("============================================")
    print("    Telegram Support Bot - وضعیت اتصال")
    print("============================================")
    print(f"وضعیت: {'✅ متصل' if status['connected'] else '❌ قطع'}")
    print(f"زمان اجرا: {uptime}")
    print(f"تعداد قطعی‌ها: {status['disconnect_count']}")
    print(f"آخرین بررسی: {status['last_check'].strftime('%Y-%m-%d %H:%M:%S') if status['last_check'] else '-'}")
    if status["last_error"]:
        print(f"خطای آخر: {status['last_error']}")
    print("--------------------------------------------")
    print("برای توقف ربات Ctrl+C را فشار دهید.")
    if final:
        print("ربات متوقف شده است.")
    sys.stdout.flush()


def status_monitor(stop_event: threading.Event) -> None:
    while not stop_event.is_set():
        connected, error = get_connection_status()
        now = datetime.now()
        if status["start_time"] is None:
            status["start_time"] = now
        if status["connected"] and not connected:
            status["disconnect_count"] += 1
        status["connected"] = connected
        status["last_check"] = now
        status["last_error"] = error
        display_status()
        if stop_event.wait(5):
            break
    display_status(final=True)


state = {
    "group_chat_id": DEFAULT_GROUP_CHAT_ID,
    "questions": {},
    "teacher_pending": {},
}


def load_state() -> dict:
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning("بارگذاری وضعیت قبلی موفق نبود: %s", e)
    return state


def save_state(data: dict) -> None:
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error("ذخیره وضعیت با خطا مواجه شد: %s", e)


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


def build_course_keyboard() -> list:
    return [[InlineKeyboardButton(course, callback_data=f"course:{course}")] for course in COURSES]


def build_submit_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("📨 ارسال سوال", callback_data=SUBMIT_QUESTION_BTN)]])


def get_status_label(status_key: str) -> str:
    return {
        "open": MESSAGES["status_open"],
        "assigned": MESSAGES["status_assigned"],
        "answered": MESSAGES["status_answered"],
        "not_related": MESSAGES["status_not_related"],
    }.get(status_key, "نامشخص")


# ====== آمار و گزارش‌گیری ======

def compute_stats(state_data: dict) -> dict:
    questions = state_data.get("questions", {})
    by_status = defaultdict(int)
    by_course = defaultdict(int)
    by_teacher = defaultdict(lambda: {"answered": 0, "assigned": 0})
    response_times = []
    unanswered_old = []
    now = datetime.now()

    for qid, q in questions.items():
        s = q.get("status", "open")
        by_status[s] += 1
        by_course[q.get("course", "نامشخص")] += 1
        teacher = q.get("assigned_teacher_name")
        if teacher:
            by_teacher[teacher]["answered" if s == "answered" else "assigned"] += 1
        if s == "answered" and q.get("created_at") and q.get("answered_at"):
            try:
                diff = (
                    datetime.strptime(q["answered_at"], "%Y-%m-%d %H:%M:%S") -
                    datetime.strptime(q["created_at"], "%Y-%m-%d %H:%M:%S")
                ).total_seconds() / 60
                response_times.append(diff)
            except Exception:
                pass
        if s == "open" and q.get("created_at"):
            try:
                if (now - datetime.strptime(q["created_at"], "%Y-%m-%d %H:%M:%S")).total_seconds() > 86400:
                    unanswered_old.append({
                        "student": q.get("student_name", "نامشخص"),
                        "course": q.get("course", "نامشخص"),
                        "created_at": q["created_at"],
                    })
            except Exception:
                pass

    return {
        "total": len(questions),
        "by_status": dict(by_status),
        "by_course": dict(by_course),
        "by_teacher": {k: dict(v) for k, v in by_teacher.items()},
        "avg_response_minutes": sum(response_times) / len(response_times) if response_times else None,
        "unanswered_old": unanswered_old,
    }


def format_stats_message(stats: dict) -> str:
    s = stats["by_status"]
    lines = [
        "📊 *آمار کلی سیستم پشتیبانی*\n",
        f"📋 کل سوالات: *{stats['total']}*",
        f"  ✅ پاسخ داده شده: {s.get('answered', 0)}",
        f"  🔄 در انتظار پاسخ: {s.get('assigned', 0)}",
        f"  🟡 باز: {s.get('open', 0)}",
        f"  ❌ نامرتبط: {s.get('not_related', 0)}",
    ]
    if stats["avg_response_minutes"] is not None:
        avg = stats["avg_response_minutes"]
        avg_str = f"{avg:.0f} دقیقه" if avg < 60 else f"{avg/60:.1f} ساعت"
        lines.append(f"\n⏱ میانگین زمان پاسخ: *{avg_str}*")
    if stats["unanswered_old"]:
        lines.append(f"\n⚠️ سوال‌های بدون پاسخ بیش از ۲۴ ساعت: *{len(stats['unanswered_old'])}*")
    return "\n".join(lines)


def format_report_message(stats: dict) -> str:
    lines = ["📈 *گزارش تفصیلی*\n", "📚 *سوالات به تفکیک دوره:*"]
    for course, count in sorted(stats["by_course"].items(), key=lambda x: x[1], reverse=True)[:10]:
        lines.append(f"  • {course}: {count}")
    lines.append("\n👨‍🏫 *عملکرد اساتید:*")
    if stats["by_teacher"]:
        for teacher, data in sorted(stats["by_teacher"].items(), key=lambda x: x[1]["answered"], reverse=True):
            lines.append(f"  • {teacher}: {data['answered']} پاسخ / {data['assigned']} در بررسی")
    else:
        lines.append("  هنوز اطلاعاتی ثبت نشده.")
    old = stats["unanswered_old"]
    if old:
        lines.append(f"\n⚠️ *سوال‌های بدون پاسخ بیش از ۲۴ ساعت ({len(old)} مورد):*")
        for item in old[:5]:
            lines.append(f"  • {item['student']} | {item['course']} | {item['created_at']}")
        if len(old) > 5:
            lines.append(f"  ... و {len(old) - 5} مورد دیگر")
    return "\n".join(lines)


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_admin(update.effective_user.id):
        await update.message.reply_text(MESSAGES["no_permission"])
        return
    await update.message.reply_text(format_stats_message(compute_stats(load_state())), parse_mode="Markdown")


async def report_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_admin(update.effective_user.id):
        await update.message.reply_text(MESSAGES["no_permission"])
        return
    await update.message.reply_text(format_report_message(compute_stats(load_state())), parse_mode="Markdown")


async def export_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_admin(update.effective_user.id):
        await update.message.reply_text(MESSAGES["no_permission"])
        return
    state_data = load_state()
    questions = state_data.get("questions", {})
    if not questions:
        await update.message.reply_text("هنوز سوالی ثبت نشده است.")
        return
    export_data = {
        "exported_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "total_questions": len(questions),
        "questions": list(questions.values()),
    }
    export_path = os.path.join(MEDIA_DIR, f"export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
    try:
        with open(export_path, "w", encoding="utf-8") as f:
            json.dump(export_data, f, ensure_ascii=False, indent=2)
        await update.message.reply_document(
            document=open(export_path, "rb"),
            filename="questions_export.json",
            caption=f"📤 خروجی کامل سوالات\n🕒 {export_data['exported_at']}\n📋 تعداد: {len(questions)}",
        )
    except Exception as e:
        logger.error("خطا در export: %s", e)
        await update.message.reply_text(f"خطا در تهیه خروجی: {e}")


async def mystats_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    questions = load_state().get("questions", {})
    answered = [q for q in questions.values() if q.get("assigned_teacher_id") == user.id and q.get("status") == "answered"]
    assigned = [q for q in questions.values() if q.get("assigned_teacher_id") == user.id and q.get("status") == "assigned"]
    course_count = defaultdict(int)
    for q in answered:
        course_count[q.get("course", "نامشخص")] += 1
    lines = [
        f"📊 *آمار شخصی شما ({user.full_name})*\n",
        f"✅ پاسخ داده شده: {len(answered)}",
        f"🔄 در دست بررسی: {len(assigned)}",
    ]
    if course_count:
        lines.append("\n📚 دوره‌های پرتکرار:")
        for course, cnt in sorted(course_count.items(), key=lambda x: x[1], reverse=True)[:3]:
            lines.append(f"  • {course}: {cnt}")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


# ====== وضعیت سوال ======

async def mystatus_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    questions = load_state().get("questions", {})
    my_questions = sorted(
        [q for q in questions.values() if q.get("student_id") == user.id],
        key=lambda q: q.get("created_at", ""),
        reverse=True,
    )
    if not my_questions:
        await update.message.reply_text("شما هنوز سوالی ثبت نکرده‌اید.", reply_markup=STUDENT_MAIN_KEYBOARD)
        return
    lines = ["📋 *وضعیت سوالات شما (۵ سوال آخر):*\n"]
    for i, q in enumerate(my_questions[:5], 1):
        label = get_status_label(q.get("status", "open"))
        summary = q.get("question", "")[:50]
        if len(q.get("question", "")) > 50:
            summary += "..."
        lines.append(
            f"{i}. 📚 {q.get('course', '')}\n"
            f"   💬 {summary}\n"
            f"   وضعیت: {label}\n"
            f"   🕒 {q.get('created_at', '')}"
        )
        if q.get("status") == "answered" and q.get("answer"):
            ans = q["answer"][:60] + ("..." if len(q["answer"]) > 60 else "")
            lines.append(f"   ✅ پاسخ: {ans}")
        lines.append("")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown", reply_markup=STUDENT_MAIN_KEYBOARD)


# ====== تاریخچه سوالات ======

async def history_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    questions = load_state().get("questions", {})
    my_questions = sorted(
        [q for q in questions.values() if q.get("student_id") == user.id],
        key=lambda q: q.get("created_at", ""),
        reverse=True,
    )
    if not my_questions:
        await update.message.reply_text("شما هنوز سوالی ثبت نکرده‌اید.", reply_markup=STUDENT_MAIN_KEYBOARD)
        return
    total = len(my_questions)
    answered = sum(1 for q in my_questions if q.get("status") == "answered")
    open_q = sum(1 for q in my_questions if q.get("status") == "open")
    lines = [
        "📂 *تاریخچه سوالات شما*\n",
        f"📋 کل: {total} | ✅ پاسخ داده: {answered} | 🟡 در انتظار: {open_q}\n",
        "─────────────────────",
    ]
    for i, q in enumerate(my_questions[:10], 1):
        label = get_status_label(q.get("status", "open"))
        summary = q.get("question", "")[:40]
        if len(q.get("question", "")) > 40:
            summary += "..."
        teacher = q.get("assigned_teacher_name")
        lines.append(
            f"\n*{i}.* 📚 {q.get('course', '')}\n"
            f"   💬 {summary}\n"
            f"   {label}" + (f" — 👨‍🏫 {teacher}" if teacher else "") +
            f"\n   🕒 {q.get('created_at', '')}"
        )
    if total > 10:
        lines.append(f"\n_... و {total - 10} سوال قدیمی‌تر_")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown", reply_markup=STUDENT_MAIN_KEYBOARD)


# ====== منوی ثابت دانشجو ======

async def menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.message.text

    if text == "❓ سوال جدید":
        context.user_data["pending_parts"] = []
        context.user_data["submit_msg_id"] = None
        await update.message.reply_text(
            "لطفاً دوره مورد نظر را انتخاب کنید:",
            reply_markup=InlineKeyboardMarkup(build_course_keyboard()),
        )

    elif text == "📋 وضعیت سوالم":
        await mystatus_command(update, context)

    elif text == "📂 تاریخچه سوالات":
        await history_command(update, context)

    elif text == "ℹ️ راهنما":
        await update.message.reply_text(
            "📚 *راهنمای استفاده از ربات*\n\n"
            "❓ *سوال جدید* — ثبت سوال جدید\n"
            "📋 *وضعیت سوالم* — مشاهده وضعیت ۵ سوال آخر\n"
            "📂 *تاریخچه سوالات* — مشاهده همه سوالات قبلی\n\n"
            "⏱ زمان پاسخگویی تا ۲۴ ساعت کاری\n"
            "☎️ تلفن: 021-63002000\n"
            "🌐 https://skppart.com/",
            parse_mode="Markdown",
            reply_markup=STUDENT_MAIN_KEYBOARD,
        )


# ====== یادآوری به اساتید ======

async def remind_unanswered(context: ContextTypes.DEFAULT_TYPE) -> None:
    state_data = load_state()
    questions = state_data.get("questions", {})
    now = datetime.now()
    old_open = []
    for qid, q in questions.items():
        if q.get("status") == "open" and q.get("created_at"):
            try:
                created = datetime.strptime(q["created_at"], "%Y-%m-%d %H:%M:%S")
                if (now - created).total_seconds() / 3600 >= REMINDER_INTERVAL_HOURS:
                    old_open.append(q)
            except Exception:
                pass
    if not old_open:
        return
    group_chat_id = state_data.get("group_chat_id") or DEFAULT_GROUP_CHAT_ID
    if not group_chat_id:
        return
    lines = [f"⏰ *یادآوری: {len(old_open)} سوال بی‌پاسخ*\n"]
    for i, q in enumerate(old_open[:10], 1):
        try:
            hours_waiting = int((now - datetime.strptime(q["created_at"], "%Y-%m-%d %H:%M:%S")).total_seconds() / 3600)
        except Exception:
            hours_waiting = "؟"
        lines.append(
            f"{i}. 👨‍🎓 {q.get('student_name', '؟')} | "
            f"📚 {q.get('course', '؟')} | "
            f"⏱ {hours_waiting} ساعت منتظر"
        )
    if len(old_open) > 10:
        lines.append(f"\n... و {len(old_open) - 10} سوال دیگر")
    try:
        await context.bot.send_message(chat_id=group_chat_id, text="\n".join(lines), parse_mode="Markdown")
    except Exception as e:
        logger.error("خطا در ارسال یادآوری: %s", e)


# ====== اطلاعیه ======

async def announce_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not is_admin(update.effective_user.id):
        await update.message.reply_text(MESSAGES["no_permission"])
        return ConversationHandler.END
    await update.message.reply_text(MESSAGES["announce_prompt"])
    return ANNOUNCE_TEXT


async def announce_receive_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["announce_text"] = update.message.text
    await update.message.reply_text(
        MESSAGES["announce_confirm"].format(text=update.message.text),
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ بله، ارسال شود", callback_data="announce_yes"),
            InlineKeyboardButton("❌ لغو", callback_data="announce_no"),
        ]]),
        parse_mode="Markdown",
    )
    return ANNOUNCE_CONFIRM_STATE


async def announce_confirm_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    if query.data == "announce_no":
        await query.message.edit_text(MESSAGES["announce_cancelled"])
        context.user_data.pop("announce_text", None)
        return ConversationHandler.END
    text = context.user_data.pop("announce_text", None)
    if not text:
        await query.message.edit_text("خطا: متن اطلاعیه یافت نشد.")
        return ConversationHandler.END
    state_data = load_state()
    student_ids = set()
    for q in state_data.get("questions", {}).values():
        if q.get("student_id"):
            student_ids.add(q["student_id"])
    for uid in state_data.get("users", {}):
        try:
            student_ids.add(int(uid))
        except Exception:
            pass
    await query.message.edit_text(f"⏳ در حال ارسال به {len(student_ids)} نفر...")
    sent_count = 0
    for sid in student_ids:
        try:
            await context.bot.send_message(
                chat_id=sid,
                text=f"📢 *اطلاعیه آکادمی SKP*\n\n{text}",
                parse_mode="Markdown",
            )
            sent_count += 1
        except Exception as e:
            logger.warning("خطا در ارسال اطلاعیه به %s: %s", sid, e)
    await query.message.edit_text(MESSAGES["announce_sent"].format(count=sent_count))
    return ConversationHandler.END


async def announce_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(MESSAGES["announce_cancelled"])
    return ConversationHandler.END


# ====== هندلرهای اصلی ======

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.effective_chat.type != ChatType.PRIVATE:
        await update.message.reply_text("برای استفاده از ربات، لطفاً در چت خصوصی /start را ارسال کنید.")
        return ConversationHandler.END
    await update.message.reply_text(
        MESSAGES["welcome"],
        reply_markup=STUDENT_MAIN_KEYBOARD,
    )
    await update.message.reply_text(
        "برای شروع دکمه زیر را بزنید:",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("شروع ثبت درخواست", callback_data="start_register")]]),
    )
    return STUDENT_PHONE


async def set_group(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_chat.type in (ChatType.GROUP, ChatType.SUPERGROUP):
        group_id = update.effective_chat.id
        state_data = load_state()
        state_data["group_chat_id"] = group_id
        save_state(state_data)
        await update.message.reply_text(MESSAGES["group_set"].format(group_id=group_id))
    else:
        await update.message.reply_text(MESSAGES["setgroup_private"])


async def course_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    course = query.data.split(":", 1)[1]
    context.user_data["selected_course"] = course
    context.user_data["pending_parts"] = []
    context.user_data["submit_msg_id"] = None
    await query.message.edit_text(MESSAGES["course_selected"].format(course=course))
    sent = await query.message.reply_text(
        "⬇️ پیام‌های خود را ارسال کن، سپس دکمه زیر را بزن:",
        reply_markup=build_submit_keyboard(),
    )
    context.user_data["submit_msg_id"] = sent.message_id
    return STUDENT_QUESTION


async def start_register_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    kb = ReplyKeyboardMarkup(
        [[KeyboardButton("ارسال شماره", request_contact=True)]],
        one_time_keyboard=True,
        resize_keyboard=True,
    )
    try:
        await context.bot.send_message(chat_id=query.from_user.id, text="لطفاً شماره تلفن خود را ارسال کنید.", reply_markup=kb)
    except Exception:
        try:
            await query.message.edit_text("لطفاً شماره تلفن خود را ارسال کنید.")
        except Exception:
            pass
    return STUDENT_PHONE


async def receive_contact(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    phone = None
    if update.message.contact and update.message.contact.phone_number:
        phone = update.message.contact.phone_number
    elif update.message.text and any(ch.isdigit() for ch in update.message.text):
        phone = update.message.text.strip()
    if not phone:
        await update.message.reply_text("شماره تلفن نامعتبر است. لطفاً مجدداً امتحان کنید.")
        return STUDENT_PHONE
    state_data = load_state()
    users = state_data.setdefault("users", {})
    users.setdefault(str(user.id), {})["phone"] = phone
    save_state(state_data)
    context.user_data["phone"] = phone
    try:
        await context.bot.send_message(
            chat_id=user.id,
            text=f"✅ شماره شما ثبت شد: {phone}\n\nاز منوی پایین گزینه مورد نظر را انتخاب کنید:",
            reply_markup=STUDENT_MAIN_KEYBOARD,
        )
        await context.bot.send_message(
            chat_id=user.id,
            text="لطفاً دوره مورد نظر را انتخاب کنید:",
            reply_markup=InlineKeyboardMarkup(build_course_keyboard()),
        )
    except Exception:
        pass
    return STUDENT_COURSE


def _extract_part(msg) -> dict | None:
    if msg.text and msg.text not in MENU_BUTTONS:
        return {"type": "text", "text": msg.text}
    elif msg.photo:
        return {"type": "photo", "file_id": msg.photo[-1].file_id, "caption": msg.caption or ""}
    elif msg.video:
        return {"type": "video", "file_id": msg.video.file_id, "caption": msg.caption or ""}
    elif msg.voice:
        return {"type": "voice", "file_id": msg.voice.file_id, "caption": msg.caption or ""}
    elif msg.document:
        return {"type": "document", "file_id": msg.document.file_id, "caption": msg.caption or ""}
    elif msg.audio:
        return {"type": "audio", "file_id": msg.audio.file_id, "caption": msg.caption or ""}
    elif msg.animation:
        return {"type": "animation", "file_id": msg.animation.file_id, "caption": msg.caption or ""}
    return None


async def _send_part(bot, chat_id: int, part: dict, caption_prefix: str = "") -> None:
    t = part["type"]
    caption = (caption_prefix + part.get("caption", "")).strip() or None
    if t == "text":
        await bot.send_message(chat_id=chat_id, text=part["text"])
    elif t == "photo":
        await bot.send_photo(chat_id=chat_id, photo=part["file_id"], caption=caption)
    elif t == "video":
        await bot.send_video(chat_id=chat_id, video=part["file_id"], caption=caption)
    elif t == "voice":
        await bot.send_voice(chat_id=chat_id, voice=part["file_id"], caption=caption)
    elif t == "document":
        await bot.send_document(chat_id=chat_id, document=part["file_id"], caption=caption)
    elif t == "audio":
        await bot.send_audio(chat_id=chat_id, audio=part["file_id"], caption=caption)
    elif t == "animation":
        await bot.send_animation(chat_id=chat_id, animation=part["file_id"], caption=caption)


async def receive_question_part(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    msg = update.message
    if msg.text and msg.text in MENU_BUTTONS:
        await menu_handler(update, context)
        return STUDENT_QUESTION
    course = context.user_data.get("selected_course")
    if not course:
        await msg.reply_text(MESSAGES["need_course"])
        return ConversationHandler.END
    part = _extract_part(msg)
    if not part:
        await msg.reply_text("این نوع پیام پشتیبانی نمی‌شود.")
        return STUDENT_QUESTION
    parts = context.user_data.setdefault("pending_parts", [])
    parts.append(part)
    await msg.reply_text(MESSAGES["part_received"].format(index=len(parts)))
    return STUDENT_QUESTION


async def submit_question_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    user = update.effective_user
    course = context.user_data.get("selected_course")
    parts = context.user_data.get("pending_parts", [])
    if not parts:
        await query.answer(MESSAGES["no_parts"], show_alert=True)
        return STUDENT_QUESTION
    if not course:
        await query.message.reply_text(MESSAGES["need_course"])
        return ConversationHandler.END
    try:
        await query.message.edit_text("⏳ در حال ارسال سوال...")
    except Exception:
        pass
    state_data = load_state()
    group_chat_id = state_data.get("group_chat_id") or DEFAULT_GROUP_CHAT_ID
    if not group_chat_id:
        await query.message.reply_text(MESSAGES["group_not_set"])
        return ConversationHandler.END
    question_id = str(uuid.uuid4())
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    users = state_data.get("users", {})
    phone = (users.get(str(user.id)) or {}).get("phone") or context.user_data.get("phone")
    summary = next((p["text"] for p in parts if p["type"] == "text"), f"سوال در {len(parts)} پیام")
    state_data["questions"][question_id] = {
        "student_id": user.id,
        "student_name": user.full_name,
        "course": course,
        "question": summary,
        "parts": parts,
        "parts_count": len(parts),
        "status": "open",
        "created_at": now,
        "answered_at": None,
        "group_message_id": None,
        "assigned_teacher_id": None,
        "assigned_teacher_name": None,
        "answer": None,
    }
    group_header = (
        f"سوال جدید ثبت شد:\n"
        f"👨‍🎓 دانشجو: {user.full_name}\n"
        + (f"📞 {phone}\n" if phone else "")
        + f"📚 دوره: {course}\n"
        f"🕒 زمان: {now}\n"
        f"📨 تعداد پیام‌ها: {len(parts)}"
    )
    keyboard = [
        [InlineKeyboardButton("✅ پاسخ می‌دهم", callback_data=f"answer:{question_id}")],
        [InlineKeyboardButton("❌ مربوط به این دوره نیست", callback_data=f"not_related:{question_id}")],
    ]
    try:
        sent = await context.bot.send_message(
            chat_id=group_chat_id,
            text=group_header,
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        state_data["questions"][question_id]["group_message_id"] = sent.message_id
        for i, part in enumerate(parts, 1):
            try:
                await _send_part(context.bot, group_chat_id, part, caption_prefix=f"[پیام {i}/{len(parts)}] ")
            except Exception as e:
                logger.error("خطا در ارسال پارت %d به گروه: %s", i, e)
        save_state(state_data)
        context.user_data["pending_parts"] = []
        context.user_data.pop("selected_course", None)
        context.user_data["submit_msg_id"] = None
        try:
            await query.message.edit_text(MESSAGES["question_sent"].format(count=len(parts)))
        except Exception:
            pass
        try:
            await context.bot.send_message(
                chat_id=user.id,
                text=MESSAGES["ask_again_prompt"],
                reply_markup=STUDENT_MAIN_KEYBOARD,
            )
        except Exception:
            pass
    except Exception as e:
        logger.error("خطا در ارسال سوال به گروه: %s", e)
        try:
            await query.message.edit_text(MESSAGES["question_send_failed"])
        except Exception:
            pass
    return ConversationHandler.END


async def group_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    action, question_id = query.data.split(":", 1)
    state_data = load_state()
    question = state_data["questions"].get(question_id)
    if not question:
        await query.edit_message_text("این سوال قبلاً حذف یا موجود نیست.")
        return
    if question["status"] != "open":
        await query.answer("این سوال قبلاً بررسی شده است.", show_alert=True)
        return
    if action == "answer":
        teacher = update.effective_user
        question["status"] = "assigned"
        question["assigned_teacher_id"] = teacher.id
        question["assigned_teacher_name"] = teacher.full_name
        state_data["teacher_pending"][str(teacher.id)] = question_id
        save_state(state_data)
        await query.edit_message_text(query.message.text + "\n\n" + MESSAGES["selected_answer"].format(teacher=teacher.full_name))
        try:
            parts = question.get("parts", [])
            count = question.get("parts_count", len(parts))
            await context.bot.send_message(
                chat_id=teacher.id,
                text=MESSAGES["teacher_private_question"].format(
                    student_name=question["student_name"],
                    course=question["course"],
                    count=count,
                ),
            )
            for i, part in enumerate(parts, 1):
                try:
                    await _send_part(context.bot, teacher.id, part, caption_prefix=f"[پیام {i}/{count}] ")
                except Exception as e:
                    logger.error("خطا در ارسال پارت %d به استاد: %s", i, e)
        except Exception as e:
            logger.error("خطا در ارسال پیام به استاد: %s", e)
            await query.message.reply_text(MESSAGES["teacher_private_error"])
    elif action == "not_related":
        question["status"] = "not_related"
        save_state(state_data)
        await query.edit_message_text(query.message.text + "\n\n" + MESSAGES["not_related_post"])
        try:
            await context.bot.send_message(chat_id=question["student_id"], text=MESSAGES["student_not_related"])
        except Exception as e:
            logger.error("خطا در ارسال پیام not_related: %s", e)


async def teacher_reply(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    teacher_id = str(update.effective_user.id)
    state_data = load_state()
    pending = state_data["teacher_pending"].get(teacher_id)
    if not pending:
        await update.message.reply_text(MESSAGES["no_pending_question"])
        return
    msg = update.message
    part = _extract_part(msg)
    if not part:
        await msg.reply_text("لطفاً متن یا رسانه‌ای برای پاسخ ارسال کنید.")
        return
    answer_text = part.get("text") or part.get("caption") or part["type"]
    question = state_data["questions"].get(pending)
    if not question:
        await msg.reply_text(MESSAGES["question_not_found"])
        return
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    question.update({
        "status": "answered",
        "answer": answer_text,
        "answered_at": now,
        "answer_part": part,
    })
    state_data["teacher_pending"].pop(teacher_id, None)
    save_state(state_data)
    student_message = (
        f"✅ پاسخ استاد برای سوال شما:\n"
        f"📚 دوره: {question['course']}\n"
        f"👨‍🏫 استاد: {question['assigned_teacher_name']}\n\n"
        f"پاسخ: {answer_text}"
    )
    post_keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("سوالی ندارم", callback_data=f"no_more:{pending}")],
        [InlineKeyboardButton("باز سوال دارم", callback_data=f"ask_more:{pending}")],
    ])
    try:
        await context.bot.send_message(chat_id=question["student_id"], text=student_message, reply_markup=post_keyboard)
        if part["type"] != "text":
            try:
                await _send_part(context.bot, question["student_id"], part)
            except Exception as e:
                logger.error("خطا در ارسال رسانه پاسخ: %s", e)
        await msg.reply_text(MESSAGES["answer_sent"])
    except Exception as e:
        logger.error("خطا در ارسال پاسخ به دانشجو: %s", e)
        await msg.reply_text(MESSAGES["answer_send_failed"])
    group_chat_id = state_data.get("group_chat_id") or DEFAULT_GROUP_CHAT_ID
    if group_chat_id and question.get("group_message_id"):
        try:
            await context.bot.edit_message_text(
                chat_id=group_chat_id,
                message_id=question["group_message_id"],
                text=question["question"] + "\n\n" + MESSAGES["question_answered_group"].format(teacher=question["assigned_teacher_name"]),
            )
        except Exception as e:
            logger.warning("خطا در به‌روزرسانی پیام گروه: %s", e)


async def post_answer_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    action, question_id = query.data.split(":", 1)
    state_data = load_state()
    question = state_data["questions"].get(question_id)
    if not question:
        try:
            await query.edit_message_text("خطا: سوال یافت نشد.")
        except Exception:
            pass
        return ConversationHandler.END
    if action == "no_more":
        try:
            await context.bot.send_poll(
                chat_id=question["student_id"],
                question="نظرسنجی: کیفیت پاسخ پشتیبانی چگونه بود؟",
                options=["خیلی خوب", "خوب", "متوسط", "ضعیف"],
                is_anonymous=False,
            )
            await query.message.reply_text("از بازخورد شما سپاسگزاریم.")
            await context.bot.send_message(
                chat_id=question["student_id"],
                text="اگر می‌خواهید دوباره از ربات استفاده کنید:",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("استارت مجدد ربات", callback_data="restart_bot")]]),
            )
        except Exception as e:
            logger.error("خطا در ارسال نظرسنجی: %s", e)
        return ConversationHandler.END
    elif action == "ask_more":
        try:
            await context.bot.send_message(
                chat_id=question["student_id"],
                text="دوره مورد نظر رو انتخاب کنید:",
                reply_markup=InlineKeyboardMarkup(build_course_keyboard()),
            )
        except Exception:
            pass
        return STUDENT_COURSE


async def restart_bot_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    try:
        await query.message.reply_text(
            MESSAGES["welcome"],
            reply_markup=STUDENT_MAIN_KEYBOARD,
        )
        await query.message.reply_text(
            "برای شروع دکمه زیر را بزنید:",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("شروع ثبت درخواست", callback_data="start_register")]]),
        )
    except Exception:
        pass


async def unknown(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(MESSAGES["unknown"], reply_markup=STUDENT_MAIN_KEYBOARD)


def main() -> None:
    global state
    state = load_state()

    app = ApplicationBuilder().token(TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
            CallbackQueryHandler(post_answer_callback, pattern=r"^ask_more:"),
        ],
        states={
            STUDENT_PHONE: [
                CallbackQueryHandler(start_register_callback, pattern=r"^start_register$"),
                MessageHandler(filters.CONTACT | (filters.TEXT & ~filters.COMMAND), receive_contact),
            ],
            STUDENT_COURSE: [
                CallbackQueryHandler(course_selected, pattern=r"^course:"),
            ],
            STUDENT_QUESTION: [
                CallbackQueryHandler(submit_question_callback, pattern=rf"^{SUBMIT_QUESTION_BTN}$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_question_part),
                MessageHandler(filters.PHOTO, receive_question_part),
                MessageHandler(filters.VIDEO, receive_question_part),
                MessageHandler(filters.VOICE, receive_question_part),
                MessageHandler(filters.Document.ALL, receive_question_part),
                MessageHandler(filters.AUDIO, receive_question_part),
                MessageHandler(filters.ANIMATION, receive_question_part),
            ],
        },
        fallbacks=[CommandHandler("start", start)],
    )

    announce_handler = ConversationHandler(
        entry_points=[CommandHandler("announce", announce_command)],
        states={
            ANNOUNCE_TEXT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, announce_receive_text),
            ],
            ANNOUNCE_CONFIRM_STATE: [
                CallbackQueryHandler(announce_confirm_callback, pattern=r"^announce_(yes|no)$"),
            ],
        },
        fallbacks=[CommandHandler("cancel", announce_cancel)],
    )

    app.add_handler(conv_handler)
    app.add_handler(announce_handler)
    app.add_handler(CallbackQueryHandler(post_answer_callback, pattern=r"^(no_more|ask_more):"))
    app.add_handler(CallbackQueryHandler(restart_bot_callback, pattern=r"^restart_bot$"))
    app.add_handler(CommandHandler("setgroup", set_group))
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(CommandHandler("report", report_command))
    app.add_handler(CommandHandler("export", export_command))
    app.add_handler(CommandHandler("mystats", mystats_command))
    app.add_handler(CommandHandler("mystatus", mystatus_command))
    app.add_handler(CommandHandler("history", history_command))
    app.add_handler(CallbackQueryHandler(group_callback, pattern=r"^(answer|not_related):"))
    app.add_handler(CallbackQueryHandler(course_selected, pattern=r"^course:"))

    # ← منوی ثابت — باید قبل از teacher_reply باشه
    app.add_handler(MessageHandler(
        filters.TEXT & filters.Regex(r"^(❓ سوال جدید|📋 وضعیت سوالم|📂 تاریخچه سوالات|ℹ️ راهنما)$"),
        menu_handler,
    ))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, teacher_reply))
    app.add_handler(MessageHandler(filters.PHOTO, teacher_reply))
    app.add_handler(MessageHandler(filters.VIDEO, teacher_reply))
    app.add_handler(MessageHandler(filters.VOICE, teacher_reply))
    app.add_handler(MessageHandler(filters.AUDIO, teacher_reply))
    app.add_handler(MessageHandler(filters.Document.ALL, teacher_reply))
    app.add_handler(MessageHandler(filters.ANIMATION, teacher_reply))
    app.add_handler(MessageHandler(filters.ALL, unknown))

    if app.job_queue:
        app.job_queue.run_repeating(
            remind_unanswered,
            interval=timedelta(hours=REMINDER_INTERVAL_HOURS),
            first=timedelta(hours=REMINDER_INTERVAL_HOURS),
        )
    else:
        logger.warning("JobQueue فعال نیست. برای فعال‌سازی: pip install 'python-telegram-bot[job-queue]'")

    stop_event = threading.Event()
    monitor_thread = threading.Thread(target=status_monitor, args=(stop_event,), daemon=True)
    monitor_thread.start()

    logger.info("ربات شروع به کار کرد...")
    try:
        app.run_polling()
    finally:
        stop_event.set()
        monitor_thread.join(timeout=5)


if __name__ == "__main__":
    main()
