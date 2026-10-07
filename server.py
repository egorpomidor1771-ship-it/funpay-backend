from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import sqlite3
import random
import string
from datetime import datetime

app = FastAPI(title="FunPay Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_PATH = "funpay.db"


def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS deals (
            id TEXT PRIMARY KEY,
            type TEXT,
            currency TEXT,
            amount REAL,
            description TEXT,
            step INTEGER DEFAULT 1,
            buyer_username TEXT,
            buyer_tg_id INTEGER,
            seller_username TEXT,
            seller_tg_id INTEGER,
            created_at TEXT,
            creator_role TEXT
        )
    """)
    conn.commit()
    conn.close()

init_db()


class CreateDeal(BaseModel):
    type: str
    currency: str
    amount: float
    description: str
    username: str
    tg_id: int


class JoinDeal(BaseModel):
    username: str
    tg_id: int


class UpdateStep(BaseModel):
    step: int


def generate_deal_id():
    chars = string.ascii_uppercase + string.digits
    while True:
        deal_id = ''.join(random.choice(chars) for _ in range(8))
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT 1 FROM deals WHERE id = ?", (deal_id,))
        exists = c.fetchone()
        conn.close()
        if not exists:
            return deal_id


def row_to_dict(row):
    if not row:
        return None
    keys = ['id', 'type', 'currency', 'amount', 'description', 'step',
            'buyer_username', 'buyer_tg_id', 'seller_username', 'seller_tg_id',
            'created_at', 'creator_role']
    return dict(zip(keys, row))


@app.get("/")
def root():
    return {"status": "ok", "service": "FunPay Backend"}


@app.post("/deals")
def create_deal(data: CreateDeal):
    deal_id = generate_deal_id()
    created_at = datetime.now().strftime("%d.%m.%Y, %H:%M:%S")

    if data.type == 'buy':
        buyer_username = data.username
        buyer_tg_id = data.tg_id
        seller_username = None
        seller_tg_id = None
        creator_role = 'buyer'
    else:
        seller_username = data.username
        seller_tg_id = data.tg_id
        buyer_username = None
        buyer_tg_id = None
        creator_role = 'seller'

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        INSERT INTO deals (id, type, currency, amount, description, step,
                           buyer_username, buyer_tg_id,
                           seller_username, seller_tg_id,
                           created_at, creator_role)
        VALUES (?, ?, ?, ?, ?, 1, ?, ?, ?, ?, ?, ?)
    """, (deal_id, data.type, data.currency, data.amount, data.description,
          buyer_username, buyer_tg_id, seller_username, seller_tg_id,
          created_at, creator_role))
    conn.commit()
    conn.close()

    return {"ok": True, "deal_id": deal_id}


@app.get("/deals/user/{tg_id}")
def get_user_deals(tg_id: int):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        SELECT * FROM deals
        WHERE buyer_tg_id = ? OR seller_tg_id = ?
        ORDER BY rowid DESC
    """, (tg_id, tg_id))
    rows = c.fetchall()
    conn.close()
    return [row_to_dict(r) for r in rows]


@app.get("/deals/{deal_id}")
def get_deal(deal_id: str):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM deals WHERE id = ?", (deal_id,))
    row = c.fetchone()
    conn.close()

    if not row:
        raise HTTPException(status_code=404, detail="Deal not found")

    return row_to_dict(row)


@app.post("/deals/{deal_id}/join")
def join_deal(deal_id: str, data: JoinDeal):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM deals WHERE id = ?", (deal_id,))
    row = c.fetchone()

    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Deal not found")

    deal = row_to_dict(row)

    if deal['creator_role'] == 'buyer':
        if deal['seller_tg_id'] and deal['seller_tg_id'] != data.tg_id:
            conn.close()
            raise HTTPException(status_code=400, detail="Deal already has seller")
        c.execute("""
            UPDATE deals SET seller_username = ?, seller_tg_id = ?
            WHERE id = ?
        """, (data.username, data.tg_id, deal_id))
    else:
        if deal['buyer_tg_id'] and deal['buyer_tg_id'] != data.tg_id:
            conn.close()
            raise HTTPException(status_code=400, detail="Deal already has buyer")
        c.execute("""
            UPDATE deals SET buyer_username = ?, buyer_tg_id = ?
            WHERE id = ?
        """, (data.username, data.tg_id, deal_id))

    conn.commit()
    conn.close()

    return {"ok": True}


@app.post("/deals/{deal_id}/step")
def update_step(deal_id: str, data: UpdateStep):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE deals SET step = ? WHERE id = ?", (data.step, deal_id))
    conn.commit()
    conn.close()
    return {"ok": True}
