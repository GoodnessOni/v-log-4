CREATE TABLE IF NOT EXISTS person (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT    NOT NULL,
    matric      TEXT    NOT NULL UNIQUE,
    photo_path  TEXT,
    encoding    BLOB    NOT NULL,
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS class (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    course_code TEXT    NOT NULL UNIQUE,
    course_name TEXT,
    lecturer    TEXT,
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS session (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    class_id    INTEGER NOT NULL,
    date        TEXT    NOT NULL,
    start_time  TEXT    NOT NULL,
    end_time    TEXT    NOT NULL,
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (class_id) REFERENCES class(id)
);

CREATE TABLE IF NOT EXISTS attendance (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    person_id   INTEGER NOT NULL,
    class_id    INTEGER NOT NULL,
    session_id  INTEGER NOT NULL,
    status      TEXT    DEFAULT 'absent',
    marked_at   DATETIME,
    FOREIGN KEY (person_id)  REFERENCES person(id),
    FOREIGN KEY (class_id)   REFERENCES class(id),
    FOREIGN KEY (session_id) REFERENCES session(id),
    UNIQUE(person_id, session_id)
);

CREATE TABLE IF NOT EXISTS unknown_flag (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    class_id    INTEGER NOT NULL,
    session_id  INTEGER,
    photo_path  TEXT,
    flagged_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (class_id)   REFERENCES class(id),
    FOREIGN KEY (session_id) REFERENCES session(id)
);