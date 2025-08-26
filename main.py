from telegram.ext import Application, CommandHandler
from telegram import ReplyKeyboardMarkup
import datetime, threading, json, os

def get_token():
    token = os.getenv("TOKEN")
    if not token:
        try:
            with open("token.txt", "r") as f:
                token = f.read().strip()
        except Exception:
            token = None
    return token

TOKEN = get_token()
EXAMS_FILE = "exams.json"

# ---------------- Utility functions ----------------
def load_exams():
    if os.path.exists(EXAMS_FILE):
        with open(EXAMS_FILE, "r") as f:
            return json.load(f)
    return []

def save_exams(exams):
    with open(EXAMS_FILE, "w") as f:
        json.dump(exams, f, indent=4)

def schedule_message(app, chat_id, reminder_time, text):
    delay = (reminder_time - datetime.datetime.now()).total_seconds()
    if delay > 0:
        async def job():
            await app.bot.send_message(chat_id=chat_id, text=text)
        threading.Timer(delay, lambda: app.create_task(job())).start()

def schedule_exam(app, chat_id, reminder_time, message):
    # 1 day before
    schedule_message(app, chat_id, reminder_time - datetime.timedelta(days=1),
                     f"📌 Reminder: {message} is tomorrow at {reminder_time.strftime('%H:%M')}")
    # 1 hour before
    schedule_message(app, chat_id, reminder_time - datetime.timedelta(hours=1),
                     f"⏳ Reminder: {message} starts in 1 hour ({reminder_time.strftime('%H:%M')})")
    # At exact time
    schedule_message(app, chat_id, reminder_time,
                     f"🚨 Exam time! {message}")

