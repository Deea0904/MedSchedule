import sqlite3

con = sqlite3.connect("medschedule.db")
print(con.execute("SELECT nume, specialitate FROM Medici").fetchall())
con.close()