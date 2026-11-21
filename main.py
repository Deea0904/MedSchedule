import sqlite3
from datetime import date, datetime, time, timedelta

from flask import Flask, g, redirect, render_template, request, url_for

DB_PATH = "medschedule.db"
MAX_ZILE = 14  # programari cu maximum 14 zile inainte
ZILE = ["Lun", "Mar", "Mie", "Joi", "Vin", "Sâm", "Dum"]

app = Flask(__name__)


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(exc):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def sloturi_libere(db, medic_id, data_str):
    """Intervalele libere ale unui medic intr-o zi."""
    try:
        d = date.fromisoformat(data_str)
    except (TypeError, ValueError):
        return []
    medic = db.execute(
        "SELECT durata_min FROM Medici WHERE id = ? AND activ = 1", (medic_id,)
    ).fetchone()
    if medic is None:
        return []
    concediu = db.execute(
        "SELECT 1 FROM Concedii WHERE medic_id = ? AND ? BETWEEN data_start AND data_end",
        (medic_id, data_str),
    ).fetchone()
    if concediu:
        return []
    ocupate = {
        r["ora"]
        for r in db.execute(
            "SELECT ora FROM Programari WHERE medic_id = ? AND data = ? AND status <> 'Anulata'",
            (medic_id, data_str),
        )
    }
    program = db.execute(
        "SELECT ora_start, ora_end FROM ProgramMedici WHERE medic_id = ? AND zi_sapt = ?",
        (medic_id, d.weekday()),
    ).fetchall()
    durata = timedelta(minutes=medic["durata_min"])
    acum = datetime.now()
    sloturi = []
    for interval in program:
        t = datetime.combine(d, time.fromisoformat(interval["ora_start"]))
        sfarsit = datetime.combine(d, time.fromisoformat(interval["ora_end"]))
        while t + durata <= sfarsit:
            ora = t.strftime("%H:%M")
            if ora not in ocupate and t > acum:
                sloturi.append(ora)
            t += durata
    return sloturi


def pagina(form=None, erori=None):
    db = get_db()
    src = form if form is not None else request.args
    spec = src.get("spec")
    medic_id = src.get("medic", type=int)
    data = src.get("data")

    specialitati = [
        r["specialitate"]
        for r in db.execute(
            "SELECT DISTINCT specialitate FROM Medici WHERE activ = 1 ORDER BY specialitate"
        )
    ]
    medici = []
    if spec:
        medici = db.execute(
            "SELECT id, nume, durata_min FROM Medici WHERE specialitate = ? AND activ = 1",
            (spec,),
        ).fetchall()

    zile = []
    if medic_id:
        azi = date.today()
        for i in range(MAX_ZILE + 1):
            d = azi + timedelta(days=i)
            iso = d.isoformat()
            zile.append(
                {
                    "iso": iso,
                    "zi": ZILE[d.weekday()],
                    "nr": d.day,
                    "libere": bool(sloturi_libere(db, medic_id, iso)),
                }
            )

    sloturi = sloturi_libere(db, medic_id, data) if (medic_id and data) else []
    medic_ales = next((m for m in medici if m["id"] == medic_id), None)

    return render_template(
        "index.html",
        specialitati=specialitati, medici=medici, zile=zile, sloturi=sloturi,
        spec=spec, medic_id=medic_id, data=data, medic_ales=medic_ales,
        form=form or {}, erori=erori or [],
    )


@app.route("/")
def index():
    return pagina()


@app.route("/programeaza", methods=["POST"])
def programeaza():
    f = request.form
    erori = []
    medic_id = f.get("medic", type=int)
    data = f.get("data", "")
    ora = f.get("ora", "")
    nume = f.get("nume", "").strip()
    nastere = f.get("data_nasterii", "").strip()
    telefon = f.get("telefon", "").strip()
    email = f.get("email", "").strip()
    motiv = f.get("motiv", "").strip()

    if not ora:
        erori.append("Alege un interval orar.")
    if not nume:
        erori.append("Completează numele.")
    if not nastere:
        erori.append("Completează data nașterii.")
    if not telefon:
        erori.append("Completează telefonul.")
    if "@" not in email or "." not in email:
        erori.append("Introdu o adresă de email validă.")
    if not f.get("gdpr"):
        erori.append("Trebuie să fii de acord cu prelucrarea datelor (GDPR).")
    try:
        d = date.fromisoformat(data)
        if not (date.today() <= d <= date.today() + timedelta(days=MAX_ZILE)):
            erori.append(f"Poți programa cu maximum {MAX_ZILE} zile înainte.")
    except ValueError:
        erori.append("Data selectată nu este validă.")

    db = get_db()
    if not erori and ora not in sloturi_libere(db, medic_id, data):
        erori.append("Intervalul ales nu mai este disponibil. Alege altul.")
    if erori:
        return pagina(form=f, erori=erori)

    try:
        cur = db.execute(
            """INSERT INTO Programari
               (medic_id, data, ora, nume, data_nasterii, telefon, email, motiv, acord_gdpr, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, 'Nou')""",
            (medic_id, data, ora, nume, nastere, telefon, email, motiv or None),
        )
        db.commit()
    except sqlite3.IntegrityError:
        # cineva a rezervat acelasi slot chiar acum (indexul unic din baza de date)
        return pagina(form=f, erori=["Intervalul tocmai a fost rezervat de altcineva. Alege altul."])
    return redirect(url_for("confirmare", id=cur.lastrowid))


@app.route("/confirmare/<int:id>")
def confirmare(id):
    p = get_db().execute(
        """SELECT p.id, p.data, p.ora, p.nume, m.nume AS medic, m.specialitate
           FROM Programari p JOIN Medici m ON m.id = p.medic_id WHERE p.id = ?""",
        (id,),
    ).fetchone()
    if p is None:
        return redirect(url_for("index"))
    return render_template("confirmare.html", p=p)


if __name__ == "__main__":
    app.run(debug=True)