# ---------------- Bot Commands ----------------
async def start(update, context):
    keyboard = [
        ["/addexam", "/myexams"],
        ["/deleteexam", "/nextexam"],
        ["/today"]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(
        "👋 *Hi! I’m your Exam Reminder Bot.*\n\n"
        "*Commands:*\n"
        "• `/addexam YYYY-MM-DD HH:MM Subject Room` — Add an exam\n"
        "• `/myexams` — View all your exams\n"
        "• `/deleteexam <number>` — Remove a saved exam\n"
        "• `/nextexam` — Show your closest upcoming exam\n"
        "• `/today` — Show exams happening today\n",
        parse_mode="Markdown",
        reply_markup=reply_markup
    )

async def add_exam(update, context):
    try:
        date_str, time_str, *details = context.args
        reminder_time = datetime.datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
        message = " ".join(details)

        exams = load_exams()
        exams.append({
            "chat_id": update.effective_chat.id,
            "time": reminder_time.isoformat(),
            "message": message
        })
        save_exams(exams)

        schedule_exam(context.application, update.effective_chat.id, reminder_time, message)

        await update.message.reply_text(
            f"✅ *Exam saved!*\n\n*Date:* `{reminder_time}`\n*Details:* {message}\n\n_You’ll be reminded 1 day before, 1 hour before, and at the start._",
            parse_mode="Markdown"
        )

    except Exception:
        await update.message.reply_text("⚠️ Use format:\n/addexam 2025-09-02 09:00 DataStructures RoomB")

async def my_exams(update, context):
    exams = load_exams()
    chat_exams = [e for e in exams if e["chat_id"] == update.effective_chat.id]

    if not chat_exams:
        await update.message.reply_text("📭 No exams saved yet.")
        return

    msg = "📌 *Your upcoming exams:*\n\n"
    for i, e in enumerate(chat_exams, start=1):
        reminder_time = datetime.datetime.fromisoformat(e["time"])
        msg += f"*{i}.* `{reminder_time.strftime('%Y-%m-%d %H:%M')}` — {e['message']}\n"
        msg += f"   ⏳ _Reminders:_ `{(reminder_time - datetime.timedelta(days=1)).strftime('%Y-%m-%d %H:%M')}`, "
        msg += f"`{(reminder_time - datetime.timedelta(hours=1)).strftime('%Y-%m-%d %H:%M')}`, "
        msg += f"`{reminder_time.strftime('%Y-%m-%d %H:%M')}`\n\n"

    await update.message.reply_text(msg, parse_mode="Markdown")

async def delete_exam(update, context):
    try:
        index = int(context.args[0]) - 1
        exams = load_exams()
        chat_exams = [e for e in exams if e["chat_id"] == update.effective_chat.id]

        if index < 0 or index >= len(chat_exams):
            await update.message.reply_text("⚠️ Invalid exam number. Use /myexams to see valid numbers.")
            return

        exam_to_delete = chat_exams[index]
        exams.remove(exam_to_delete)
        save_exams(exams)

        await update.message.reply_text(
            f"❌ *Deleted exam:* {exam_to_delete['message']}\n*Date:* `{datetime.datetime.fromisoformat(exam_to_delete['time']).strftime('%Y-%m-%d %H:%M')}`",
            parse_mode="Markdown"
        )
    except:
        await update.message.reply_text("⚠️ Use format: /deleteexam <number> (check with /myexams)")

async def nextexam(update, context):
    exams = load_exams()
    chat_exams = [e for e in exams if e["chat_id"] == update.effective_chat.id]

    if not chat_exams:
        await update.message.reply_text("📭 No exams saved yet.")
        return

    # Sort by soonest exam
    chat_exams.sort(key=lambda e: datetime.datetime.fromisoformat(e["time"]))
    next_exam = chat_exams[0]
    reminder_time = datetime.datetime.fromisoformat(next_exam["time"])

    msg = "🎯 *Your next exam:*\n"
    msg += f"*Subject:* {next_exam['message']}\n"
    msg += f"*Date:* `{reminder_time.strftime('%Y-%m-%d %H:%M')}`\n"
    msg += f"⏳ _Reminders:_ `{(reminder_time - datetime.timedelta(days=1)).strftime('%Y-%m-%d %H:%M')}`, "
    msg += f"`{(reminder_time - datetime.timedelta(hours=1)).strftime('%Y-%m-%d %H:%M')}`, "
    msg += f"`{reminder_time.strftime('%Y-%m-%d %H:%M')}`"

    await update.message.reply_text(msg, parse_mode="Markdown")

async def today(update, context):
    exams = load_exams()
    chat_exams = [e for e in exams if e["chat_id"] == update.effective_chat.id]

    today_date = datetime.datetime.now().date()
    today_exams = [e for e in chat_exams if datetime.datetime.fromisoformat(e["time"]).date() == today_date]

    if not today_exams:
        await update.message.reply_text("📭 No exams scheduled for today.")
        return

    msg = "📅 *Exams happening today:*\n\n"
    for e in today_exams:
        reminder_time = datetime.datetime.fromisoformat(e["time"])
        msg += f"📝 `{reminder_time.strftime('%Y-%m-%d %H:%M')}` — {e['message']}\n"
        msg += f"   ⏳ _Reminders:_ `{(reminder_time - datetime.timedelta(days=1)).strftime('%Y-%m-%d %H:%M')}`, "
        msg += f"`{(reminder_time - datetime.timedelta(hours=1)).strftime('%Y-%m-%d %H:%M')}`, "
        msg += f"`{reminder_time.strftime('%Y-%m-%d %H:%M')}`\n\n"

    await update.message.reply_text(msg, parse_mode="Markdown")

# ---------------- Main ----------------
def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("addexam", add_exam))
    app.add_handler(CommandHandler("myexams", my_exams))
    app.add_handler(CommandHandler("deleteexam", delete_exam))
    app.add_handler(CommandHandler("nextexam", nextexam))
    app.add_handler(CommandHandler("today", today))
    app.run_polling()

if __name__ == "__main__":
    main()
