from flask import Flask, request, jsonify
import sqlite3
import random
import string
from datetime import datetime

app = Flask(__name__)

DB_PATH = "funpay.db"


def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS deals (
            id TEXT PRIMARY KEY,
            type TEXT, currency TEXT, amount REAL, description TEXT,
            step INTEGER DEFAULT 1,
            buyer_username TEXT, buyer_tg_id INTEGER,
            seller_username TEXT, seller_tg_id INTEGER,
            created_at TEXT, creator_role TEXT
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            rating INTEGER, nickname TEXT, gift TEXT, text TEXT,
            tg_id INTEGER, published INTEGER DEFAULT 1, created_at TEXT
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS wallets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tg_id INTEGER, currency TEXT, network TEXT, address TEXT,
            updated_at TEXT,
            UNIQUE(tg_id, currency, network)
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS balances (
            tg_id INTEGER,
            currency TEXT,
            amount REAL DEFAULT 0,
            PRIMARY KEY (tg_id, currency)
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS workers (
            tg_id INTEGER PRIMARY KEY,
            success INTEGER DEFAULT 0,
            completed INTEGER DEFAULT 0,
            cancelled INTEGER DEFAULT 0,
            turnover REAL DEFAULT 0,
            added_at TEXT
        )
    """)
    conn.commit()
    conn.close()


init_db()


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
    if not row: return None
    keys = ['id', 'type', 'currency', 'amount', 'description', 'step',
            'buyer_username', 'buyer_tg_id', 'seller_username', 'seller_tg_id',
            'created_at', 'creator_role']
    return dict(zip(keys, row))


def review_to_dict(row):
    if not row: return None
    keys = ['id', 'rating', 'nickname', 'gift', 'text', 'tg_id', 'published', 'created_at']
    return dict(zip(keys, row))


# ===== CORS =====
@app.after_request
def add_cors(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    return response


@app.route('/', methods=['GET', 'OPTIONS'])
def root():
    if request.method == 'OPTIONS':
        return '', 200
    return jsonify({"status": "ok", "service": "FunPay Backend"})


# ===== DEALS =====
@app.route('/deals', methods=['POST', 'OPTIONS'])
def create_deal():
    if request.method == 'OPTIONS':
        return '', 200
    data = request.get_json()
    deal_id = generate_deal_id()
    created_at = datetime.now().strftime("%d.%m.%Y, %H:%M:%S")
    if data['type'] == 'buy':
        buyer_username, buyer_tg_id = data['username'], data['tg_id']
        seller_username, seller_tg_id = None, None
        creator_role = 'buyer'
    else:
        seller_username, seller_tg_id = data['username'], data['tg_id']
        buyer_username, buyer_tg_id = None, None
        creator_role = 'seller'
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        INSERT INTO deals (id, type, currency, amount, description, step,
                           buyer_username, buyer_tg_id, seller_username, seller_tg_id,
                           created_at, creator_role)
        VALUES (?, ?, ?, ?, ?, 1, ?, ?, ?, ?, ?, ?)
    """, (deal_id, data['type'], data['currency'], data['amount'], data['description'],
          buyer_username, buyer_tg_id, seller_username, seller_tg_id,
          created_at, creator_role))
    conn.commit(); conn.close()
    return jsonify({"ok": True, "deal_id": deal_id})


@app.route('/deals/user/<int:tg_id>', methods=['GET', 'OPTIONS'])
def get_user_deals(tg_id):
    if request.method == 'OPTIONS':
        return '', 200
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("SELECT * FROM deals WHERE buyer_tg_id = ? OR seller_tg_id = ? ORDER BY rowid DESC", (tg_id, tg_id))
    rows = c.fetchall(); conn.close()
    return jsonify([row_to_dict(r) for r in rows])


@app.route('/deals/<deal_id>', methods=['GET', 'OPTIONS'])
def get_deal(deal_id):
    if request.method == 'OPTIONS':
        return '', 200
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("SELECT * FROM deals WHERE id = ?", (deal_id,))
    row = c.fetchone(); conn.close()
    if not row:
        return jsonify({"detail": "Deal not found"}), 404
    return jsonify(row_to_dict(row))


@app.route('/deals/<deal_id>/join', methods=['POST', 'OPTIONS'])
def join_deal(deal_id):
    if request.method == 'OPTIONS':
        return '', 200
    data = request.get_json()
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("SELECT * FROM deals WHERE id = ?", (deal_id,))
    row = c.fetchone()
    if not row:
        conn.close(); return jsonify({"detail": "Deal not found"}), 404
    deal = row_to_dict(row)
    if deal['creator_role'] == 'buyer':
        c.execute("UPDATE deals SET seller_username = ?, seller_tg_id = ? WHERE id = ?",
                  (data['username'], data['tg_id'], deal_id))
    else:
        c.execute("UPDATE deals SET buyer_username = ?, buyer_tg_id = ? WHERE id = ?",
                  (data['username'], data['tg_id'], deal_id))
    conn.commit(); conn.close()
    return jsonify({"ok": True})


@app.route('/deals/<deal_id>/step', methods=['POST', 'OPTIONS'])
def update_step(deal_id):
    if request.method == 'OPTIONS':
        return '', 200
    data = request.get_json()
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("UPDATE deals SET step = ? WHERE id = ?", (data['step'], deal_id))
    conn.commit(); conn.close()
    return jsonify({"ok": True})


@app.route('/deals/<deal_id>', methods=['DELETE', 'OPTIONS'])
def delete_deal(deal_id):
    if request.method == 'OPTIONS':
        return '', 200
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("DELETE FROM deals WHERE id = ?", (deal_id,))
    conn.commit(); conn.close()
    return jsonify({"ok": True})


# ===== REVIEWS =====
@app.route('/reviews', methods=['POST', 'OPTIONS'])
def create_review():
    if request.method == 'OPTIONS':
        return '', 200
    data = request.get_json()
    if data['rating'] < 1 or data['rating'] > 5:
        return jsonify({"detail": "Rating must be 1-5"}), 400
    published = 1 if data['rating'] >= 4 else 0
    created_at = datetime.now().strftime("%d.%m.%Y, %H:%M:%S")
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("""INSERT INTO reviews (rating, nickname, gift, text, tg_id, published, created_at)
                 VALUES (?, ?, ?, ?, ?, ?, ?)""",
              (data['rating'], data['nickname'], data['gift'], data['text'], data['tg_id'], published, created_at))
    conn.commit(); conn.close()
    return jsonify({"ok": True, "published": published})


@app.route('/reviews', methods=['GET', 'OPTIONS'])
def get_reviews():
    if request.method == 'OPTIONS':
        return '', 200
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("SELECT * FROM reviews WHERE published = 1 ORDER BY id DESC")
    rows = c.fetchall()
    c.execute("SELECT rating, COUNT(*) FROM reviews GROUP BY rating")
    stats_raw = c.fetchall()
    conn.close()
    stats = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
    total = 0; total_sum = 0
    for rating, count in stats_raw:
        stats[rating] = count; total += count; total_sum += rating * count
    average = round(total_sum / total, 1) if total > 0 else 0.0
    return jsonify({
        "reviews": [review_to_dict(r) for r in rows],
        "stats": {"average": average, "total": total,
                  "5": stats[5], "4": stats[4], "3": stats[3], "2": stats[2], "1": stats[1]}
    })


@app.route('/admin/seed-reviews', methods=['POST', 'OPTIONS'])
def seed_reviews():
    if request.method == 'OPTIONS':
        return '', 200
    reviews = request.get_json()
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    added = 0
    for r in reviews:
        published = 1 if r['rating'] >= 4 else 0
        c.execute("""INSERT INTO reviews (rating, nickname, gift, text, tg_id, published, created_at)
                     VALUES (?, ?, ?, ?, 0, ?, ?)""",
                  (r['rating'], r['nickname'], r['gift'], r['text'], published, r['created_at']))
        added += 1
    conn.commit(); conn.close()
    return jsonify({"ok": True, "added": added})


@app.route('/admin/reviews', methods=['DELETE', 'OPTIONS'])
def clear_reviews():
    if request.method == 'OPTIONS':
        return '', 200
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("DELETE FROM reviews")
    conn.commit(); conn.close()
    return jsonify({"ok": True})


# ===== WALLETS =====
@app.route('/wallets/<int:tg_id>', methods=['GET', 'OPTIONS'])
def get_wallets(tg_id):
    if request.method == 'OPTIONS':
        return '', 200
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("SELECT tg_id, currency, network, address, updated_at FROM wallets WHERE tg_id = ?", (tg_id,))
    rows = c.fetchall(); conn.close()
    keys = ['tg_id', 'currency', 'network', 'address', 'updated_at']
    return jsonify([dict(zip(keys, r)) for r in rows])


@app.route('/wallets', methods=['POST', 'OPTIONS'])
def save_wallet():
    if request.method == 'OPTIONS':
        return '', 200
    data = request.get_json()
    updated_at = datetime.now().strftime("%d.%m.%Y, %H:%M:%S")
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    if not data['address'].strip():
        c.execute("DELETE FROM wallets WHERE tg_id = ? AND currency = ? AND network = ?",
                  (data['tg_id'], data['currency'], data['network']))
    else:
        c.execute("""INSERT INTO wallets (tg_id, currency, network, address, updated_at)
                     VALUES (?, ?, ?, ?, ?)
                     ON CONFLICT(tg_id, currency, network) DO UPDATE SET
                         address = excluded.address,
                         updated_at = excluded.updated_at""",
                  (data['tg_id'], data['currency'], data['network'], data['address'].strip(), updated_at))
    conn.commit(); conn.close()
    return jsonify({"ok": True})


# ===== BALANCES =====
@app.route('/balance/<int:tg_id>', methods=['GET', 'OPTIONS'])
def get_all_balances(tg_id):
    if request.method == 'OPTIONS':
        return '', 200
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("SELECT currency, amount FROM balances WHERE tg_id = ?", (tg_id,))
    rows = c.fetchall(); conn.close()
    return jsonify({r[0]: r[1] for r in rows})


@app.route('/balance/<int:tg_id>/<currency>', methods=['GET', 'OPTIONS'])
def get_balance(tg_id, currency):
    if request.method == 'OPTIONS':
        return '', 200
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("SELECT amount FROM balances WHERE tg_id = ? AND currency = ?", (tg_id, currency))
    row = c.fetchone(); conn.close()
    return jsonify({"amount": row[0] if row else 0})


@app.route('/balance/add', methods=['POST', 'OPTIONS'])
def balance_add():
    if request.method == 'OPTIONS':
        return '', 200
    data = request.get_json()
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("""INSERT INTO balances (tg_id, currency, amount)
                 VALUES (?, ?, ?)
                 ON CONFLICT(tg_id, currency) DO UPDATE SET amount = amount + excluded.amount""",
              (data['tg_id'], data['currency'], data['amount']))
    conn.commit(); conn.close()
    return jsonify({"ok": True})


@app.route('/balance/subtract', methods=['POST', 'OPTIONS'])
def balance_subtract():
    if request.method == 'OPTIONS':
        return '', 200
    data = request.get_json()
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("SELECT amount FROM balances WHERE tg_id = ? AND currency = ?", (data['tg_id'], data['currency']))
    row = c.fetchone()
    current = row[0] if row else 0
    if current < data['amount']:
        conn.close()
        return jsonify({"detail": "Not enough balance"}), 400
    c.execute("UPDATE balances SET amount = amount - ? WHERE tg_id = ? AND currency = ?",
              (data['amount'], data['tg_id'], data['currency']))
    conn.commit(); conn.close()
    return jsonify({"ok": True})


# ===== WORKER =====
@app.route('/worker/<int:tg_id>', methods=['GET', 'OPTIONS'])
def get_worker(tg_id):
    if request.method == 'OPTIONS':
        return '', 200
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("SELECT tg_id, success, completed, cancelled, turnover, added_at FROM workers WHERE tg_id = ?", (tg_id,))
    row = c.fetchone()
    if not row:
        conn.close()
        return jsonify({"success": 0, "completed": 0, "cancelled": 0, "turnover": 0, "is_worker": False})
    conn.close()
    return jsonify({"success": row[1], "completed": row[2], "cancelled": row[3], "turnover": row[4], "is_worker": True})


@app.route('/worker/grant', methods=['POST', 'OPTIONS'])
def worker_grant():
    if request.method == 'OPTIONS':
        return '', 200
    data = request.get_json()
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    added_at = datetime.now().strftime("%d.%m.%Y, %H:%M:%S")
    c.execute("""INSERT INTO workers (tg_id, added_at)
                 VALUES (?, ?)
                 ON CONFLICT(tg_id) DO NOTHING""", (data['tg_id'], added_at))
    conn.commit(); conn.close()
    return jsonify({"ok": True})


@app.route('/worker/update', methods=['POST', 'OPTIONS'])
def worker_update():
    if request.method == 'OPTIONS':
        return '', 200
    data = request.get_json()
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    if 'success' in data:
        c.execute("UPDATE workers SET success = ? WHERE tg_id = ?", (data['success'], data['tg_id']))
    if 'completed' in data:
        c.execute("UPDATE workers SET completed = ? WHERE tg_id = ?", (data['completed'], data['tg_id']))
    if 'cancelled' in data:
        c.execute("UPDATE workers SET cancelled = ? WHERE tg_id = ?", (data['cancelled'], data['tg_id']))
    if 'turnover' in data:
        c.execute("UPDATE workers SET turnover = ? WHERE tg_id = ?", (data['turnover'], data['tg_id']))
    conn.commit(); conn.close()
    return jsonify({"ok": True})


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000)