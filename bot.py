# bot.py
import os
import io
import asyncio
import logging
from uuid import uuid4

from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup, InputFile
)
from telegram.ext import (
    ApplicationBuilder, ContextTypes, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters
)

from game import GameSession
from render import render_frame
from db import init_db, add_chat, update_score, top_n, get_all_chats

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.environ.get("TG_BOT_TOKEN")  # set this in Render / env
OWNER_ID = 8094286612  # owner you provided

# sessions
SESSIONS = {}           # session_id -> GameSession
CHAT_TO_SESSION = {}    # chat_id -> session_id
RUNNING_TASKS = {}      # session_id -> asyncio.Task
PENDING_PODCAST = {}    # owner_id -> caption (waiting for media)
STOPPING = False

# helper decorator
def owner_only(func):
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        uid = user.id if user else None
        if uid != OWNER_ID:
            # respond politely
            if update.message:
                await update.message.reply_text("❌ Owner-only command.")
            elif update.callback_query:
                await update.callback_query.answer("Owner-only.", show_alert=True)
            return
        return await func(update, context)
    return wrapper

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    add_chat(update.effective_chat.id, update.effective_chat.title or "")
    await update.message.reply_text(
        "Hey! I'm DinoRace Bot.\nCommands:\n/newrace - create a race\n/join - join created race\n/startgame - start the race (creator)\n/leaderboard - top scores\n/leave - leave the race\n/status - show session status\n\nOwner-only (you): /broadcast <text>, /podcast (send audio next), /shutdown"
    )

