# db.py
import sqlite3
from pathlib import Path
from typing import List, Tuple

DB_PATH = Path("dino.db")

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS leaderboard (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        score INTEGER
    )
    """)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS chats (
        chat_id INTEGER PRIMARY KEY,
        title TEXT
    )
    """)
    conn.commit()
    conn.close()

def update_score(user_id:int, username:str, score:int):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT score FROM leaderboard WHERE user_id=?", (user_id,))
    row = cur.fetchone()
    if row:
        if score > row[0]:
            cur.execute("UPDATE leaderboard SET score=?, username=? WHERE user_id=?", (score, username, user_id))
    else:
        cur.execute("INSERT INTO leaderboard(user_id, username, score) VALUES(?,?,?)", (user_id, username, score))
    conn.commit()
    conn.close()

def top_n(n:int=10) -> List[Tuple[str,int]]:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT username, score FROM leaderboard ORDER BY score DESC LIMIT ?", (n,))
    rows = cur.fetchall()
    conn.close()
    return rows

def add_chat(chat_id:int, title:str=None):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("INSERT OR REPLACE INTO chats(chat_id, title) VALUES(?,?)", (chat_id, title or ""))
    conn.commit()
    conn.close()

def get_all_chats() -> List[int]:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT chat_id FROM chats")
    rows = [r[0] for r in cur.fetchall()]
    conn.close()
    return rows

if __name__ == "__main__":
    init_db()
    print("DB initialized.")
