import os
from pathlib import Path
from datetime import datetime, timezone, timedelta
from flask import (Flask, render_template, request,
                   jsonify, send_from_directory)
from dotenv import load_dotenv

load_dotenv()

from database.db import (
    init_db,
    add_person, get_all_persons, get_person_by_id,
    add_class, get_all_classes, get_class_by_id,
    assign_all_students_to_class, assign_students_to_class,
    get_class_roster, is_student_in_class,
    create_session, get_sessions_for_class,
    get_session_by_id, get_active_session,
    mark_present, flag_unknown,
    get_session_report, get_session_summary, get_unknown_flags,
    get_all_encodings
)
from model.face_engine import (
    encode_face_from_bytes,
    match_face, save_student_photo,
    save_unknown_snapshot_bytes
)

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "examface_dev_secret")

WAT = timezone(timedelta(hours=1))

def nigeria_now():
    return datetime.now(WAT).strftime("%Y-%m-%d %H:%M:%S")

def nigeria_timestamp():
    return datetime.now(WAT).strftime("%Y%m%d_%H%M%S")


# ─── SESSION STATE ────────────────────────────────────────
_active_class_id   = None
_active_session_id = None
_known_people      = []


# ─── PAGES ────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/admin")
def admin():
    return render_template("admin.html",
                           persons=get_all_persons(),
                           classes=get_all_classes())


@app.route("/scan")
def scan_page():
    return render_template("scan.html",
                           classes=get_all_classes())


@app.route("/report")
def report_page():
    return render_template("report.html",
                           classes=get_all_classes())


# ─── API: PERSONS ─────────────────────────────────────────

@app.route("/api/persons", methods=["GET"])
def api_persons():
    return jsonify(get_all_persons())


@app.route("/api/persons/add", methods=["POST"])
def api_add_person():
    name   = request.form.get("name",   "").strip()
    matric = request.form.get("matric", "").strip().upper()
    photo  = request.files.get("photo")

    if not name or not matric or not photo:
        return jsonify({"error": "Name, matric and photo are all required"}), 400

    img_bytes = photo.read()
    encoding  = encode_face_from_bytes(img_bytes)

    if encoding is None:
        return jsonify({"error": "No face detected — please use a clear front-facing photo with one face only"}), 400

    photo_path = save_student_photo(img_bytes, matric)
    person_id  = add_person(name, matric, photo_path, encoding)

    return jsonify({
        "success":   True,
        "person_id": person_id,
        "message":   f"{name} registered successfully"
    })


# ─── API: CLASSES ─────────────────────────────────────────

@app.route("/api/classes", methods=["GET"])
def api_classes():
    return jsonify(get_all_classes())


@app.route("/api/classes/add", methods=["POST"])
def api_add_class():
    data        = request.get_json() or {}
    course_code = str(data.get("course_code", "")).strip().upper()
    course_name = str(data.get("course_name", "")).strip()
    lecturer    = str(data.get("lecturer",    "")).strip()

    if not course_code:
        return jsonify({"error": "Course code is required"}), 400

    class_id = add_class(course_code, course_name, lecturer)
    return jsonify({
        "success":  True,
        "class_id": class_id,
        "message":  f"Class {course_code} created"
    })


@app.route("/api/classes/<int:class_id>/assign_all", methods=["POST"])
def api_assign_all(class_id):
    count = assign_all_students_to_class(class_id)
    return jsonify({
        "success": True,
        "message": f"{count} students assigned to class"
    })


@app.route("/api/classes/<int:class_id>/assign", methods=["POST"])
def api_assign_students(class_id):
    data       = request.get_json() or {}
    person_ids = data.get("person_ids", [])
    assign_students_to_class(class_id, person_ids)
    return jsonify({
        "success": True,
        "message": f"{len(person_ids)} students assigned"
    })


@app.route("/api/classes/<int:class_id>/roster")
def api_class_roster(class_id):
    return jsonify({
        "class":    get_class_by_id(class_id),
        "students": get_class_roster(class_id)
    })


# ─── API: SESSIONS ────────────────────────────────────────

@app.route("/api/sessions/create", methods=["POST"])
def api_create_session():
    """Admin creates a session before exam day."""
    data       = request.get_json() or {}
    class_id   = data.get("class_id")
    date       = data.get("date")
    start_time = data.get("start_time")
    end_time   = data.get("end_time")

    if not all([class_id, date, start_time, end_time]):
        return jsonify({"error": "class_id, date, start_time and end_time are required"}), 400

    cls = get_class_by_id(class_id)
    if not cls:
        return jsonify({"error": "Class not found"}), 404

    session_id = create_session(class_id, date, start_time, end_time)
    return jsonify({
        "success":    True,
        "session_id": session_id,
        "message":    f"Session created for {cls['course_code']} on {date} ({start_time}–{end_time})"
    })


