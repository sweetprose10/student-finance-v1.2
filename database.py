import sqlite3
from pathlib import Path
from werkzeug.security import check_password_hash, generate_password_hash

DATABASE = Path(__file__).resolve().parent / "database" / "finance.db"


def connect():
    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row
    return connection


def create_tables():
    connection = connect()
    cursor = connection.cursor()
    cursor.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL,
            google_sub TEXT UNIQUE,
            role TEXT NOT NULL DEFAULT 'user',
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS transaksi (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL DEFAULT 1,
            jenis TEXT NOT NULL,
            kategori TEXT NOT NULL,
            nominal INTEGER NOT NULL,
            keterangan TEXT,
            tanggal TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS wishlist (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL DEFAULT 1,
            nama TEXT NOT NULL,
            harga INTEGER NOT NULL,
            terkumpul INTEGER DEFAULT 0,
            prioritas TEXT DEFAULT 'Normal',
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS targets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            nama TEXT NOT NULL,
            nominal INTEGER NOT NULL,
            terkumpul INTEGER NOT NULL DEFAULT 0,
            tenggat TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );
        """
    )
    transaction_columns = {row[1] for row in cursor.execute("PRAGMA table_info(transaksi)").fetchall()}
    wishlist_columns = {row[1] for row in cursor.execute("PRAGMA table_info(wishlist)").fetchall()}
    user_columns = {row[1] for row in cursor.execute("PRAGMA table_info(users)").fetchall()}
    if "user_id" not in transaction_columns:
        cursor.execute("ALTER TABLE transaksi ADD COLUMN user_id INTEGER NOT NULL DEFAULT 1")
    if "user_id" not in wishlist_columns:
        cursor.execute("ALTER TABLE wishlist ADD COLUMN user_id INTEGER NOT NULL DEFAULT 1")
    if "google_sub" not in user_columns:
        cursor.execute("ALTER TABLE users ADD COLUMN google_sub TEXT")
    cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_google_sub ON users(google_sub)")
    connection.commit()
    connection.close()


def ensure_default_user():
    connection = connect()
    existing = connection.execute("SELECT * FROM users WHERE username = ?", ("admin",)).fetchone()
    if not existing:
        connection.execute(
            "INSERT INTO users (username, password, role, created_at) VALUES (?, ?, ?, datetime('now'))",
            ("admin", generate_password_hash("12345"), "admin",),
        )
        connection.commit()
    else:
        password = existing["password"] if "password" in existing.keys() else ""
        if not password.startswith(("scrypt:", "pbkdf2:")):
            connection.execute(
                "UPDATE users SET password = ? WHERE id = ?",
                (generate_password_hash(password), existing["id"]),
            )
            connection.commit()
    connection.close()


def get_user(username, password):
    connection = connect()
    user = connection.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    if user and not check_password_hash(user["password"], password):
        user = None
    connection.close()
    return user


def create_user(username, password):
    connection = connect()
    try:
        cursor = connection.execute(
            "INSERT INTO users (username, password, created_at) VALUES (?, ?, datetime('now'))",
            (username, generate_password_hash(password)),
        )
        connection.commit()
        return cursor.lastrowid
    except sqlite3.IntegrityError:
        return None
    finally:
        connection.close()


def user_by_id(user_id):
    connection = connect()
    user = connection.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    connection.close()
    return user


def user_by_google_sub(google_sub):
    connection = connect()
    user = connection.execute("SELECT * FROM users WHERE google_sub = ?", (google_sub,)).fetchone()
    connection.close()
    return user


def create_google_user(username, google_sub):
    connection = connect()
    try:
        cursor = connection.execute(
            "INSERT INTO users (username, password, google_sub, created_at) VALUES (?, ?, ?, datetime('now'))",
            (username, generate_password_hash(google_sub), google_sub),
        )
        connection.commit()
        return cursor.lastrowid
    except sqlite3.IntegrityError:
        return None
    finally:
        connection.close()


def all_users():
    connection = connect()
    users = connection.execute("SELECT id, username, role, created_at FROM users ORDER BY id DESC").fetchall()
    connection.close()
    return users


def delete_user(user_id):
    connection = connect()
    connection.execute("DELETE FROM users WHERE id = ?", (user_id,))
    connection.commit()
    connection.close()


def tambah_transaksi(user_id, jenis, kategori, nominal, keterangan, tanggal):
    connection = connect()
    connection.execute(
        "INSERT INTO transaksi (user_id, jenis, kategori, nominal, keterangan, tanggal) VALUES (?, ?, ?, ?, ?, ?)",
        (user_id, jenis, kategori, nominal, keterangan, tanggal),
    )
    connection.commit()
    connection.close()


def semua_transaksi(user_id):
    connection = connect()
    data = connection.execute(
        "SELECT user_id, id, jenis, kategori, nominal, keterangan, tanggal FROM transaksi WHERE user_id = ? ORDER BY id DESC", (user_id,)
    ).fetchall()
    connection.close()
    return data


def total_pemasukan(user_id):
    connection = connect()
    total = connection.execute(
        "SELECT COALESCE(SUM(nominal), 0) FROM transaksi WHERE user_id = ? AND jenis = 'Pemasukan'",
        (user_id,),
    ).fetchone()[0]
    connection.close()
    return total


def total_pengeluaran(user_id):
    connection = connect()
    total = connection.execute(
        "SELECT COALESCE(SUM(nominal), 0) FROM transaksi WHERE user_id = ? AND jenis = 'Pengeluaran'",
        (user_id,),
    ).fetchone()[0]
    connection.close()
    return total


def saldo(user_id):
    return total_pemasukan(user_id) - total_pengeluaran(user_id)


def hapus_transaksi(user_id, transaction_id):
    connection = connect()
    connection.execute("DELETE FROM transaksi WHERE id = ? AND user_id = ?", (transaction_id, user_id))
    connection.commit()
    connection.close()


def transaksi_by_id(user_id, transaction_id):
    connection = connect()
    data = connection.execute(
        "SELECT user_id, id, jenis, kategori, nominal, keterangan, tanggal FROM transaksi WHERE id = ? AND user_id = ?", (transaction_id, user_id)
    ).fetchone()
    connection.close()
    return data


def update_transaksi(user_id, transaction_id, kategori, nominal, keterangan):
    connection = connect()
    connection.execute(
        "UPDATE transaksi SET kategori = ?, nominal = ?, keterangan = ? WHERE id = ? AND user_id = ?",
        (kategori, nominal, keterangan, transaction_id, user_id),
    )
    connection.commit()
    connection.close()


def cari_transaksi(user_id, keyword):
    connection = connect()
    pattern = f"%{keyword}%"
    data = connection.execute(
        "SELECT user_id, id, jenis, kategori, nominal, keterangan, tanggal FROM transaksi WHERE user_id = ? AND (kategori LIKE ? OR keterangan LIKE ?) ORDER BY id DESC",
        (user_id, pattern, pattern),
    ).fetchall()
    connection.close()
    return data


def semua_wishlist(user_id):
    connection = connect()
    data = connection.execute("SELECT user_id, id, nama, harga, terkumpul, prioritas FROM wishlist WHERE user_id = ? ORDER BY id DESC", (user_id,)).fetchall()
    connection.close()
    return data


def tambah_wishlist(user_id, nama, harga, prioritas):
    connection = connect()
    connection.execute(
        "INSERT INTO wishlist (user_id, nama, harga, prioritas) VALUES (?, ?, ?, ?)",
        (user_id, nama, harga, prioritas),
    )
    connection.commit()
    connection.close()


def hapus_wishlist(user_id, wishlist_id):
    connection = connect()
    connection.execute("DELETE FROM wishlist WHERE id = ? AND user_id = ?", (wishlist_id, user_id))
    connection.commit()
    connection.close()


def semua_target(user_id):
    connection = connect()
    data = connection.execute("SELECT * FROM targets WHERE user_id = ? ORDER BY id DESC", (user_id,)).fetchall()
    connection.close()
    return data


def tambah_target(user_id, nama, nominal, tenggat):
    connection = connect()
    connection.execute(
        "INSERT INTO targets (user_id, nama, nominal, tenggat) VALUES (?, ?, ?, ?)",
        (user_id, nama, nominal, tenggat),
    )
    connection.commit()
    connection.close()


def update_target_progress(user_id, target_id, terkumpul):
    connection = connect()
    connection.execute(
        "UPDATE targets SET terkumpul = ? WHERE id = ? AND user_id = ?",
        (terkumpul, target_id, user_id),
    )
    connection.commit()
    connection.close()


def hapus_target(user_id, target_id):
    connection = connect()
    connection.execute("DELETE FROM targets WHERE id = ? AND user_id = ?", (target_id, user_id))
    connection.commit()
    connection.close()


create_tables()
ensure_default_user()
