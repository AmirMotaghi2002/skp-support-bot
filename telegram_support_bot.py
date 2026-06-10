import json
import logging
import os
import sys
import threading
import time
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timedelta

# Fix UTF-8 encoding for Windows console
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

# ====== تنظیمات اولیه ======
TOKEN = os.getenv("BOT_TOKEN")
STATE_FILE = "support_state.json"
MEDIA_DIR = "media"  # پوشه برای ذخیره فایل‌های رسانه‌ای
DEFAULT_GROUP_CHAT_ID = os.environ.get(
    "TELEGRAM_GROUP_ID"
)

# ایجاد پوشه رسانه اگر وجود ندارد
os.makedirs(MEDIA_DIR, exist_ok=True)

COURSES = [
    "نقشه خوانی",
    "نتظیم موتور",
    "پارامتر خوانی",
    "مالتی پلکس ایران خودرو",
    "مالتی پلکس فرانسه",
    "مالتی پلکس سایپا",
    "کولر و تهویه مطبوع",
    "استارت و دینام",
    "هیوندا و کیا",
    "ایسیو ۱",
    "ایسیو ۲",
    "تعمیرات نود مالتی پلکس",
    "جک و لیفان",
    "ریمپ با TNM",
    "کاربری TNM",
    "ایمو بلایزر و تعریف ریموت",
    "وینولز",
]

BEST_5 = [
    "نقشه خوانی",
    "کولر و تهویه مطبوع",
    "استارت و دینام",
    "مالتی پلکس ایران خودرو",
    "ایمو بلایزر و تعریف ریموت",
]

MESSAGES = {
    "welcome": (
        "🔧 به ربات پشتیبانی آموزشی آکادمی SKP خوش آمدید\n\n"
        "این سامانه با هدف ارائه پشتیبانی تخصصی و پاسخگویی به سوالات کارآموزان دوره‌های آموزشی مکانیک و برق خودرو راه‌اندازی شده است.\n\n"
        "📚 نحوه استفاده از ربات:\n\n"
        "1️⃣ ابتدا شماره تلفن خود را ثبت نمایید.\n\n"
        "2️⃣ سپس دوره آموزشی مورد نظر خود را از لیست دوره‌ها انتخاب کنید.\n\n"
        "3️⃣ سوال فنی، آموزشی یا تخصصی خود را به صورت کامل و دقیق ارسال نمایید.\n"
        "   (می‌توانید متن، عکس، ویدیو یا ویس ارسال کنید)\n\n"
        "4️⃣ سوال شما برای استاد مربوطه ارسال خواهد شد.\n\n"
        "5️⃣ پس از بررسی و پاسخگویی، جواب استاد از طریق همین ربات برای شما ارسال می‌شود.\n\n"
        "💡 برای دریافت پاسخ دقیق‌تر، لطفاً هنگام ثبت سوال مواردی مانند مدل خودرو، سال ساخت، نوع سیستم، کد خطا (در صورت وجود) و توضیحات کامل مشکل را ذکر نمایید.\n\n"
        "⏱ زمان پاسخگویی بسته به نوع سوال، حجم درخواست‌ها و زمان حضور اساتید ممکن است از چند دقیقه تا حداکثر ۲۴ ساعت کاری متغیر باشد.\n\n"
        "☎️ تلفن شرکت:\n021-63002000\n\n"
        "🌐 وب‌سایت:\nhttps://skppart.com/\n\n"
        "از اعتماد شما به آکادمی SKP سپاسگزاریم و امیدواریم این سامانه تجربه‌ای سریع، تخصصی و کاربردی برای شما فراهم کند.\n\n"
    ),
    "group_set": "گروه پشتیبانی ثبت شد. اکنون سوال‌ها به این گروه ارسال می‌شود.\nID گروه: {group_id}",
    "setgroup_private": "این دستور را داخل گروه پشتیبانی اجرا کنید.",
    "course_selected": "دوره انتخاب شده: {course}\n\nحالا سوال خود را ارسال کن (متن، عکس، ویدیو یا ویس).",
    "need_course": "ابتدا باید دوره را انتخاب کنید. /start را ارسال کنید.",
    "group_not_set": "گروه پشتیبانی تنظیم نشده است. ابتدا /setgroup را در گروه پشتیبانی اجرا کنید.",
    "question_sent": "سوال شما ثبت شد و به گروه اساتید ارسال شد. به زودی پاسخ دریافت می‌کنید.",
    "question_send_failed": "ارسال سوال به گروه موفق نبود. ابتدا مطمئن شوید ربات در گروه اضافه شده و /setgroup اجرا شده است.",
    "selected_answer": "✅ این سوال توسط {teacher} انتخاب شد. لطفاً جواب را در چت خصوصی با ربات ارسال کنید.",
    "teacher_private_question": (
        "شما سوال را برای پاسخ انتخاب کردید:\n"
        "👨‍🎓 دانشجو: {student_name}\n"
        "📚 دوره: {course}\n"
        "سوال: {question}\n\n"
        "لطفاً پاسخ خود را هم‌اکنون در این چت ارسال کنید."
    ),
    "teacher_private_error": "خطا: ربات نمی‌تواند به استاد پیام خصوصی ارسال کند. لطفاً ابتدا ربات را در چت خصوصی استارت کنید.",
    "not_related_post": "❌ این سوال توسط استاد ثبت شد که مربوط به دوره انتخاب‌شده نیست.",
    "student_not_related": (
        "سلام! یکی از اساتید اعلام کرده این سوال مربوط به دوره انتخاب‌شده نیست. "
        "اگر می‌خواهید می‌توانید دوباره سوال خود را ارسال کنید یا دوره را تغییر دهید."
    ),
    "no_pending_question": "شما در حال حاضر سوالی برای پاسخ دادن ندارید. ابتدا در گروه سوال را انتخاب کنید.",
    "question_not_found": "سوال پیدا نشد یا قبلاً بسته شده است.",
    "answer_sent": "پاسخ شما با موفقیت به دانشجو ارسال شد.",
    "answer_send_failed": "خطا در ارسال پاسخ به دانشجو رخ داد. لطفاً مطمئن شوید دانشجو ربات را استارت کرده است.",
    "unknown": "لطفاً از دستور /start برای شروع استفاده کنید یا سوال خود را پس از انتخاب دوره ارسال کنید.",
    "new_question_title": "سوال جدید ثبت شد:",
    "question_answered_group": "✅ این سوال توسط {teacher} پاسخ داده شد.",
    "ask_again_button": "ارسال سوال جدید",
    "ask_again_prompt": "در صورت داشتن سوال مجدد، دوره خود را انتخاب کنید یا سوال را ارسال کنید.",
}

