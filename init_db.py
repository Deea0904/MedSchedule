import sqlite3

con = sqlite3.connect("medschedule.db")
with open("schema.sql", encoding="utf-8") as f:
    con.executescript(f.read())
con.close()
print("Baza de date a fost creată.")