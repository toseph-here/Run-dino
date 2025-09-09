import sqlite3
from pathlib import Path

DB_PATH = Path("dino.db")

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS leaderboard (
        user_id INTEGER,
        username TEXT,
        score INTEGER,
        PRIMARY KEY(user_id)
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
            cur.execute("UPDATE leaderboard SET score=? WHERE user_id=?", (score, user_id))
    else:
        cur.execute("INSERT INTO leaderboard(user_id, username, score) VALUES(?,?,?)", (user_id, username, score))
    conn.commit()
    conn.close()

def top_n(n=10):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT username, score FROM leaderboard ORDER BY score DESC LIMIT ?", (n,))
    rows = cur.fetchall()
    conn.close()
    return rows
