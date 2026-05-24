import sqlite3
import random
import string
from datetime import datetime
from typing import Optional
from config import DATABASE_URL, BASE_SLOTS, MAX_SLOTS, USERNAME_ADJECTIVES, USERNAME_NOUNS


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DATABASE_URL)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_conn() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            telegram_id     INTEGER PRIMARY KEY,
            username        TEXT,
            stars_balance   INTEGER DEFAULT 0,
            extra_slots     INTEGER DEFAULT 0,
            is_banned       INTEGER DEFAULT 0,
            created_at      TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS user_nicknames (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            owner_id        INTEGER NOT NULL,
            nickname        TEXT NOT NULL UNIQUE,
            created_at      TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (owner_id) REFERENCES users(telegram_id)
        );

        CREATE TABLE IF NOT EXISTS market (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            seller_id       INTEGER NOT NULL,
            nickname_id     INTEGER NOT NULL,
            price_stars     INTEGER NOT NULL,
            listed_at       TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (seller_id) REFERENCES users(telegram_id),
            FOREIGN KEY (nickname_id) REFERENCES user_nicknames(id)
        );

        CREATE TABLE IF NOT EXISTS transactions (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            buyer_id        INTEGER,
            seller_id       INTEGER,
            nickname_id     INTEGER,
            price_stars     INTEGER,
            type            TEXT,
            created_at      TEXT DEFAULT (datetime('now'))
        );
        """)


# ─── User operations ───────────────────────────────────────────────────────────

def register_user(telegram_id: int, username: Optional[str]) -> dict:
    with get_conn() as conn:
        existing = conn.execute(
            "SELECT * FROM users WHERE telegram_id = ?", (telegram_id,)
        ).fetchone()
        if existing:
            # Update username if changed
            conn.execute(
                "UPDATE users SET username = ? WHERE telegram_id = ?",
                (username, telegram_id)
            )
            return dict(existing)
        conn.execute(
            "INSERT INTO users (telegram_id, username) VALUES (?, ?)",
            (telegram_id, username)
        )
        return get_user(telegram_id)


def get_user(telegram_id: int) -> Optional[dict]:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE telegram_id = ?", (telegram_id,)
        ).fetchone()
        return dict(row) if row else None


def get_all_users() -> list:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM users ORDER BY created_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]


def ban_user(telegram_id: int, ban: bool = True):
    with get_conn() as conn:
        conn.execute(
            "UPDATE users SET is_banned = ? WHERE telegram_id = ?",
            (1 if ban else 0, telegram_id)
        )


def add_stars(telegram_id: int, amount: int):
    with get_conn() as conn:
        conn.execute(
            "UPDATE users SET stars_balance = stars_balance + ? WHERE telegram_id = ?",
            (amount, telegram_id)
        )


def get_user_slots(telegram_id: int) -> dict:
    user = get_user(telegram_id)
    if not user:
        return {"used": 0, "total": BASE_SLOTS, "extra": 0}
    with get_conn() as conn:
        used = conn.execute(
            "SELECT COUNT(*) FROM user_nicknames WHERE owner_id = ?", (telegram_id,)
        ).fetchone()[0]
    total = BASE_SLOTS + user["extra_slots"]
    return {"used": used, "total": total, "extra": user["extra_slots"]}


def expand_slots(telegram_id: int, stars_to_pay: int) -> dict:
    """Returns {'ok': bool, 'reason': str}"""
    from config import STARS_PER_PACK, SLOTS_PER_PACK
    user = get_user(telegram_id)
    if not user:
        return {"ok": False, "reason": "User not found"}
    if user["is_banned"]:
        return {"ok": False, "reason": "You are banned"}

    packs = stars_to_pay // STARS_PER_PACK
    if packs == 0:
        return {"ok": False, "reason": f"Minimum {STARS_PER_PACK} stars"}

    new_extra = user["extra_slots"] + packs * SLOTS_PER_PACK
    max_extra = MAX_SLOTS - BASE_SLOTS
    if new_extra > max_extra:
        new_extra = max_extra
        packs = (new_extra - user["extra_slots"]) // SLOTS_PER_PACK
        if packs == 0:
            return {"ok": False, "reason": "Already at maximum slots"}

    cost = packs * STARS_PER_PACK
    if user["stars_balance"] < cost:
        return {"ok": False, "reason": "Not enough stars"}

    with get_conn() as conn:
        conn.execute(
            "UPDATE users SET stars_balance = stars_balance - ?, extra_slots = ? WHERE telegram_id = ?",
            (cost, new_extra, telegram_id)
        )
    return {"ok": True, "slots_added": packs * SLOTS_PER_PACK, "stars_spent": cost}


# ─── Nickname operations ────────────────────────────────────────────────────────

def _generate_nickname() -> str:
    adj = random.choice(USERNAME_ADJECTIVES)
    noun = random.choice(USERNAME_NOUNS)
    number = "".join(random.choices(string.digits, k=4))
    return f"@{adj}{noun}{number}"


def create_nickname(telegram_id: int) -> dict:
    user = get_user(telegram_id)
    if not user:
        return {"ok": False, "reason": "User not found"}
    if user["is_banned"]:
        return {"ok": False, "reason": "You are banned"}

    slots = get_user_slots(telegram_id)
    if slots["used"] >= slots["total"]:
        return {"ok": False, "reason": "Inventory full"}

    # Generate unique nickname
    for _ in range(20):
        nick = _generate_nickname()
        with get_conn() as conn:
            existing = conn.execute(
                "SELECT id FROM user_nicknames WHERE nickname = ?", (nick,)
            ).fetchone()
            if not existing:
                conn.execute(
                    "INSERT INTO user_nicknames (owner_id, nickname) VALUES (?, ?)",
                    (telegram_id, nick)
                )
                row = conn.execute(
                    "SELECT * FROM user_nicknames WHERE nickname = ?", (nick,)
                ).fetchone()
                return {"ok": True, "nickname": dict(row)}

    return {"ok": False, "reason": "Could not generate unique nickname, try again"}


def get_user_nicknames(telegram_id: int) -> list:
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT un.*, 
               CASE WHEN m.id IS NOT NULL THEN 1 ELSE 0 END as on_market,
               m.price_stars
               FROM user_nicknames un
               LEFT JOIN market m ON m.nickname_id = un.id
               WHERE un.owner_id = ?
               ORDER BY un.created_at DESC""",
            (telegram_id,)
        ).fetchall()
        return [dict(r) for r in rows]


