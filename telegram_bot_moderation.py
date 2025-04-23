# Telegram Moderation Bot with Custom Admin Controls

from telegram import Update, ChatPermissions, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, CommandHandler, CallbackQueryHandler, filters
import re, asyncio, datetime

# إعدادات أساسية
TOKEN = "7826067736:AAFnSPsBdfxAa6IZ4eorZwM4DmtBEHou9Z8"
OWNER_ID = 6182938670  # ضع هنا معرف المالك الحقيقي
real_admins = set()  # لتخزين المشرفين المضافين يدويًا
banned_items = set()  # لتخزين الكلمات أو المحتوى الممنوع
muted_users = {}  # تخزين المستخدمين المكتومين مع انتهاء الكتم
banned_users = set()  # تخزين المستخدمين المحظورين
user_messages = {}  # لحماية السبام

# إعدادات الميديا
media_settings = {
    'media': True,
    'link': True,
    'photo': True,
    'stic': True,
    'doc': True,
    'voi': True,
    'gif': True,
}

lang_settings = {
    'arabic': True,
    'english': True
}

# التحقق من المشرف
async def is_admin(user_id, chat_id, context, check_real_admin=False):
    if user_id == OWNER_ID:
        return True
    if check_real_admin:
        return user_id in real_admins
    member = await context.bot.get_chat_member(chat_id, user_id)
    return member.status in ["administrator", "creator"]

# لوحة الأوامر
async def show_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update.effective_user.id, update.effective_chat.id, context): return
    keyboard = [
        [InlineKeyboardButton("✅ الصور", callback_data='photo'), InlineKeyboardButton("❌ الصور", callback_data='unphoto')],
        [InlineKeyboardButton("✅ الروابط", callback_data='link'), InlineKeyboardButton("❌ الروابط", callback_data='unlink')],
        [InlineKeyboardButton("✅ ملصقات", callback_data='stic'), InlineKeyboardButton("❌ ملصقات", callback_data='unstic')],
        [InlineKeyboardButton("✅ GIF", callback_data='gif'), InlineKeyboardButton("❌ GIF", callback_data='ungif')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("لوحة التحكم:", reply_markup=reply_markup)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    command = query.data
    if command.startswith('un'):
        media_settings[command[2:]] = False
        await query.edit_message_text(f"❌ تم تعطيل {command[2:]}")
    else:
        media_settings[command] = True
        await query.edit_message_text(f"✅ تم تفعيل {command}")

# عرض قائمة الأوامر
async def show_commands(update: Update, context: ContextTypes.DEFAULT_TYPE):
    commands = """
🛠️ أوامر التحكم:

/panel - عرض لوحة التحكم بالأزرار
/starta /stopa - تفعيل/تعطيل اللغة العربية
/starte /stope - تفعيل/تعطيل اللغة الإنجليزية

/mute [id] [المدة] - كتم عضو (بالرد أو المعرف)
/unmute [id] - فك الكتم

/ban [id] - حظر عضو
/unban [id] - فك الحظر

/banword [كلمة] أو بالرد - منع كلمة
/unbanword [كلمة] أو بالرد - إلغاء منع

/addadmin [id] - إضافة مشرف حقيقي
/removeadmin [id] - إزالة مشرف حقيقي

/media /unmedia - تفعيل/تعطيل الوسائط
/link /unlink - تفعيل/تعطيل الروابط
/photo /unphoto - تفعيل/تعطيل الصور
/stic /unstic - تفعيل/تعطيل الملصقات
/doc /undoc - تفعيل/تعطيل الملفات
/voi /unvoi - تفعيل/تعطيل الصوتيات
/gif /ungif - تفعيل/تعطيل GIF
"""
    await update.message.reply_text(commands)

# تفعيل / تعطيل اللغة
async def toggle_lang(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != OWNER_ID and user_id not in real_admins:
        return
    cmd = update.message.text.lower()
    if cmd == "/starta": lang_settings['arabic'] = True
    elif cmd == "/stopa": lang_settings['arabic'] = False
    elif cmd == "/starte": lang_settings['english'] = True
    elif cmd == "/stope": lang_settings['english'] = False
    await update.message.reply_text("✅ تم تحديث إعدادات اللغة")

# كتم وفك كتم مع وقت
async def mute_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update.effective_user.id, update.effective_chat.id, context): return
    user_id = update.message.reply_to_message.from_user.id if update.message.reply_to_message else int(context.args[0])
    duration = context.args[1] if len(context.args) > 1 else '1h'
    unit = duration[-1]
    amount = int(duration[:-1])
    delta = {'s': 'seconds', 'm': 'minutes', 'h': 'hours', 'd': 'days', 'w': 'weeks', 'n': 'days'}.get(unit, 'hours')
    time = datetime.datetime.now() + datetime.timedelta(**{delta: amount if unit != 'n' else amount * 30})
    muted_users[user_id] = time
    await update.message.reply_text("🚫 User has been muted")

async def unmute_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update.effective_user.id, update.effective_chat.id, context): return
    user_id = update.message.reply_to_message.from_user.id if update.message.reply_to_message else int(context.args[0])
    muted_users.pop(user_id, None)
    await update.message.reply_text("✅ User has been unmuted")

# حظر وفك حظر
async def ban_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update.effective_user.id, update.effective_chat.id, context): return
    user_id = update.message.reply_to_message.from_user.id if update.message.reply_to_message else int(context.args[0])
    banned_users.add(user_id)
    await update.message.reply_text("🚫 User has been banned")