STUDENT_PHONE, STUDENT_COURSE, STUDENT_QUESTION = range(3)

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
    start_time = status["start_time"] or now
    uptime = format_timedelta(now - start_time)
    connection_text = "✅ متصل" if status["connected"] else "❌ قطع"
    print("============================================")
    print("    Telegram Support Bot - وضعیت اتصال")
    print("============================================")
    print(f"وضعیت: {connection_text}")
    print(f"زمان اجرا: {uptime}")
    print(f"تعداد قطعی‌ها: {status['disconnect_count']}")
    print(f"آخرین بررسی: {status['last_check'].strftime('%Y-%m-%d %H:%M:%S') if status['last_check'] else '-'}")
    if status["last_error"]:
        print(f"خطای آخر: {status['last_error']}")
    print("--------------------------------------------")
    print("برای توقف ربات Ctrl+C را فشار دهید.")
    if final:
        print("ربات متوقف شده است یا اتصال قطع است.")
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
                data = json.load(f)
            logger.info("وضعیت قبلی بارگذاری شد.")
            return data
        except Exception as e:
            logger.warning("بارگذاری وضعیت قبلی موفق نبود: %s", e)
    return state


def save_state(data: dict) -> None:
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error("ذخیره وضعیت با خطا مواجه شد: %s", e)


def build_course_keyboard() -> list:
    buttons = []
    for course in COURSES:
        buttons.append([InlineKeyboardButton(course, callback_data=f"course:{course}")])
    return buttons


async def download_media(context: ContextTypes.DEFAULT_TYPE, file_id: str, media_type: str) -> str:
    """دانلود فایل رسانه‌ای و ذخیره آن"""
    try:
        file = await context.bot.get_file(file_id)
        file_path = os.path.join(MEDIA_DIR, f"{uuid.uuid4()}_{media_type}")
        await file.download_to_drive(file_path)
        return file_path
    except Exception as e:
        logger.error("خطا در دانلود فایل: %s", e)
        return None


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.effective_chat.type != ChatType.PRIVATE:
        await update.message.reply_text(
            "برای استفاده از ربات پشتیبانی، لطفاً در چت خصوصی با من /start را ارسال کنید."
        )
        return ConversationHandler.END

    logger.info("Received /start from user %s (%s)", update.effective_user.id if update.effective_user else None, update.effective_user.full_name if update.effective_user else None)
    text = MESSAGES["welcome"]
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("شروع ثبت درخواست", callback_data="start_register")]])
    await update.message.reply_text(text, reply_markup=keyboard)
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
    await query.message.edit_text(MESSAGES["course_selected"].format(course=course))
    return STUDENT_QUESTION


