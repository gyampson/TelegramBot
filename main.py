# Unknown message handler
async def unknown(update, context):
    keyboard = [
        ["/addexam", "/newexam"],
        ["/myexams", "/deleteexam"],
        ["/nextexam", "/today"]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(
        "👋 *Hi! I’m your Exam Reminder Bot.*\n\n"
        "*Commands:*\n"
        "• `/addexam YYYY-MM-DD HH:MM Subject Room` — Add an exam (bulk)\n"
        "• `/newexam` — Add an exam (guided)\n"
        "• `/myexams` — View all your exams\n"
        "• `/deleteexam <number>` — Remove a saved exam\n"
        "• `/nextexam` — Show your closest upcoming exam\n"
        "• `/today` — Show exams happening today\n",
        parse_mode="Markdown",
        reply_markup=reply_markup
    )
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ConversationHandler, MessageHandler, filters
# --- Conversation states ---
EXAM_SUBJECT, EXAM_DATE, EXAM_TIME, EXAM_LOCATION = range(4)

# --- Guided exam addition ---
async def newexam_start(update, context):
    await update.message.reply_text("📝 Please enter the subject/course for your exam:")
    return EXAM_SUBJECT

async def newexam_subject(update, context):
    context.user_data['subject'] = update.message.text.strip()
    await update.message.reply_text("📅 Enter the exam date (e.g. 29th August 2025):")
    return EXAM_DATE

async def newexam_date(update, context):
    context.user_data['date'] = update.message.text.strip()
    await update.message.reply_text("⏰ Enter the exam time (e.g. 7:30pm):")
    return EXAM_TIME

async def newexam_time(update, context):
    context.user_data['time'] = update.message.text.strip()
    await update.message.reply_text("🏛️ Enter the location (e.g. Online, Room B):")
    return EXAM_LOCATION

async def newexam_location(update, context):
    context.user_data['location'] = update.message.text.strip()
    # Parse date and time
    import re
    from datetime import datetime
    months = {m: i+1 for i, m in enumerate(["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"])}
    date_match = re.match(r"(\d+)[a-z]* ([A-Za-z]+) (\d{4})", context.user_data['date'])
    if not date_match:
        await update.message.reply_text("⚠️ Invalid date format. Please use e.g. 29th August 2025.")
        return ConversationHandler.END
    day, month_str, year = date_match.groups()
    month = months.get(month_str)
    if not month:
        await update.message.reply_text("⚠️ Invalid month. Please use e.g. August.")
        return ConversationHandler.END
    # Parse time
    time_str = context.user_data['time'].replace(' ', '')
    try:
        if re.search(r'[AaPp][Mm]$', time_str):
            dt = datetime.strptime(f"{year} {month} {day} {time_str}", "%Y %m %d %I:%M%p")
        else:
            hour, minute = map(int, time_str.split(":"))
            dt = datetime(int(year), month, int(day), hour, minute)
    except Exception:
        await update.message.reply_text("⚠️ Invalid time format. Please use e.g. 7:30pm or 14:00.")
        return ConversationHandler.END

async def newexam_cancel(update, context):
    await update.message.reply_text("Exam creation cancelled.")
    return ConversationHandler.END
from telegram import ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
from telegram import ReplyKeyboardMarkup
import datetime, threading, json, os, asyncio

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


# Reliable reminder system: reminders are checked and sent in a background loop
REMINDER_OFFSETS = [datetime.timedelta(days=3), datetime.timedelta(days=1), datetime.timedelta(hours=1), datetime.timedelta(0)]
REMINDER_LABELS = [
    "📅 Reminder: {message} is in 3 days at {time}",
    "📌 Reminder: {message} is tomorrow at {time}",
    "⏳ Reminder: {message} starts in 1 hour ({time})",
    "🚨 Exam time! {message}"
]

def get_reminder_times(reminder_time):
    return [reminder_time - offset for offset in REMINDER_OFFSETS]

def get_reminder_texts(message, reminder_time):
    times = [reminder_time.strftime('%H:%M')] * 4
    texts = [
        REMINDER_LABELS[0].format(message=message, time=times[0]),
        REMINDER_LABELS[1].format(message=message, time=times[1]),
        REMINDER_LABELS[2].format(message=message, time=times[2]),
        REMINDER_LABELS[3].format(message=message, time=times[3]) + "\n\n_All the best in your exams!_"
    ]
    return texts

async def reminder_loop(app):
    import logging
    logging.basicConfig(level=logging.INFO)
    while True:
        exams = load_exams()
        now = datetime.datetime.now()
        changed = False
        for exam in exams:
            reminder_time = datetime.datetime.fromisoformat(exam["time"])
            chat_id = exam["chat_id"]
            message = exam["message"]
            if "sent" not in exam:
                exam["sent"] = [False, False, False, False]
            reminder_times = get_reminder_times(reminder_time)
            reminder_texts = get_reminder_texts(message, reminder_time)
            for i, (rt, txt) in enumerate(zip(reminder_times, reminder_texts)):
                if not exam["sent"][i] and rt <= now < reminder_time + datetime.timedelta(hours=1):
                    logging.info(f"Sending reminder {i} for exam '{message}' to chat {chat_id} at {now.strftime('%Y-%m-%d %H:%M:%S')}")
                    try:
                        # Extract details for UI
                        exam_time_str = reminder_time.strftime('%A, %d %B %Y at %I:%M %p')
                        mode = ''
                        if '(' in message and message.endswith(')'):
                            mode = message.split('(')[-1].rstrip(')')
                        subject = message.split('(')[0].strip() if '(' in message else message
                        # Friendly Markdown message
                        notif = (
                            f"{txt}\n\n"
                            f"*Subject:* {subject}\n"
                            f"*Date & Time:* `{exam_time_str}`\n"
                            f"*Mode:* {mode if mode else 'N/A'}\n"
                        )
                        # Inline button for details (opens external link)
                        from telegram import InlineKeyboardMarkup, InlineKeyboardButton
                        import urllib.parse
                        # Build URL with query params
                        base_url = "https://sts.ug.edu.gh/timetable/"
                        params = {
                            "subject": subject,
                            "datetime": exam_time_str,
                            "mode": mode
                        }
                        url = base_url + "?" + urllib.parse.urlencode(params)
                        keyboard = InlineKeyboardMarkup([
                            [InlineKeyboardButton("View Exam Details", url=url)]
                        ])
                        await app.bot.send_message(
                            chat_id=chat_id,
                            text=notif,
                            parse_mode="Markdown",
                            reply_markup=keyboard
                        )
                        exam["sent"][i] = True
                        changed = True
                    except Exception as e:
                        logging.error(f"Failed to send reminder: {e}")
        if changed:
            save_exams(exams)
        await asyncio.sleep(10)


# ---------------- Bot Commands ----------------
async def start(update, context):
    keyboard = [
        ["/addexam", "/newexam"],
        ["/myexams", "/deleteexam"],
        ["/nextexam", "/today"]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(
        "👋 *Hi! I’m your Exam Reminder Bot.*\n\n"
        "*Commands:*\n"
        "• `/addexam YYYY-MM-DD HH:MM Subject Room` — Add an exam (bulk)\n"
        "• `/newexam` — Add an exam (guided)\n"
        "• `/myexams` — View all your exams\n"
        "• `/deleteexam <number>` — Remove a saved exam\n"
        "• `/nextexam` — Show your closest upcoming exam\n"
        "• `/today` — Show exams happening today\n",
        parse_mode="Markdown",
        reply_markup=reply_markup
    )

async def add_exam(update, context):
    # Use full message text for bulk entry
    full_text = update.message.text
    # Remove command part
    lines = full_text.split('\n')
    # Remove the command from the first line
    if lines:
        if lines[0].startswith('/addexam'):
            lines[0] = lines[0][len('/addexam'):].strip()
    # Remove empty lines and strip
    lines = [line.strip() for line in lines if line.strip()]
    exams = load_exams()
    added, failed = [], []

    import re
    from datetime import datetime
    months = {m: i+1 for i, m in enumerate(["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"])}
    current_year = datetime.now().year

    for line in lines:
        try:
            # Custom format: subject–Month Day(th)(HH:MM[am|pm])–(Location)
            parts = [p.strip() for p in re.split(r"–", line)]
            if len(parts) < 2:
                raise ValueError("Invalid format")
            subject = parts[0]
            # Extract date and time, support AM/PM
            date_time_match = re.match(r"([A-Za-z]+) (\d+)[a-z]*\((\d{1,2}:\d{2}(?: ?[AaPp][Mm])?)\)", parts[1])
            if not date_time_match:
                raise ValueError("Invalid date/time format")
            month_str, day_str, time_str = date_time_match.groups()
            month = months.get(month_str)
            day = int(day_str)
            # Parse time with AM/PM
            time_str = time_str.replace(' ', '')
            if re.search(r'[AaPp][Mm]$', time_str):
                dt = datetime.strptime(f"{current_year} {month} {day} {time_str}", "%Y %m %d %I:%M%p")
            else:
                hour, minute = map(int, time_str.split(":"))
                dt = datetime(current_year, month, day, hour, minute)
            reminder_time = dt
            location = parts[2] if len(parts) > 2 else ""
            message = f"{subject} {location}".strip()
            exams.append({
                "chat_id": update.effective_chat.id,
                "time": reminder_time.isoformat(),
                "message": message
            })
            added.append(f"`{reminder_time}` — {message}")
        except Exception:
            failed.append(line)

    save_exams(exams)

    def pretty_date(dt):
        day = dt.day
        suffix = 'th' if 11 <= day <= 13 else {1:'st',2:'nd',3:'rd'}.get(day%10, 'th')
        return f"{day}{suffix} {dt.strftime('%B %Y')} ({dt.strftime('%I:%M %p')})"

    reply = ""
    if added:
        reply += "✅ *Exams saved:*\n"
        for exam in added:
            # exam is like '`2025-08-29 19:30:00` — 312 (Online)'
            try:
                dt_str = exam.split(' — ')[0].replace('`','').strip()
                dt = datetime.fromisoformat(dt_str)
                reply += f"{pretty_date(dt)} — {exam.split(' — ')[-1]}\n"
            except Exception:
                reply += exam + "\n"
        reply += ("\n_You’ll be reminded 3 days before, a day before, an hour before, and at the start._")
    if failed:
        reply += "\n⚠️ *Failed to add:*\n" + "\n".join(failed) + "\n_Format: 312–August 29th(7:30pm)–(Online)_"
    if not reply.strip():
        reply = "No exams were added. Please check your input format."
    await update.message.reply_text(reply, parse_mode="Markdown")

async def my_exams(update, context):
    exams = load_exams()
    chat_exams = [e for e in exams if e["chat_id"] == update.effective_chat.id]

    if not chat_exams:
        await update.message.reply_text("📭 No exams saved yet.")
        return

    msg = "📌 *Your upcoming exams:*\n\n"
    buttons = []
    def pretty_date(dt):
        day = dt.day
        suffix = 'th' if 11 <= day <= 13 else {1:'st',2:'nd',3:'rd'}.get(day%10, 'th')
        return f"{day}{suffix} {dt.strftime('%B %Y')} ({dt.strftime('%I:%M %p')})"

    for i, e in enumerate(chat_exams, start=1):
        reminder_time = datetime.datetime.fromisoformat(e["time"])
        msg += f"*{i}.* `{pretty_date(reminder_time)}` — {e['message']}\n"
        msg += f"   ⏳ _Reminders:_ `{pretty_date(reminder_time - datetime.timedelta(days=3))}`, "
        msg += f"`{pretty_date(reminder_time - datetime.timedelta(days=1))}`, "
        msg += f"`{pretty_date(reminder_time - datetime.timedelta(hours=1))}`, "
        msg += f"`{pretty_date(reminder_time)}`\n\n"
        buttons.append([InlineKeyboardButton(f"❌ Delete {i}", callback_data=f"delete_exam_{i-1}")])

    reply_markup = InlineKeyboardMarkup(buttons) if buttons else None
    # Telegram max message length is 4096 chars
    MAX_LEN = 4000
    if len(msg) <= MAX_LEN:
        await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=reply_markup)
    else:
        # Split message into chunks
        chunks = [msg[i:i+MAX_LEN] for i in range(0, len(msg), MAX_LEN)]
        # Send first chunk with buttons, rest without
        await update.message.reply_text(chunks[0], parse_mode="Markdown", reply_markup=reply_markup)
        for chunk in chunks[1:]:
            await update.message.reply_text(chunk, parse_mode="Markdown")

# Callback handler for inline delete
async def inline_delete_exam(update, context):
    query = update.callback_query
    await query.answer()
    data = query.data
    if data.startswith("delete_exam_"):
        index = int(data.split("_")[-1])
        exams = load_exams()
        chat_exams = [e for e in exams if e["chat_id"] == query.message.chat.id]
        if index < 0 or index >= len(chat_exams):
            await query.edit_message_text("⚠️ Invalid exam number. Use /myexams to see valid numbers.")
            return
        exam_to_delete = chat_exams[index]
        exams.remove(exam_to_delete)
        save_exams(exams)
        await query.edit_message_text(
            f"❌ *Deleted exam:* {exam_to_delete['message']}\n*Date:* `{datetime.datetime.fromisoformat(exam_to_delete['time']).strftime('%Y-%m-%d %H:%M')}`",
            parse_mode="Markdown"
        )
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

        reminder_time = datetime.datetime.fromisoformat(exam_to_delete['time'])
        def pretty_date(dt):
            day = dt.day
            suffix = 'th' if 11 <= day <= 13 else {1:'st',2:'nd',3:'rd'}.get(day%10, 'th')
            return f"{day}{suffix} {dt.strftime('%B %Y')} ({dt.strftime('%I:%M %p')})"
        await update.message.reply_text(
            f"❌ *Deleted exam:* {exam_to_delete['message']}\n*Date:* `{pretty_date(reminder_time)}`",
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
    def pretty_date(dt):
        day = dt.day
        suffix = 'th' if 11 <= day <= 13 else {1:'st',2:'nd',3:'rd'}.get(day%10, 'th')
        return f"{day}{suffix} {dt.strftime('%B %Y')} ({dt.strftime('%I:%M %p')})"
    msg += f"*Subject:* {next_exam['message']}\n"
    msg += f"*Date:* `{pretty_date(reminder_time)}`\n"
    msg += f"⏳ _Reminders:_ `{pretty_date(reminder_time - datetime.timedelta(days=3))}`, "
    msg += f"`{pretty_date(reminder_time - datetime.timedelta(days=1))}`, "
    msg += f"`{pretty_date(reminder_time - datetime.timedelta(hours=1))}`, "
    msg += f"`{pretty_date(reminder_time)}`"

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
    def pretty_date(dt):
        day = dt.day
        suffix = 'th' if 11 <= day <= 13 else {1:'st',2:'nd',3:'rd'}.get(day%10, 'th')
        return f"{day}{suffix} {dt.strftime('%B %Y')} ({dt.strftime('%I:%M %p')})"
    for e in today_exams:
        reminder_time = datetime.datetime.fromisoformat(e["time"])
        msg += f"📝 `{pretty_date(reminder_time)}` — {e['message']}\n"
        msg += f"   ⏳ _Reminders:_ `{pretty_date(reminder_time - datetime.timedelta(days=3))}`, "
        msg += f"`{pretty_date(reminder_time - datetime.timedelta(days=1))}`, "
        msg += f"`{pretty_date(reminder_time - datetime.timedelta(hours=1))}`, "
        msg += f"`{pretty_date(reminder_time)}`\n\n"

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
    app.add_handler(CallbackQueryHandler(inline_delete_exam))
    # Guided exam addition
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('newexam', newexam_start)],
        states={
            EXAM_SUBJECT: [MessageHandler(filters.TEXT & ~filters.COMMAND, newexam_subject)],
            EXAM_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, newexam_date)],
            EXAM_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, newexam_time)],
            EXAM_LOCATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, newexam_location)],
        },
        fallbacks=[CommandHandler('cancel', newexam_cancel)]
    )
    app.add_handler(conv_handler)
    app.add_handler(MessageHandler(filters.COMMAND | filters.TEXT, unknown))
    # Start reminder loop using Application lifecycle hooks
    reminder_task = None
    async def start_reminder(app):
        nonlocal reminder_task
        reminder_task = asyncio.create_task(reminder_loop(app))
    async def stop_reminder(app):
        if reminder_task:
            reminder_task.cancel()
            try:
                await reminder_task
            except asyncio.CancelledError:
                pass
    app.add_post_init_handler(start_reminder)
    app.add_shutdown_handler(stop_reminder)
    app.run_polling()

if __name__ == "__main__":
    main()
