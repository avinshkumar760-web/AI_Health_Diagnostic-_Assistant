import sqlite3

DATABASE = "health_ai.db"


def create_database():

    conn = sqlite3.connect(DATABASE)

    cursor = conn.cursor()

    # Users Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            name TEXT NOT NULL,

            email TEXT UNIQUE NOT NULL,

            password TEXT NOT NULL

        )
    """)

    # Assessments Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS assessments (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            user_id INTEGER NOT NULL,

            symptoms TEXT NOT NULL,

            result TEXT NOT NULL,

            risk TEXT NOT NULL,

            created_at TEXT NOT NULL,

            FOREIGN KEY (user_id)
            REFERENCES users(id)

        )
    """)

    conn.commit()

    conn.close()

    print("Database created successfully!")


if __name__ == "__main__":

    create_database()