@app.route("/api/classes/<int:class_id>/sessions")
def api_class_sessions(class_id):
    return jsonify({
        "class":    get_class_by_id(class_id),
        "sessions": get_sessions_for_class(class_id)
    })


@app.route("/api/sessions/<int:class_id>/active")
def api_active_session(class_id):
    session = get_active_session(class_id)
    if session:
        return jsonify({"success": True, "session": session})
    return jsonify({"success": False, "message": "No active session for this class right now"})


# ─── API: SCAN ────────────────────────────────────────────

@app.route("/api/scan/start/<int:class_id>", methods=["POST"])
def api_start_scan(class_id):
    global _active_class_id, _active_session_id, _known_people

    cls = get_class_by_id(class_id)
    if not cls:
        return jsonify({"error": "Class not found"}), 404

    # Check for active session
    session = get_active_session(class_id)
    if not session:
        return jsonify({
            "error": "No active session for this class right now. Ask admin to create a session first."
        }), 400

    _active_class_id   = class_id
    _active_session_id = session["id"]
    _known_people      = get_all_encodings()

    return jsonify({
        "success":       True,
        "message":       f"Scan started for {cls['course_code']}",
        "session":       session,
        "student_count": len(_known_people)
    })


@app.route("/api/scan/stop", methods=["POST"])
def api_stop_scan():
    global _active_class_id, _active_session_id, _known_people
    _active_class_id   = None
    _active_session_id = None
    _known_people      = []
    return jsonify({"success": True, "message": "Scan session ended"})


@app.route("/api/scan/snap", methods=["POST"])
def api_snap():
    global _active_class_id, _active_session_id, _known_people

    if _active_class_id is None or _active_session_id is None:
        return jsonify({"error": "No active scan session"}), 400

    photo = request.files.get("photo")
    if not photo:
        return jsonify({"error": "No photo received"}), 400

    img_bytes = photo.read()
    encoding  = encode_face_from_bytes(img_bytes)

    if encoding is None:
        return jsonify({
            "result":  "no_face",
            "message": "No face detected — make sure face is clearly visible"
        })

    match = match_face(encoding, _known_people)

    if match:
        if not is_student_in_class(match["person_id"], _active_class_id):
            return jsonify({
                "result":  "unknown",
                "message": f"Face recognised but {match['name']} is not enrolled in this class"
            })
        mark_present(match["person_id"], _active_class_id,
                     _active_session_id, nigeria_now())
        return jsonify({
            "result":  "match",
            "message": f"Present: {match['name']} ({match['matric']})",
            "name":    match["name"],
            "matric":  match["matric"]
        })
    else:
        photo_path = save_unknown_snapshot_bytes(
            img_bytes, _active_class_id, nigeria_timestamp())
        flag_unknown(_active_class_id, _active_session_id, photo_path)
        return jsonify({
            "result":  "unknown",
            "message": "Face not recognised — snapshot saved"
        })


# ─── API: REPORTS ─────────────────────────────────────────

@app.route("/api/classes/<int:class_id>/sessions/list")
def api_sessions_list(class_id):
    """Return all sessions for a class with their attendance summary."""
    return jsonify({
        "class":    get_class_by_id(class_id),
        "sessions": get_sessions_for_class(class_id)
    })


@app.route("/api/report/session/<int:session_id>")
def api_session_report(session_id):
    session = get_session_by_id(session_id)
    if not session:
        return jsonify({"error": "Session not found"}), 404
    return jsonify({
        "session":  session,
        "class":    get_class_by_id(session["class_id"]),
        "summary":  get_session_summary(session_id),
        "students": get_session_report(session_id),
        "unknowns": get_unknown_flags(session_id)
    })


# ─── STATIC FILES ─────────────────────────────────────────

STATIC_DIR = Path(__file__).parent / "static"

@app.route("/static/photos/<path:filename>")
def serve_photo(filename):
    return send_from_directory(str(STATIC_DIR / "photos"), filename)


@app.route("/static/flags/<path:filename>")
def serve_flag(filename):
    return send_from_directory(str(STATIC_DIR / "flags"), filename)


# ─── MAIN ─────────────────────────────────────────────────

if __name__ == "__main__":
    init_db()
    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True,
        threaded=True
    )