async def ask_again_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    context.user_data.pop("selected_course", None)
    try:
        await context.bot.send_message(
            chat_id=query.from_user.id,
            text=MESSAGES["ask_again_prompt"],
            reply_markup=InlineKeyboardMarkup(build_course_keyboard()),
        )
    except Exception:
        try:
            await query.message.edit_text(MESSAGES["ask_again_prompt"], reply_markup=InlineKeyboardMarkup(build_course_keyboard()))
        except Exception:
            pass
    return STUDENT_COURSE


async def start_register_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    logger.info("start_register pressed by %s", query.from_user.id if query.from_user else None)
    kb = ReplyKeyboardMarkup([[KeyboardButton("ارسال شماره", request_contact=True)]], one_time_keyboard=True, resize_keyboard=True)
    try:
        await context.bot.send_message(chat_id=query.from_user.id, text="لطفاً شماره تلفن خود را ارسال کنید (ارسال از طریق دکمه یا تایپ شماره).", reply_markup=kb)
    except Exception:
        try:
            await query.message.edit_text("لطفاً شماره تلفن خود را ارسال کنید (ارسال از طریق دکمه یا تایپ شماره).")
        except Exception:
            pass
    return STUDENT_PHONE


async def receive_contact(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    phone = None
    logger.info("receive_contact invoked by %s", user.id if user else None)
    if update.message.contact and update.message.contact.phone_number:
        phone = update.message.contact.phone_number
    elif update.message.text:
        txt = update.message.text.strip()
        if any(ch.isdigit() for ch in txt):
            phone = txt

    if not phone:
        await update.message.reply_text("شماره تلفن نامعتبر است. لطفاً مجدداً امتحان کنید.")
        return STUDENT_PHONE

    state_data = load_state()
    users = state_data.get("users") or {}
    users[str(user.id)] = users.get(str(user.id), {})
    users[str(user.id)]["phone"] = phone
    state_data["users"] = users
    save_state(state_data)

    context.user_data["phone"] = phone
    try:
        await context.bot.send_message(chat_id=user.id, text=f"شماره شما ثبت شد: {phone}", reply_markup=ReplyKeyboardRemove())
        await context.bot.send_message(chat_id=user.id, text="لطفاً دوره مورد نظر را انتخاب کنید:", reply_markup=InlineKeyboardMarkup(build_course_keyboard()))
    except Exception:
        pass

    return STUDENT_COURSE


async def receive_question(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    course = context.user_data.get("selected_course")
    logger.info("receive_question from %s, course=%s", user.id if user else None, course)
    
    # متغیرها برای نوع رسانه
    question_text = None
    media_file_id = None
    media_type = None
    
    # چک کردن نوع پیام
    if update.message.text:
        question_text = update.message.text.strip()
    elif update.message.photo:
        question_text = update.message.caption or "عکس ارسال شده"
        media_file_id = update.message.photo[-1].file_id
        media_type = "photo"
    elif update.message.video:
        question_text = update.message.caption or "ویدیو ارسال شده"
        media_file_id = update.message.video.file_id
        media_type = "video"
    elif update.message.voice:
        question_text = update.message.caption or "ویس ارسال شده"
        media_file_id = update.message.voice.file_id
        media_type = "voice"
    elif update.message.document:
        question_text = update.message.caption or "فایل ارسال شده"
        media_file_id = update.message.document.file_id
        media_type = "document"
    else:
        await update.message.reply_text("لطفاً متن، عکس، ویدیو یا ویس ارسال کنید.")
        return STUDENT_QUESTION

    if not course:
        await update.message.reply_text(MESSAGES["need_course"])
        return ConversationHandler.END

    state_data = load_state()
    group_chat_id = state_data.get("group_chat_id") or DEFAULT_GROUP_CHAT_ID
    if group_chat_id is None:
        await update.message.reply_text(MESSAGES["group_not_set"])
        return ConversationHandler.END

    question_id = str(uuid.uuid4())
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # دانلود رسانه اگر موجود باشد
    local_media_path = None
    if media_file_id:
        local_media_path = await download_media(context, media_file_id, media_type)
    
    state_data["questions"][question_id] = {
        "student_id": user.id,
        "student_name": user.full_name,
        "course": course,
        "question": question_text,
        "status": "open",
        "created_at": now,
        "group_message_id": None,
        "assigned_teacher_id": None,
        "assigned_teacher_name": None,
        "answer": None,
        "media_file_id": media_file_id,
        "media_type": media_type,
        "local_media_path": local_media_path,
    }

    keyboard = [
        [InlineKeyboardButton("✅ پاسخ می‌دهم", callback_data=f"answer:{question_id}")],
        [InlineKeyboardButton("❌ مربوط به این دوره نیست", callback_data=f"not_related:{question_id}")],
    ]

    phone = None
    users = state_data.get("users") or {}
    if users.get(str(user.id)) and users.get(str(user.id)).get("phone"):
        phone = users.get(str(user.id))["phone"]
    elif context.user_data.get("phone"):
        phone = context.user_data.get("phone")

    group_message = (
        f"سوال جدید ثبت شد:\n"
        f"👨‍🎓 دانشجو: {user.full_name}\n"
        + (f"📞 {phone}\n" if phone else "")
        + f"📚 دوره: {course}\n"
        f"🕒 زمان: {now}\n\n"
        f"سوال: {question_text}"
    )

    try:
        # ارسال پیام متنی و سپس رسانه
        msg = await context.bot.send_message(
            chat_id=group_chat_id,
            text=group_message,
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        state_data["questions"][question_id]["group_message_id"] = msg.message_id
        
        # اگر رسانه وجود دارد، آن را هم ارسال کن
        if media_file_id and media_type:
            try:
                if media_type == "photo":
                    await context.bot.send_photo(chat_id=group_chat_id, photo=media_file_id, caption="📷 عکس مربوط به سوال")
                elif media_type == "video":
                    await context.bot.send_video(chat_id=group_chat_id, video=media_file_id, caption="🎥 ویدیو مربوط به سوال")
                elif media_type == "voice":
                    await context.bot.send_voice(chat_id=group_chat_id, voice=media_file_id, caption="🎙️ ویس مربوط به سوال")
                elif media_type == "document":
                    await context.bot.send_document(chat_id=group_chat_id, document=media_file_id, caption="📎 فایل مربوط به سوال")
            except Exception as e:
                logger.error("خطا در ارسال رسانه به گروه: %s", e)
        
        save_state(state_data)
        await update.message.reply_text(MESSAGES["question_sent"])

        try:
            await context.bot.send_message(
                chat_id=user.id,
                text=MESSAGES["ask_again_prompt"],
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton(MESSAGES["ask_again_button"], callback_data="ask_again")]]
                ),
            )
        except Exception:
            pass

    except Exception as e:
        logger.error("خطا در ارسال سوال به گروه: %s", e)
        await update.message.reply_text(MESSAGES["question_send_failed"])

    return ConversationHandler.END


