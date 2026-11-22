import secrets
import sqlite3

con = sqlite3.connect("medschedule.db")
cols = {r[1] for r in con.execute("PRAGMA table_info(Programari)")}

if "token" not in cols:
    con.execute("ALTER TABLE Programari ADD COLUMN token TEXT")
if "raspuns_pacient" not in cols:
    con.execute("ALTER TABLE Programari ADD COLUMN raspuns_pacient TEXT "
                "CHECK (raspuns_pacient IN ('Confirmat', 'Anulat'))")
if "anulare_procesata" not in cols:
    con.execute("ALTER TABLE Programari ADD COLUMN anulare_procesata INTEGER NOT NULL DEFAULT 0")

# programarile existente primesc si ele un token
for (id_,) in con.execute("SELECT id FROM Programari WHERE token IS NULL").fetchall():
    con.execute("UPDATE Programari SET token = ? WHERE id = ?", (secrets.token_urlsafe(16), id_))

con.execute("CREATE UNIQUE INDEX IF NOT EXISTS ux_programari_token ON Programari (token)")
con.commit()
con.close()
print("Baza de date a fost actualizata.")
