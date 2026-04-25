import sqlite3
import numpy as np
import json
from pathlib import Path
from datetime import datetime, timezone, timedelta

BASE_DIR = Path(__file__).parent
DB_PATH  = BASE_DIR / "attendance.db"
SCHEMA   = BASE_DIR / "schema.sql"

WAT = timezone(timedelta(hours=1))

def nigeria_now():
    return datetime.now(WAT).strftime("%Y-%m-%d %H:%M:%S")

def nigeria_today():
    return datetime.now(WAT).strftime("%Y-%m-%d")

def nigeria_time():
    return datetime.now(WAT).strftime("%H:%M")


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()
    with open(SCHEMA, "r") as f:
        conn.executescript(f.read())
    conn.commit()
    conn.close()


# ─── PERSONS ──────────────────────────────────────────────

def add_person(name, matric, photo_path, encoding):
    encoding_json = json.dumps(encoding.tolist())
    conn = get_connection()
    cursor = conn.execute(
        "INSERT INTO person (name, matric, photo_path, encoding) VALUES (?,?,?,?)",
        (name, matric, photo_path, encoding_json)
    )
    person_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return person_id


def get_all_persons():
    conn = get_connection()
    rows = conn.execute(
        "SELECT id, name, matric, photo_path, created_at FROM person ORDER BY name"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_person_by_id(person_id):
    conn = get_connection()
    row  = conn.execute(
        "SELECT * FROM person WHERE id=?", (person_id,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def get_all_encodings():
    conn = get_connection()
    rows = conn.execute(
        "SELECT id, name, matric, encoding FROM person"
    ).fetchall()
    conn.close()
    result = []
    for r in rows:
        encoding = np.array(json.loads(r["encoding"]))
        result.append({
            "person_id": r["id"],
            "name":      r["name"],
            "matric":    r["matric"],
            "encoding":  encoding
        })
    return result


# ─── CLASSES ──────────────────────────────────────────────

def add_class(course_code, course_name, lecturer):
    conn = get_connection()
    cursor = conn.execute(
        "INSERT INTO class (course_code, course_name, lecturer) VALUES (?,?,?)",
        (course_code, course_name, lecturer)
    )
    class_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return class_id


def get_all_classes():
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM class ORDER BY created_at DESC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_class_by_id(class_id):
    conn = get_connection()
    row  = conn.execute(
        "SELECT * FROM class WHERE id=?", (class_id,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def get_class_roster(class_id):
    conn = get_connection()
    rows = conn.execute(
        """SELECT DISTINCT p.id, p.name, p.matric, p.photo_path
           FROM person p
           WHERE p.id IN (
               SELECT DISTINCT person_id FROM attendance WHERE class_id=?
           )
           ORDER BY p.name""",
        (class_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ─── SESSIONS ─────────────────────────────────────────────

def create_session(class_id, date, start_time, end_time):
    """Create a new exam session for a class."""
    conn = get_connection()
    cursor = conn.execute(
        """INSERT INTO session (class_id, date, start_time, end_time)
           VALUES (?,?,?,?)""",
        (class_id, date, start_time, end_time)
    )
    session_id = cursor.lastrowid

    # Auto-assign all students in this class to this session as absent
    persons = conn.execute(
        """SELECT DISTINCT person_id FROM attendance
           WHERE class_id=?""",
        (class_id,)
    ).fetchall()

    for p in persons:
        conn.execute(
            """INSERT OR IGNORE INTO attendance
               (person_id, class_id, session_id, status)
               VALUES (?,?,?,'absent')""",
            (p["person_id"], class_id, session_id)
        )

    conn.commit()
    conn.close()
    return session_id


def get_sessions_for_class(class_id):
    """Get all sessions for a class, newest first."""
    conn = get_connection()
    rows = conn.execute(
        """SELECT s.*,
             (SELECT COUNT(*) FROM attendance a
              WHERE a.session_id=s.id AND a.status='present') as present_count,
             (SELECT COUNT(*) FROM attendance a
              WHERE a.session_id=s.id) as total_count
           FROM session s
           WHERE s.class_id=?
           ORDER BY s.date DESC, s.start_time DESC""",
        (class_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_session_by_id(session_id):
    conn = get_connection()
    row  = conn.execute(
        "SELECT * FROM session WHERE id=?", (session_id,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def get_active_session(class_id):
    """
    Find a session for this class that is active right now
    based on today's date and current time.
    """
    today = nigeria_today()
    now   = nigeria_time()
    conn  = get_connection()
    row   = conn.execute(
        """SELECT * FROM session
           WHERE class_id=?
           AND date=?
           AND start_time <= ?
           AND end_time >= ?""",
        (class_id, today, now, now)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


# ─── ATTENDANCE ───────────────────────────────────────────

def assign_all_students_to_class(class_id):
    """Add every registered student to a class roster."""
    conn    = get_connection()
    persons = conn.execute("SELECT id FROM person").fetchall()

    # We just need one attendance record to track class membership
    # Session-specific records are created when sessions start
    for p in persons:
        conn.execute(
            """INSERT OR IGNORE INTO attendance
               (person_id, class_id, session_id, status)
               VALUES (?,?, -1, 'roster')""",
            (p["id"], class_id)
        )
    count = len(persons)
    conn.commit()
    conn.close()
    return count


def assign_students_to_class(class_id, person_ids):
    conn = get_connection()
    for pid in person_ids:
        conn.execute(
            """INSERT OR IGNORE INTO attendance
               (person_id, class_id, session_id, status)
               VALUES (?,?, -1, 'roster')""",
            (pid, class_id)
        )
    conn.commit()
    conn.close()


def is_student_in_class(person_id, class_id):
    conn = get_connection()
    row  = conn.execute(
        """SELECT id FROM attendance
           WHERE person_id=? AND class_id=?""",
        (person_id, class_id)
    ).fetchone()
    conn.close()
    return row is not None


def mark_present(person_id, class_id, session_id, marked_at=None):
    if marked_at is None:
        marked_at = nigeria_now()
    conn = get_connection()
    conn.execute(
        """INSERT INTO attendance (person_id, class_id, session_id, status, marked_at)
           VALUES (?,?,?,'present',?)
           ON CONFLICT(person_id, session_id) DO UPDATE SET
           status='present', marked_at=excluded.marked_at""",
        (person_id, class_id, session_id, marked_at)
    )
    conn.commit()
    conn.close()


def flag_unknown(class_id, session_id, photo_path):
    conn = get_connection()
    conn.execute(
        """INSERT INTO unknown_flag (class_id, session_id, photo_path)
           VALUES (?,?,?)""",
        (class_id, session_id, photo_path)
    )
    conn.commit()
    conn.close()


# ─── REPORTS ──────────────────────────────────────────────

def get_session_report(session_id):
    """Full attendance list for one session."""
    conn = get_connection()
    rows = conn.execute(
        """SELECT p.name, p.matric, p.photo_path,
                  a.status, a.marked_at
           FROM attendance a
           JOIN person p ON p.id = a.person_id
           WHERE a.session_id = ?
           AND a.status != 'roster'
           ORDER BY p.name""",
        (session_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_session_summary(session_id):
    conn = get_connection()
    row  = conn.execute(
        """SELECT
             COUNT(*) as total,
             SUM(CASE WHEN status='present' THEN 1 ELSE 0 END) as present,
             SUM(CASE WHEN status='absent'  THEN 1 ELSE 0 END) as absent
           FROM attendance
           WHERE session_id=? AND status != 'roster'""",
        (session_id,)
    ).fetchone()
    conn.close()
    return dict(row)


def get_unknown_flags(session_id):
    conn = get_connection()
    rows = conn.execute(
        """SELECT * FROM unknown_flag
           WHERE session_id=?
           ORDER BY flagged_at DESC""",
        (session_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]