async def newrace(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = update.effective_user
    add_chat(chat_id, update.effective_chat.title or "")
    if chat_id in CHAT_TO_SESSION:
        await update.message.reply_text("Ek session already active in this chat. Use /status or wait for it to end.")
        return
    session_id = str(uuid4())[:8]
    gs = GameSession(chat_id, session_id, [(user.id, user.first_name)])
    SESSIONS[session_id] = gs
    CHAT_TO_SESSION[chat_id] = session_id
    await update.message.reply_text(f"New race `{session_id}` created by {user.first_name}. Others use /join to join. Creator use /startgame when ready.", parse_mode="Markdown")

async def join(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = update.effective_user
    add_chat(chat_id, update.effective_chat.title or "")
    if chat_id not in CHAT_TO_SESSION:
        await update.message.reply_text("Koi active session nahi hai. Pehle /newrace kro.")
        return
    session_id = CHAT_TO_SESSION[chat_id]
    gs = SESSIONS.get(session_id)
    if not gs:
        await update.message.reply_text("Session invalid. Try /newrace.")
        return
    ok, reason = gs.add_player(user.id, user.first_name)
    if not ok:
        if reason == "already":
            await update.message.reply_text("Tu already join kar chuka hai.")
        elif reason == "full":
            await update.message.reply_text("Session full (3 players).")
        else:
            await update.message.reply_text("Cannot join: " + str(reason))
        return
    await update.message.reply_text(f"{user.first_name} joined the race. ({len(gs.players)}/{gs.max_players})")

async def leave(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = update.effective_user
    if chat_id not in CHAT_TO_SESSION:
        await update.message.reply_text("Koi active session nahi hai.")
        return
    session_id = CHAT_TO_SESSION[chat_id]
    gs = SESSIONS.get(session_id)
    if not gs:
        await update.message.reply_text("Session invalid.")
        return
    removed = gs.remove_player(user.id)
    if removed:
        await update.message.reply_text("Tu race se nikal gaya.")
    else:
        await update.message.reply_text("Tu race me hi nahi tha.")

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id not in CHAT_TO_SESSION:
        await update.message.reply_text("No active session here.")
        return
    session_id = CHAT_TO_SESSION[chat_id]
    gs = SESSIONS.get(session_id)
    if not gs:
        await update.message.reply_text("Session invalid.")
        return
    text = f"Session `{session_id}`\nPlayers:\n"
    for i,p in enumerate(gs.players, start=1):
        text += f"{i}. {p.username} — {'Alive' if p.alive else 'Dead'} — score {p.score}\n"
    await update.message.reply_text(text, parse_mode="Markdown")

async def startgame(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = update.effective_user
    if chat_id not in CHAT_TO_SESSION:
        await update.message.reply_text("Koi active session. /newrace kro.")
        return
    session_id = CHAT_TO_SESSION[chat_id]
    gs = SESSIONS.get(session_id)
    if not gs:
        await update.message.reply_text("Session invalid.")
        return
    # only creator or owner may start
    if user.id != gs.creator_id and user.id != OWNER_ID:
        await update.message.reply_text("Sirf session creator start kar sakta hai.")
        return
    if gs.running:
        await update.message.reply_text("Game already running.")
        return
    gs.start()
    await update.message.reply_text("Game starting! Buttons will appear under frames. Jump button only works for assigned player.")
    # start loop task
    task = asyncio.create_task(game_loop(context, gs))
    RUNNING_TASKS[gs.session_id] = task

async def game_loop(context: ContextTypes.DEFAULT_TYPE, gs: GameSession):
    chat_id = gs.chat_id
    tick_interval = 0.7  # seconds, tune for rate limiting / feel
    logger.info(f"Starting loop for session {gs.session_id}")
    try:
        while gs.running and not STOPPING:
            info = gs.update()
            img = render_frame(info['states'], info['obstacles'], info['tick'], gs.finish_x)
            bio = io.BytesIO()
            img.save(bio, format="PNG")
            bio.seek(0)

            # prepare buttons — one jump button per player
            kb = []
            for i, p in enumerate(gs.players):
                kb.append([InlineKeyboardButton(f"Jump — P{i+1} ({p.username})", callback_data=f"jump|{gs.session_id}|{i}")])
            # end early button (only creator or owner)
            kb.append([InlineKeyboardButton("End Early", callback_data=f"end|{gs.session_id}")])
            reply_markup = InlineKeyboardMarkup(kb)

            try:
                await context.bot.send_photo(chat_id=chat_id, photo=InputFile(bio, filename="frame.png"),
                                             caption=f"Tick {info['tick']}", reply_markup=reply_markup)
            except Exception as e:
                logger.exception("Failed to send frame: %s", e)

            await asyncio.sleep(tick_interval)

        # finished
        if gs.winner:
            text = f"🏁 Winner: {gs.winner}!"
        else:
            # maybe list survivors with highest score
            best = sorted(gs.players, key=lambda p: p.score, reverse=True)
            if best and best[0].score > 0:
                text = f"Game over. Top: {best[0].username} — {best[0].score}"
            else:
                text = "Game over. No winners."

        await context.bot.send_message(chat_id=chat_id, text=text)

        # update leaderboard
        for p in gs.players:
            try:
                update_score(p.user_id, p.username, p.score)
            except Exception:
                logger.exception("Failed DB update")

    except asyncio.CancelledError:
        logger.info("Game loop cancelled for session %s", gs.session_id)
    except Exception:
        logger.exception("Game loop error")
    finally:
        # cleanup
        try:
            if chat_id in CHAT_TO_SESSION:
                del CHAT_TO_SESSION[chat_id]
        except:
            pass
        try:
            del SESSIONS[gs.session_id]
        except:
            pass
        RUNNING_TASKS.pop(gs.session_id, None)
        logger.info("Session cleaned: %s", gs.session_id)

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data or ""
    parts = data.split("|")
    if parts[0] == "jump":
        _, session_id, idx = parts
        gs = SESSIONS.get(session_id)
        if not gs:
            await query.edit_message_caption("Session expired or not found.")
            return
        idx = int(idx)
        # check user allowed
        uid = query.from_user.id
        # defense bounds
        if idx < 0 or idx >= len(gs.players):
            await query.answer("Invalid player", show_alert=True)
            return
        if uid != gs.players[idx].user_id:
            await query.answer("Yeh button aapke liye nahi hai.", show_alert=True)
            return
        ok, reason = gs.jump_by_user(uid)
        if ok:
            await query.answer("Jumped!")
        else:
            await query.answer(f"Cannot jump: {reason}", show_alert=False)

    elif parts[0] == "end":
        _, session_id = parts
        gs = SESSIONS.get(session_id)
        if not gs:
            await query.answer("Session not found.")
            return
        # allow only creator or owner
        if query.from_user.id != gs.creator_id and query.from_user.id != OWNER_ID:
            await query.answer("Only creator/owner can end.", show_alert=True)
            return
        gs.running = False
        await query.answer("Ending session...")

@owner_only
async def broadcast_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # /broadcast text...
    if not context.args:
        await update.message.reply_text("Usage: /broadcast <message>")
        return
    text = " ".join(context.args)
    chats = get_all_chats()
    sent = 0
    for c in chats:
        try:
            await context.bot.send_message(chat_id=c, text=f"📣 Broadcast:\n\n{text}")
            sent += 1
            await asyncio.sleep(0.12)  # small pause to reduce rate-limit risk
        except Exception as e:
            logger.exception("Failed send to %s", c)
    await update.message.reply_text(f"Broadcast sent to {sent}/{len(chats)} chats.")

@owner_only
async def podcast_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Owner will send an audio/voice/document next — we will forward to all chats
    caption = " ".join(context.args) if context.args else ""
    PENDING_PODCAST[update.effective_user.id] = caption
    await update.message.reply_text("Send the audio/voice/document now. I will broadcast it to all saved chats.")

async def media_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # If owner has pending podcast and sends audio or voice or document, broadcast it
    user = update.effective_user
    if user.id not in PENDING_PODCAST:
        # track chat for DB and ignore other media
        add_chat(update.effective_chat.id, update.effective_chat.title or "")
        return
    caption = PENDING_PODCAST.pop(user.id, "")
    chats = get_all_chats()
    sent = 0
    # prefer copy_message (keeps file), fallback to forward_message
    for c in chats:
        try:
            # copy the received message (sends by bot)
            await context.bot.copy_message(chat_id=c, from_chat_id=update.effective_chat.id, message_id=update.message.message_id, caption=caption or None)
            sent += 1
            await asyncio.sleep(0.12)
        except Exception:
            try:
                await context.bot.forward_message(chat_id=c, from_chat_id=update.effective_chat.id, message_id=update.message.message_id)
                sent += 1
                await asyncio.sleep(0.12)
            except Exception:
                logger.exception("Failed to send podcast to %s", c)
    await update.message.reply_text(f"Podcast broadcasted to {sent}/{len(chats)} chats.")

@owner_only
async def shutdown_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global STOPPING
    STOPPING = True
    await update.message.reply_text("Shutting down bot and stopping all games...")
    # cancel running tasks
    for sid, task in list(RUNNING_TASKS.items()):
        try:
            task.cancel()
        except:
            pass
    # attempt graceful stop
    await context.application.stop()
    # final exit
    os._exit(0)

async def leaderboard_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rows = top_n(10)
    if not rows:
        await update.message.reply_text("No scores yet.")
        return
    text = "🏆 Leaderboard:\n"
    for i,(u,s) in enumerate(rows, start=1):
        text += f"{i}. {u} — {s}\n"
    await update.message.reply_text(text)

async def catch_all_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # track chat for DB (helps owner broadcasts)
    add_chat(update.effective_chat.id, update.effective_chat.title or "")

def main():
    init_db()
    if not TOKEN:
        print("Set TG_BOT_TOKEN env var or insert token variable in bot.py")
        return
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("newrace", newrace))
    app.add_handler(CommandHandler("join", join))
    app.add_handler(CommandHandler("leave", leave))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("startgame", startgame))
    app.add_handler(CommandHandler("leaderboard", leaderboard_cmd))

    app.add_handler(CommandHandler("broadcast", broadcast_cmd))
    app.add_handler(CommandHandler("podcast", podcast_cmd))
    app.add_handler(CommandHandler("shutdown", shutdown_cmd))

    # Callback queries for buttons
    app.add_handler(CallbackQueryHandler(callback_handler))

    # media handler for podcast: accept audio, voice, document
    audio_filter = filters.VOICE | filters.AUDIO | filters.Document.IMAGE | filters.Document
    app.add_handler(MessageHandler(audio_filter, media_handler))

    # track chats (any message)
    app.add_handler(MessageHandler(filters.ALL & (~filters.COMMAND), catch_all_message))

    print("Bot running (polling)...")
    app.run_polling()

if __name__ == "__main__":
    main()
