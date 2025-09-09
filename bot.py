import asyncio, logging, io, os, uuid
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputFile
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, CallbackQueryHandler
from game import GameSession
from render import render_frame
from db import init_db, update_score, top_n

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.environ.get("TG_BOT_TOKEN")
OWNER_ID = 8094286612  # owner only

SESSIONS = {}
CHAT_TO_SESSION = {}

async def start(update:Update, context:ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Yo! Dino Race Bot.\n/newrace, /join, /startgame, /leaderboard")

async def newrace(update:Update, context:ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id in CHAT_TO_SESSION:
        await update.message.reply_text("Already active session.")
        return
    session_id = str(uuid.uuid4())[:8]
    user = update.effective_user
    players = [(user.id, user.first_name)]
    gs = GameSession(chat_id, session_id, players)
    SESSIONS[session_id] = gs
    CHAT_TO_SESSION[chat_id] = session_id
    await update.message.reply_text(f"New race created! Session {session_id}. Creator joined. Use /join.")

async def join(update:Update, context:ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = update.effective_user
    if chat_id not in CHAT_TO_SESSION:
        await update.message.reply_text("No active session. Use /newrace.")
        return
    session_id = CHAT_TO_SESSION[chat_id]
    gs = SESSIONS[session_id]
    if any(p.user_id == user.id for p in gs.players):
        await update.message.reply_text("Already joined.")
        return
    if len(gs.players) >= 3:
        await update.message.reply_text("Session full (3).")
        return
    existing = [(p.user_id, p.username) for p in gs.players]
    existing.append((user.id, user.first_name))
    newgs = GameSession(chat_id, session_id, existing)
    SESSIONS[session_id] = newgs
    await update.message.reply_text(f"{user.first_name} joined. ({len(existing)}/3)")

async def startgame(update:Update, context:ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id not in CHAT_TO_SESSION:
        await update.message.reply_text("No session.")
        return
    session_id = CHAT_TO_SESSION[chat_id]
    gs = SESSIONS[session_id]
    gs.start()
    await update.message.reply_text("Game starting...")
    asyncio.create_task(game_loop(context, gs))

async def game_loop(context:ContextTypes.DEFAULT_TYPE, gs):
    chat_id = gs.chat_id
    tick_interval = 0.6
    while gs.running:
        info = gs.update()
        img = render_frame(info['states'], info['tick'], info['scores'], gs.obstacles)
        bio = io.BytesIO()
        img.save(bio, format="PNG")
        bio.seek(0)
        kb = []
        for i,p in enumerate(gs.players):
            kb.append([InlineKeyboardButton(f"P{i+1} Jump ({p.username})", callback_data=f"jump|{gs.session_id}|{i}")])
        kb.append([InlineKeyboardButton("End", callback_data=f"end|{gs.session_id}")])
        reply_markup = InlineKeyboardMarkup(kb)
        await context.bot.send_photo(chat_id=chat_id, photo=InputFile(bio, filename="frame.png"), caption=f"Tick {info['tick']}", reply_markup=reply_markup)
        await asyncio.sleep(tick_interval)
    if gs.winner:
        await context.bot.send_message(chat_id=chat_id, text=f"🏁 Winner: {gs.winner.username}")
        for p in gs.players:
            update_score(p.user_id, p.username, p.score)
    else:
        await context.bot.send_message(chat_id=chat_id, text="Game Over!")
    del CHAT_TO_SESSION[chat_id]
    del SESSIONS[gs.session_id]

async def callback_handler(update:Update, context:ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data.split("|")
    if data[0]=="jump":
        _, session_id, idx = data
        idx=int(idx)
        gs = SESSIONS.get(session_id)
        if not gs: return
        if query.from_user.id != gs.players[idx].user_id:
            await query.answer("Not your button", show_alert=True)
            return
        gs.jump(idx)
    elif data[0]=="end":
        _, session_id = data
        gs = SESSIONS.get(session_id)
        if gs: gs.running=False

async def leaderboard(update:Update, context:ContextTypes.DEFAULT_TYPE):
    rows = top_n(10)
    text = "🏆 Leaderboard:\n" + "\n".join([f"{i+1}. {u} — {s}" for i,(u,s) in enumerate(rows)])
    await update.message.reply_text(text or "Empty")

# --- Owner only ---
async def broadcast(update:Update, context:ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        await update.message.reply_text("Not authorized.")
        return
    msg = " ".join(context.args)
    if not msg:
        await update.message.reply_text("Usage: /broadcast <msg>")
        return
    for chat_id in list(CHAT_TO_SESSION.keys()):
        await context.bot.send_message(chat_id=chat_id, text=f"[Broadcast]: {msg}")

async def shutdown(update:Update, context:ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        await update.message.reply_text("Not authorized.")
        return
    await update.message.reply_text("Shutting down...")
    os._exit(0)

def main():
    init_db()
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("newrace", newrace))
    app.add_handler(CommandHandler("join", join))
    app.add_handler(CommandHandler("startgame", startgame))
    app.add_handler(CommandHandler("leaderboard", leaderboard))
    app.add_handler(CommandHandler("broadcast", broadcast))
    app.add_handler(CommandHandler("shutdown", shutdown))
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.run_polling()

if __name__=="__main__":
    main()
