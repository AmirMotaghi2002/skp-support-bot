import json
import logging
import os
import uuid
from datetime import datetime

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
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
DEFAULT_GROUP_CHAT_ID = None  # اگر می‌خواهید مستقیماً داخل کد وارد کنید، اینجا مقدار را قرار دهید

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

STUDENT_COURSE, STUDENT_QUESTION = range(2)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

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


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.effective_chat.type != ChatType.PRIVATE:
        return

    text = (
        "سلام! من ربات پشتیبانی دوره هستم.\n"
        "در این ربات دوره خود را انتخاب کن و سوالت را ارسال کن.\n"
        "سوال شما به گروه اساتید ارسال خواهد شد تا در صورت مرتبط بودن، پاسخ بدند.\n\n"
        "بهترین ۵ دوره برای شروع:\n"
        + "\n".join([f"- {item}" for item in BEST_5])
    )

    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(build_course_keyboard()))
    return STUDENT_COURSE


async def set_group(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_chat.type in (ChatType.GROUP, ChatType.SUPERGROUP):
        group_id = update.effective_chat.id
        state_data = load_state()
        state_data["group_chat_id"] = group_id
        save_state(state_data)
        await update.message.reply_text(
            f"گروه پشتیبانی ثبت شد. اکنون سوال‌ها به این گروه ارسال می‌شود.\nID گروه: {group_id}"
        )
    else:
        await update.message.reply_text("این دستور را داخل گروه پشتیبانی اجرا کنید.")


async def course_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    course = query.data.split(":", 1)[1]
    context.user_data["selected_course"] = course
    await query.message.edit_text(
        f"دوره انتخاب شده: {course}\n\nحالا سوال خود را تایپ و ارسال کن."
    )
    return STUDENT_QUESTION


async def receive_question(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    course = context.user_data.get("selected_course")
    question_text = update.message.text.strip()

    if not course:
        await update.message.reply_text("ابتدا باید دوره را انتخاب کنید. /start را ارسال کنید.")
        return ConversationHandler.END

    state_data = load_state()
    group_chat_id = state_data.get("group_chat_id") or DEFAULT_GROUP_CHAT_ID
    if group_chat_id is None:
        await update.message.reply_text(
            "گروه پشتیبانی تنظیم نشده است. ابتدا /setgroup را در گروه پشتیبانی اجرا کنید."
        )
        return ConversationHandler.END

    question_id = str(uuid.uuid4())
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
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
    }

    keyboard = [
        [InlineKeyboardButton("✅ پاسخ می‌دهم", callback_data=f"answer:{question_id}")],
        [InlineKeyboardButton("❌ مربوط به این دوره نیست", callback_data=f"not_related:{question_id}")],
    ]

    group_message = (
        f"سوال جدید ثبت شد:\n"
        f"👨‍🎓 دانشجو: {user.full_name}\n"
        f"📚 دوره: {course}\n"
        f"🕒 زمان: {now}\n\n"
        f"سوال: {question_text}"
    )

    try:
        msg = await context.bot.send_message(
            chat_id=group_chat_id,
            text=group_message,
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        state_data["questions"][question_id]["group_message_id"] = msg.message_id
        save_state(state_data)
        await update.message.reply_text(
            "سوال شما ثبت شد و به گروه اساتید ارسال شد. به زودی پاسخ دریافت می‌کنید."
        )
    except Exception as e:
        logger.error("خطا در ارسال سوال به گروه: %s", e)
        await update.message.reply_text(
            "ارسال سوال به گروه موفق نبود. ابتدا مطمئن شوید ربات در گروه اضافه شده و /setgroup اجرا شده است."
        )

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
            query.message.text + f"\n\n✅ این سوال توسط {teacher.full_name} انتخاب شد. لطفاً جواب را در چت خصوصی با ربات ارسال کنید."
        )

        try:
            await context.bot.send_message(
                chat_id=teacher.id,
                text=(
                    f"شما سوال را برای پاسخ انتخاب کردید:\n"
                    f"👨‍🎓 دانشجو: {question['student_name']}\n"
                    f"📚 دوره: {question['course']}\n"
                    f"سوال: {question['question']}\n\n"
                    "لطفاً پاسخ خود را هم‌اکنون در این چت ارسال کنید."
                ),
            )
        except Exception as e:
            logger.error("خطا در ارسال پیام خصوصی به استاد: %s", e)
            await query.message.reply_text(
                "خطا: ربات نمی‌تواند به استاد پیام خصوصی ارسال کند. لطفاً ابتدا ربات را در چت خصوصی استارت کنید."
            )

    elif action == "not_related":
        question["status"] = "not_related"
        save_state(state_data)

        await query.edit_message_text(
            query.message.text + "\n\n❌ این سوال توسط استاد ثبت شد که مربوط به دوره انتخاب‌شده نیست."
        )

        try:
            await context.bot.send_message(
                chat_id=question["student_id"],
                text=(
                    "سلام! یکی از اساتید اعلام کرده این سوال مربوط به دوره انتخاب‌شده نیست. "
                    "اگر می‌خواهید می‌توانید دوباره سوال خود را ارسال کنید یا دوره را تغییر دهید."
                ),
            )
        except Exception as e:
            logger.error("ارسال پیام به دانشجو هنگام not_related با خطا مواجه شد: %s", e)


async def teacher_reply(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    teacher_id = str(update.effective_user.id)
    state_data = load_state()
    pending = state_data["teacher_pending"].get(teacher_id)

    if not pending:
        await update.message.reply_text(
            "شما در حال حاضر سوالی برای پاسخ دادن ندارید. ابتدا در گروه سوال را انتخاب کنید."
        )
        return

    answer_text = update.message.text.strip()
    question = state_data["questions"].get(pending)
    if not question:
        await update.message.reply_text("سوال پیدا نشد یا قبلاً بسته شده است.")
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
        await context.bot.send_message(chat_id=question["student_id"], text=student_message)
        await update.message.reply_text("پاسخ شما با موفقیت به دانشجو ارسال شد.")
    except Exception as e:
        logger.error("ارسال پاسخ استاد به دانشجو با خطا مواجه شد: %s", e)
        await update.message.reply_text(
            "خطا در ارسال پاسخ به دانشجو رخ داد. لطفاً مطمئن شوید دانشجو ربات را استارت کرده است."
        )

    group_chat_id = state_data.get("group_chat_id") or DEFAULT_GROUP_CHAT_ID
    if group_chat_id and question.get("group_message_id"):
        try:
            await context.bot.edit_message_text(
                chat_id=group_chat_id,
                message_id=question["group_message_id"],
                text=(
                    f"{question['question']}\n\n"
                    f"✅ این سوال توسط {question['assigned_teacher_name']} پاسخ داده شد."
                ),
            )
        except Exception as e:
            logger.warning("به‌روزرسانی پیام گروه پس از پاسخ با خطا مواجه شد: %s", e)


async def unknown(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "لطفاً از دستور /start برای شروع استفاده کنید یا سوال خود را پس از انتخاب دوره ارسال کنید."
    )


def main() -> None:
    global state
    state = load_state()

    app = ApplicationBuilder().token(TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            STUDENT_COURSE: [CallbackQueryHandler(course_selected, pattern=r"^course:")],
            STUDENT_QUESTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_question)],
        },
        fallbacks=[CommandHandler("start", start)],
    )

    app.add_handler(conv_handler)
    app.add_handler(CommandHandler("setgroup", set_group))
    app.add_handler(CallbackQueryHandler(group_callback, pattern=r"^(answer|not_related):"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, teacher_reply))
    app.add_handler(MessageHandler(filters.ALL, unknown))

    logger.info("ربات شروع به کار کرد...")
    app.run_polling()


if __name__ == "__main__":
    main()
