-- MedSchedule: schema SQLite
PRAGMA foreign_keys = ON;

-- Medici
CREATE TABLE Medici (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    nume          TEXT    NOT NULL,
    specialitate  TEXT    NOT NULL,
    durata_min    INTEGER NOT NULL DEFAULT 30 CHECK (durata_min > 0),
    activ         INTEGER NOT NULL DEFAULT 1 CHECK (activ IN (0, 1))
);

-- Programul saptamanal (0 = luni ... 6 = duminica)
CREATE TABLE ProgramMedici (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    medic_id   INTEGER NOT NULL REFERENCES Medici(id),
    zi_sapt    INTEGER NOT NULL CHECK (zi_sapt BETWEEN 0 AND 6),
    ora_start  TEXT    NOT NULL,           -- 'HH:MM'
    ora_end    TEXT    NOT NULL,           -- 'HH:MM'
    CHECK (ora_start < ora_end)
);

-- Concedii (aplicatia nu afiseaza sloturi in aceste intervale)
CREATE TABLE Concedii (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    medic_id    INTEGER NOT NULL REFERENCES Medici(id),
    data_start  TEXT    NOT NULL,          -- 'YYYY-MM-DD'
    data_end    TEXT    NOT NULL,
    CHECK (data_start <= data_end)
);

-- Programari: aplicatia le scrie cu status 'Nou', robotul le proceseaza
CREATE TABLE Programari (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    medic_id        INTEGER NOT NULL REFERENCES Medici(id),
    data            TEXT    NOT NULL,      -- 'YYYY-MM-DD'
    ora             TEXT    NOT NULL,      -- 'HH:MM'

    -- datele pacientului, asa cum au fost introduse in formular
    nume            TEXT    NOT NULL,
    data_nasterii   TEXT    NOT NULL,
    telefon         TEXT    NOT NULL,
    email           TEXT    NOT NULL,
    motiv           TEXT,
    acord_gdpr      INTEGER NOT NULL CHECK (acord_gdpr = 1),

    -- campuri folosite de robot
    status          TEXT    NOT NULL DEFAULT 'Nou'
                    CHECK (status IN ('Nou', 'In procesare', 'Email trimis', 'Confirmata',
                                      'Necesita revizuire', 'Eroare', 'Anulata')),
    urgent          INTEGER NOT NULL DEFAULT 0 CHECK (urgent IN (0, 1)),
    motiv_eroare    TEXT,
    reminder_trimis INTEGER NOT NULL DEFAULT 0 CHECK (reminder_trimis IN (0, 1)),
    creat_la        TEXT    NOT NULL DEFAULT (datetime('now')),
    confirmat_la    TEXT,

    -- confirmare / anulare de catre pacient (linkuri din email)
    token             TEXT    NOT NULL UNIQUE,
    raspuns_pacient   TEXT    CHECK (raspuns_pacient IN ('Confirmat', 'Anulat')),
    anulare_procesata INTEGER NOT NULL DEFAULT 0 CHECK (anulare_procesata IN (0, 1))
);

-- Blocheaza dublurile pe acelasi slot; o programare anulata elibereaza slotul
CREATE UNIQUE INDEX ux_programari_slot
    ON Programari (medic_id, data, ora)
    WHERE status <> 'Anulata';

CREATE INDEX ix_programari_status ON Programari (status);
CREATE INDEX ix_programari_data   ON Programari (data);

-- Jurnal pentru raportare si depanare
CREATE TABLE LogRobot (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    programare_id INTEGER REFERENCES Programari(id),
    eveniment     TEXT NOT NULL,           -- ex: 'PRELUATA', 'CONFIRMARE_TRIMISA', 'EROARE'
    detalii       TEXT,
    creat_la      TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Date de test (fictive)
INSERT INTO Medici (nume, specialitate, durata_min) VALUES
    ('Dr. A. Popescu', 'Cardiologie', 30),
    ('Dr. M. Ionescu', 'Cardiologie', 30),
    ('Dr. C. Marin',   'Dermatologie', 20);

INSERT INTO ProgramMedici (medic_id, zi_sapt, ora_start, ora_end) VALUES
    (1, 0, '09:00', '15:30'), (1, 1, '09:00', '15:30'), (1, 2, '09:00', '15:30'),
    (2, 3, '10:00', '16:00'), (2, 4, '10:00', '16:00'),
    (3, 0, '08:00', '14:00'), (3, 2, '08:00', '14:00');

-- Interogari utile
-- Programari de procesat de robot:
--   SELECT * FROM Programari WHERE status = 'Nou' ORDER BY creat_la;
-- Reminder pentru maine:
--   SELECT * FROM Programari
--   WHERE status = 'Confirmata' AND reminder_trimis = 0
--     AND data = date('now', '+1 day');