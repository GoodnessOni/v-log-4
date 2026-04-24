import face_recognition
import cv2
import numpy as np
from pathlib import Path
from PIL import Image
import io

BASE_DIR   = Path(__file__).parent.parent
PHOTOS_DIR = BASE_DIR / "static" / "photos"
FLAGS_DIR  = BASE_DIR / "static" / "flags"

PHOTOS_DIR.mkdir(parents=True, exist_ok=True)
FLAGS_DIR.mkdir(parents=True, exist_ok=True)

TOLERANCE = 0.45
MAX_SIZE  = 800


def resize_image(img_array):
    h, w = img_array.shape[:2]
    if max(h, w) <= MAX_SIZE:
        return img_array
    scale = MAX_SIZE / max(h, w)
    return cv2.resize(img_array, (int(w * scale), int(h * scale)))


def encode_face_from_bytes(img_bytes):
    """Used during registration — takes uploaded photo bytes."""
    pil_img   = Image.open(io.BytesIO(img_bytes)).convert("RGB")
    img_array = np.array(pil_img)
    img_array = resize_image(img_array)

    face_locations = face_recognition.face_locations(img_array, model="hog")

    if len(face_locations) != 1:
        return None

    return face_recognition.face_encodings(img_array, face_locations)[0]


def encode_face_from_camera(frame):
    """Used during scanning — takes an OpenCV frame."""
    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    rgb_frame = resize_image(rgb_frame)

    face_locations = face_recognition.face_locations(rgb_frame, model="hog")

    if len(face_locations) != 1:
        return None, None

    encodings = face_recognition.face_encodings(rgb_frame, face_locations)
    return encodings[0], face_locations[0]


def match_face(unknown_encoding, known_people):
    """Compare unknown face against all known students."""
    if not known_people:
        return None

    known_encodings = [p["encoding"] for p in known_people]
    matches         = face_recognition.compare_faces(
                          known_encodings, unknown_encoding, tolerance=TOLERANCE)
    distances       = face_recognition.face_distance(known_encodings, unknown_encoding)

    if not any(matches):
        return None

    best_index = int(np.argmin(distances))
    return known_people[best_index] if matches[best_index] else None


def save_student_photo(img_bytes, matric):
    """Save registration photo, return relative path."""
    filename = f"{matric}.jpg"
    filepath = PHOTOS_DIR / filename
    pil_img  = Image.open(io.BytesIO(img_bytes)).convert("RGB")
    pil_img.thumbnail((600, 600))
    pil_img.save(filepath, "JPEG", quality=85)
    return f"photos/{filename}"


def save_unknown_snapshot(frame, class_id, timestamp):
    """Save unknown face frame from webcam."""
    filename  = f"unknown_{class_id}_{timestamp}.jpg"
    filepath  = FLAGS_DIR / filename
    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    pil_img   = Image.fromarray(rgb_frame)
    pil_img.thumbnail((400, 400))
    pil_img.save(filepath, "JPEG", quality=80)
    return f"flags/{filename}"


def open_camera(source=0):
    """Open webcam by index or URL."""
    cap = cv2.VideoCapture(source)
    if not cap.isOpened():
        raise RuntimeError(f"Could not open camera: {source}")
    return cap


def snap_frame(cap):
    """Grab exactly one frame from the webcam."""
    ret, frame = cap.read()
    if not ret:
        raise RuntimeError("Failed to read frame from camera")
    return frame


def generate_preview_stream(cap):
    """
    Yields MJPEG frames for the preview window on the scan page.
    This is just a raw camera feed — no face recognition running here.
    Lightweight, just so the lecturer can see the student is in frame.
    """
    while True:
        ret, frame = cap.read()
        if not ret:
            break

        # Flip horizontally so it feels like a mirror
        frame = cv2.flip(frame, 1)

        _, buffer = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
        yield (b"--frame\r\n"
               b"Content-Type: image/jpeg\r\n\r\n" +
               buffer.tobytes() + b"\r\n")
        
def save_unknown_snapshot_bytes(img_bytes, class_id, timestamp):
    """
    Save unknown face snapshot received as bytes from browser camera.
    """
    filename = f"unknown_{class_id}_{timestamp}.jpg"
    filepath = FLAGS_DIR / filename
    pil_img  = Image.open(io.BytesIO(img_bytes)).convert("RGB")
    pil_img.thumbnail((400, 400))
    pil_img.save(filepath, "JPEG", quality=80)
    return f"flags/{filename}"