async def group_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    data = query.data.split(":", 1)
    action = data[0]
    question_id = data[1]
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

        await query.edit_message_text(
            query.message.text + "\n\n" + MESSAGES["selected_answer"].format(teacher=teacher.full_name)
        )

        try:
            await context.bot.send_message(
                chat_id=teacher.id,
                text=MESSAGES["teacher_private_question"].format(
                    student_name=question["student_name"],
                    course=question["course"],
                    question=question["question"],
                ),
            )
            
            # ارسال رسانه به استاد اگر موجود باشد
            if question.get("media_file_id") and question.get("media_type"):
                try:
                    media_type = question["media_type"]
                    media_file_id = question["media_file_id"]
                    
                    if media_type == "photo":
                        await context.bot.send_photo(chat_id=teacher.id, photo=media_file_id, caption="📷 عکس سوال")
                    elif media_type == "video":
                        await context.bot.send_video(chat_id=teacher.id, video=media_file_id, caption="🎥 ویدیو سوال")
                    elif media_type == "voice":
                        await context.bot.send_voice(chat_id=teacher.id, voice=media_file_id, caption="🎙️ ویس سوال")
                    elif media_type == "document":
                        await context.bot.send_document(chat_id=teacher.id, document=media_file_id, caption="📎 فایل سوال")
                except Exception as e:
                    logger.error("خطا در ارسال رسانه به استاد: %s", e)
                    
        except Exception as e:
            logger.error("خطا در ارسال پیام خصوصی به استاد: %s", e)
            await query.message.reply_text(MESSAGES["teacher_private_error"])

    elif action == "not_related":
        question["status"] = "not_related"
        save_state(state_data)

        await query.edit_message_text(
            query.message.text + "\n\n" + MESSAGES["not_related_post"]
        )

        try:
            await context.bot.send_message(
                chat_id=question["student_id"],
                text=MESSAGES["student_not_related"],
            )
        except Exception as e:
            logger.error("ارسال پیام به دانشجو هنگام not_related با خطا مواجه شد: %s", e)