def delete_nickname(telegram_id: int, nickname_id: int) -> dict:
    with get_conn() as conn:
        nick = conn.execute(
            "SELECT * FROM user_nicknames WHERE id = ? AND owner_id = ?",
            (nickname_id, telegram_id)
        ).fetchone()
        if not nick:
            return {"ok": False, "reason": "Nickname not found"}
        # Remove from market if listed
        conn.execute("DELETE FROM market WHERE nickname_id = ?", (nickname_id,))
        conn.execute("DELETE FROM user_nicknames WHERE id = ?", (nickname_id,))
        return {"ok": True}


# ─── Market operations ──────────────────────────────────────────────────────────

def list_on_market(telegram_id: int, nickname_id: int, price: int) -> dict:
    user = get_user(telegram_id)
    if not user or user["is_banned"]:
        return {"ok": False, "reason": "Banned or not found"}

    with get_conn() as conn:
        nick = conn.execute(
            "SELECT * FROM user_nicknames WHERE id = ? AND owner_id = ?",
            (nickname_id, telegram_id)
        ).fetchone()
        if not nick:
            return {"ok": False, "reason": "Nickname not found"}

        already = conn.execute(
            "SELECT id FROM market WHERE nickname_id = ?", (nickname_id,)
        ).fetchone()
        if already:
            return {"ok": False, "reason": "Already listed"}

        if price < 1:
            return {"ok": False, "reason": "Minimum price is 1 star"}

        conn.execute(
            "INSERT INTO market (seller_id, nickname_id, price_stars) VALUES (?, ?, ?)",
            (telegram_id, nickname_id, price)
        )
        return {"ok": True}


def delist_from_market(telegram_id: int, nickname_id: int) -> dict:
    with get_conn() as conn:
        listing = conn.execute(
            "SELECT m.* FROM market m WHERE m.nickname_id = ? AND m.seller_id = ?",
            (nickname_id, telegram_id)
        ).fetchone()
        if not listing:
            return {"ok": False, "reason": "Listing not found"}
        conn.execute("DELETE FROM market WHERE id = ?", (listing["id"],))
        return {"ok": True}


def get_market_listings() -> list:
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT m.id as market_id, m.price_stars, m.listed_at,
               un.id as nickname_id, un.nickname,
               u.username as seller_username, u.telegram_id as seller_id
               FROM market m
               JOIN user_nicknames un ON un.id = m.nickname_id
               JOIN users u ON u.telegram_id = m.seller_id
               ORDER BY m.listed_at DESC"""
        ).fetchall()
        return [dict(r) for r in rows]


def buy_from_market(buyer_id: int, market_id: int) -> dict:
    buyer = get_user(buyer_id)
    if not buyer:
        return {"ok": False, "reason": "User not found"}
    if buyer["is_banned"]:
        return {"ok": False, "reason": "You are banned"}

    with get_conn() as conn:
        listing = conn.execute(
            """SELECT m.*, un.nickname, un.owner_id
               FROM market m JOIN user_nicknames un ON un.id = m.nickname_id
               WHERE m.id = ?""",
            (market_id,)
        ).fetchone()
        if not listing:
            return {"ok": False, "reason": "Listing not found"}

        listing = dict(listing)
        if listing["seller_id"] == buyer_id:
            return {"ok": False, "reason": "Cannot buy your own listing"}

        # Check buyer slots
        slots = get_user_slots(buyer_id)
        if slots["used"] >= slots["total"]:
            return {"ok": False, "reason": "Your inventory is full"}

        if buyer["stars_balance"] < listing["price_stars"]:
            return {"ok": False, "reason": "Not enough stars"}

        # Transfer
        conn.execute(
            "UPDATE users SET stars_balance = stars_balance - ? WHERE telegram_id = ?",
            (listing["price_stars"], buyer_id)
        )
        conn.execute(
            "UPDATE users SET stars_balance = stars_balance + ? WHERE telegram_id = ?",
            (listing["price_stars"], listing["seller_id"])
        )
        conn.execute(
            "UPDATE user_nicknames SET owner_id = ? WHERE id = ?",
            (buyer_id, listing["nickname_id"])
        )
        conn.execute("DELETE FROM market WHERE id = ?", (market_id,))
        conn.execute(
            """INSERT INTO transactions (buyer_id, seller_id, nickname_id, price_stars, type)
               VALUES (?, ?, ?, ?, 'market_purchase')""",
            (buyer_id, listing["seller_id"], listing["nickname_id"], listing["price_stars"])
        )
        return {"ok": True, "nickname": listing["nickname"], "price": listing["price_stars"]}
