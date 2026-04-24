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
    row  = conn.execute("SELECT * FROM person WHERE id=?", (person_id,)).fetchone()
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


# ─── ATTENDANCE ───────────────────────────────────────────

def assign_all_students_to_class(class_id):
    conn    = get_connection()
    persons = conn.execute("SELECT id FROM person").fetchall()
    for p in persons:
        conn.execute(
            """INSERT OR IGNORE INTO attendance (person_id, class_id, status)
               VALUES (?, ?, 'absent')""",
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
            """INSERT OR IGNORE INTO attendance (person_id, class_id, status)
               VALUES (?, ?, 'absent')""",
            (pid, class_id)
        )
    conn.commit()
    conn.close()

def get_class_roster(class_id):
    """
    Return all students assigned to a class
    regardless of attendance status.
    """
    conn = get_connection()
    rows = conn.execute(
        """SELECT p.id, p.name, p.matric, p.photo_path
           FROM attendance a
           JOIN person p ON p.id = a.person_id
           WHERE a.class_id = ?
           ORDER BY p.name""",
        (class_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def mark_present(person_id, class_id, marked_at=None):
    if marked_at is None:
        marked_at = nigeria_now()
    conn = get_connection()
    conn.execute(
        """UPDATE attendance SET status='present', marked_at=?
           WHERE person_id=? AND class_id=?""",
        (marked_at, person_id, class_id)
    )
    conn.commit()
    conn.close()


def is_student_in_class(person_id, class_id):
    conn = get_connection()
    row  = conn.execute(
        "SELECT id FROM attendance WHERE person_id=? AND class_id=?",
        (person_id, class_id)
    ).fetchone()
    conn.close()
    return row is not None


def flag_unknown(class_id, photo_path):
    conn = get_connection()
    conn.execute(
        "INSERT INTO unknown_flag (class_id, photo_path) VALUES (?,?)",
        (class_id, photo_path)
    )
    conn.commit()
    conn.close()


# ─── REPORTS ──────────────────────────────────────────────

def get_attendance_report(class_id):
    conn = get_connection()
    rows = conn.execute(
        """SELECT p.name, p.matric, p.photo_path,
                  a.status, a.marked_at
           FROM attendance a
           JOIN person p ON p.id = a.person_id
           WHERE a.class_id = ?
           ORDER BY p.name""",
        (class_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_filtered_report(class_id, date=None, start_time=None, end_time=None):
    """
    Get attendance filtered by date and time range.
    Absent students always show regardless of filter.
    """
    conn = get_connection()

    query = """
        SELECT p.name, p.matric, p.photo_path,
               a.status, a.marked_at
        FROM attendance a
        JOIN person p ON p.id = a.person_id
        WHERE a.class_id = ?
        AND (
            a.status = 'absent'
            OR (
                1=1
    """
    params = [class_id]

    if date:
        query += " AND DATE(a.marked_at) = ?"
        params.append(date)

    if start_time and date:
        query += " AND TIME(a.marked_at) >= ?"
        params.append(start_time + ":00")

    if end_time and date:
        query += " AND TIME(a.marked_at) <= ?"
        params.append(end_time + ":00")

    query += ")) ORDER BY p.name"

    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_attendance_summary(class_id):
    conn = get_connection()
    row  = conn.execute(
        """SELECT
             COUNT(*) as total,
             SUM(CASE WHEN status='present' THEN 1 ELSE 0 END) as present,
             SUM(CASE WHEN status='absent'  THEN 1 ELSE 0 END) as absent
           FROM attendance WHERE class_id=?""",
        (class_id,)
    ).fetchone()
    conn.close()
    return dict(row)


def get_unknown_flags(class_id):
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM unknown_flag WHERE class_id=? ORDER BY flagged_at DESC",
        (class_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]