async def teacher_reply(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    teacher_id = str(update.effective_user.id)
    state_data = load_state()
    pending = state_data["teacher_pending"].get(teacher_id)

    if not pending:
        await update.message.reply_text(MESSAGES["no_pending_question"])
        return

    answer_text = update.message.text.strip()
    question = state_data["questions"].get(pending)
    if not question:
        await update.message.reply_text(MESSAGES["question_not_found"])
        return

    question["status"] = "answered"
    question["answer"] = answer_text
    state_data["teacher_pending"].pop(teacher_id, None)
    save_state(state_data)

    student_message = (
        f"✅ پاسخ استاد برای سوال شما:\n"
        f"📚 دوره: {question['course']}\n"
        f"👨‍🏫 استاد: {question['assigned_teacher_name']}\n\n"
        f"پاسخ: {answer_text}"
    )

    try:
        post_keyboard = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("سوالی ندارم", callback_data=f"no_more:{pending}")],
                [InlineKeyboardButton("باز سوال دارم", callback_data=f"ask_more:{pending}")],
            ]
        )
        await context.bot.send_message(chat_id=question["student_id"], text=student_message, reply_markup=post_keyboard)
        await update.message.reply_text(MESSAGES["answer_sent"])
    except Exception as e:
        logger.error("ارسال پاسخ استاد به دانشجو با خطا مواجه شد: %s", e)
        await update.message.reply_text(MESSAGES["answer_send_failed"])

    group_chat_id = state_data.get("group_chat_id") or DEFAULT_GROUP_CHAT_ID
    if group_chat_id and question.get("group_message_id"):
        try:
            await context.bot.edit_message_text(
                chat_id=group_chat_id,
                message_id=question["group_message_id"],
                text=(
                    f"{question['question']}\n\n"
                    + MESSAGES["question_answered_group"].format(teacher=question["assigned_teacher_name"])
                ),
            )
        except Exception as e:
            logger.warning("به‌روزرسانی پیام گروه پس از پاسخ با خطا مواجه شد: %s", e)


async def post_answer_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    data = query.data.split(":", 1)
    action = data[0]
    question_id = data[1]
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
                text="اگر می‌خواهید دوباره از ربات استفاده کنید، دکمه زیر را بزنید:",
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton("استارت مجدد ربات", callback_data="restart_bot")]]
                ),
            )
        except Exception as e:
            logger.error("خطا در ارسال نظرسنجی: %s", e)
        return ConversationHandler.END
    elif action == "ask_more":
        try:
            await context.bot.send_message(chat_id=question["student_id"], text="دوره مورد نظر رو انتخاب کنید:", reply_markup=InlineKeyboardMarkup(build_course_keyboard()))
        except Exception:
            pass
        return STUDENT_COURSE


async def restart_bot_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    try:
        await query.message.reply_text(
            MESSAGES["welcome"],
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("شروع ثبت درخواست", callback_data="start_register")]]
            ),
        )
    except Exception:
        pass


async def unknown(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(MESSAGES["unknown"])


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
            STUDENT_COURSE: [CallbackQueryHandler(course_selected, pattern=r"^course:")],
            STUDENT_QUESTION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_question),
            ],
        },
        fallbacks=[CommandHandler("start", start)],
    )


    app.add_handler(conv_handler)
    app.add_handler(CallbackQueryHandler(post_answer_callback, pattern=r"^(no_more|ask_more):"))
    app.add_handler(CallbackQueryHandler(restart_bot_callback, pattern=r"^restart_bot$"))
    app.add_handler(CommandHandler("setgroup", set_group))
    app.add_handler(CallbackQueryHandler(group_callback, pattern=r"^(answer|not_related):"))
    app.add_handler(CallbackQueryHandler(course_selected, pattern=r"^course:"))
    app.add_handler(CallbackQueryHandler(ask_again_callback, pattern=r"^ask_again$"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, teacher_reply))
    app.add_handler(MessageHandler(filters.ALL, unknown))

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
