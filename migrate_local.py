"""
Script de diagnóstico y reparación de la base de datos local.
Agrega las columnas que faltan en SQLite sin borrar datos.
"""
import sqlite3
import os

DB_FILE = "loans.db"

if not os.path.exists(DB_FILE):
    print(f"No existe {DB_FILE}, no es necesaria la migración.")
    exit(0)

conn = sqlite3.connect(DB_FILE)
cursor = conn.cursor()

def column_exists(table, column):
    cursor.execute(f"PRAGMA table_info({table})")
    cols = [row[1] for row in cursor.fetchall()]
    return column in cols

def table_exists(table):
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,))
    return cursor.fetchone() is not None

fixes = []

# rates: add updated_at
if table_exists("rates") and not column_exists("rates", "updated_at"):
    cursor.execute("ALTER TABLE rates ADD COLUMN updated_at DATETIME")
    fixes.append("rates.updated_at")

# users: add webauthn_id (SQLite no permite UNIQUE en ALTER TABLE, se omite)
if table_exists("users") and not column_exists("users", "webauthn_id"):
    cursor.execute("ALTER TABLE users ADD COLUMN webauthn_id VARCHAR")
    fixes.append("users.webauthn_id")

# Create WebAuthnCredential table if missing
if not table_exists("webauthn_credentials"):
    cursor.execute("""
        CREATE TABLE webauthn_credentials (
            id INTEGER PRIMARY KEY,
            user_id INTEGER NOT NULL,
            credential_id VARCHAR NOT NULL UNIQUE,
            public_key TEXT NOT NULL,
            sign_count INTEGER DEFAULT 0,
            created_at DATETIME,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)
    fixes.append("tabla webauthn_credentials")

# Create PushSubscription table if missing
if not table_exists("push_subscriptions"):
    cursor.execute("""
        CREATE TABLE push_subscriptions (
            id INTEGER PRIMARY KEY,
            user_id INTEGER NOT NULL,
            endpoint TEXT NOT NULL UNIQUE,
            auth_key TEXT NOT NULL,
            p256dh_key TEXT NOT NULL,
            browser TEXT,
            created_at DATETIME,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)
    fixes.append("tabla push_subscriptions")

conn.commit()
conn.close()

if fixes:
    print(f"Migración completada. Cambios: {', '.join(fixes)}")
else:
    print("Base de datos ya está al día, no hubo cambios.")