async def unban_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update.effective_user.id, update.effective_chat.id, context): return
    user_id = update.message.reply_to_message.from_user.id if update.message.reply_to_message else int(context.args[0])
    banned_users.discard(user_id)
    await update.message.reply_text("✅ User has been unbanned")

# أوامر المشرفين الحقيقيين
async def add_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID: return
    real_admins.add(int(context.args[0]))
    await update.message.reply_text("✅ Admin added")

async def remove_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID: return
    real_admins.discard(int(context.args[0]))
    await update.message.reply_text("✅ Admin removed")

# منع/إلغاء منع محتوى
async def ban_content(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update.effective_user.id, update.effective_chat.id, context): return
    text = update.message.reply_to_message.text if update.message.reply_to_message else " ".join(context.args)
    banned_items.add(text.lower())
    await update.message.reply_text("🚫 Content banned")

async def unban_content(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update.effective_user.id, update.effective_chat.id, context): return
    text = update.message.reply_to_message.text if update.message.reply_to_message else " ".join(context.args)
    banned_items.discard(text.lower())
    await update.message.reply_text("✅ Content unbanned")

# حذف رسايل الدخول
async def delete_joins(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.new_chat_members:
        await update.message.delete()

# فحص المحتوى الممنوع وحماية من السبام
async def message_filter(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    now = datetime.datetime.now()

    if user_id in banned_users:
        await update.message.delete()
        return

    if user_id in muted_users:
        if now < muted_users[user_id]:
            await update.message.delete()
            return
        else:
            muted_users.pop(user_id)

    # حماية من السبام
    if user_id not in user_messages:
        user_messages[user_id] = []
    user_messages[user_id].append(now)
    user_messages[user_id] = [t for t in user_messages[user_id] if (now - t).seconds <= 5]
    if len(user_messages[user_id]) > 5:
        await update.message.delete()
        return

    # التحقق من المحتوى الممنوع
    text = update.message.text or ""
    for banned in banned_items:
        if banned.lower() in text.lower():
            if not await is_admin(user_id, update.effective_chat.id, context):
                await update.message.delete()
                break

    # حماية اللغة حسب الإعدادات
    if not lang_settings['arabic']:
        if re.search(r'[\u0600-\u06FF]', text):
            if not await is_admin(user_id, update.effective_chat.id, context):
                await update.message.delete()
                return

    if not lang_settings['english']:
        if re.search(r'[a-zA-Z]', text):
            if not await is_admin(user_id, update.effective_chat.id, context):
                await update.message.delete()
                return

# تنفيذ أوامر التفعيل/التعطيل للميديا
async def toggle_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update.effective_user.id, update.effective_chat.id, context): return
    command = update.message.text.replace("/", "").lower()
    if command.startswith("un"):
        media_settings[command[2:]] = False
        await update.message.reply_text(f"❌ {command[2:]} disabled")
    else:
        media_settings[command] = True
        await update.message.reply_text(f"✅ {command} enabled")

# تشغيل البوت
app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("panel", show_panel))
app.add_handler(CallbackQueryHandler(button_handler))
app.add_handler(CommandHandler("commands", show_commands))

for cmd in ["media", "unmedia", "link", "unlink", "photo", "unphoto", "stic", "unstic", "doc", "undoc", "voi", "unvoi", "gif", "ungif"]:
    app.add_handler(CommandHandler(cmd, toggle_media))

app.add_handler(CommandHandler(["starta", "stopa", "starte", "stope"], toggle_lang))
app.add_handler(CommandHandler("mute", mute_user))
app.add_handler(CommandHandler("unmute", unmute_user))
app.add_handler(CommandHandler("ban", ban_user))
app.add_handler(CommandHandler("unban", unban_user))
app.add_handler(CommandHandler("addadmin", add_admin))
app.add_handler(CommandHandler("removeadmin", remove_admin))
app.add_handler(CommandHandler("banword", ban_content))
app.add_handler(CommandHandler("unbanword", unban_content))

app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, delete_joins))
app.add_handler(MessageHandler(filters.ALL, message_filter))

print("Bot is running...")
app.run_polling()
