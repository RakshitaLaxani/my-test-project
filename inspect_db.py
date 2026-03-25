import sqlite3

conn = sqlite3.connect('voting.db')
cur = conn.cursor()

# Get all tables
cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = cur.fetchall()
print("Tables:", tables)

for table in tables:
    table_name = table[0]
    print(f"\n{table_name} table:")

    # Get columns
    cur.execute(f"PRAGMA table_info({table_name})")
    columns = cur.fetchall()
    print("Columns:", [col[1] for col in columns])

    # Get data
    cur.execute(f"SELECT * FROM {table_name}")
    data = cur.fetchall()
    print("Data:", data)

conn.close()
