import sqlite3

from database import Base, DB_PATH, engine


def init_db():
    Base.metadata.create_all(bind=engine)
    print(f"Database initialized at: {DB_PATH}")


def confirm_tables():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT name, sql FROM sqlite_master WHERE type='table'")
    rows = cursor.fetchall()
    conn.close()
    return rows


if __name__ == "__main__":
    init_db()
    for name, sql in confirm_tables():
        print(f"\n-- {name} --")
        print(sql)
