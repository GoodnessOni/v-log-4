# ExamFace 📷
### Facial Recognition Exam Attendance System

A smart, portable attendance system built with Python and Flask that uses facial recognition to mark students present during exams. Designed to run on a Raspberry Pi 4 with lecturers controlling everything from their phone browser.

---

## How It Works

1. **Admin registers students** — uploads a clear photo of each student. The system encodes the face into 128 unique numbers and stores them.
2. **Admin creates exam sessions** — sets the class, date, start time and end time for each exam.
3. **On exam day** — lecturer opens the system on their phone browser, selects the class, and the active session is detected automatically.
4. **Students are scanned** — lecturer points their phone camera at each student and taps Snap. The system matches the face against the database in under a second.
5. **Report is generated** — full attendance list per session, printable with invigilator signature line.

---

## Features

- 📷 **Browser-based camera** — uses the lecturer's phone camera, no dedicated hardware needed per hall
- 🧠 **Facial recognition** — powered by `face_recognition` (dlib) with HOG model for CPU efficiency
- 🕐 **Session-based attendance** — each exam sitting is a separate session, no data mixing between dates
- 📋 **Per-session reports** — view and print attendance for any past session
- 👥 **Class roster** — view all students assigned to a class with their photos, printable
- ❓ **Unknown face flagging** — unrecognised faces are photographed and saved for review
- 📱 **Mobile-first UI** — fully responsive, works on any phone browser
- 🔒 **Enrolment check** — recognised faces are verified against the class roster before being marked present
- 🇳🇬 **Nigeria timezone** — all times recorded in WAT (UTC+1)

---

## System Architecture

```
Raspberry Pi 4
├── Runs Flask web server (app.py)
├── Stores SQLite database (student records, sessions, attendance)
└── Connected to campus/hall WiFi router

Lecturer's Phone
├── Opens browser → http://pi-address:5000
├── Controls scanning (Start, Snap, Stop)
└── Views and prints reports

Phone Camera
└── Captures student face → sends to Pi → Pi matches → marks present
```

---

## Folder Structure

```
examface/
├── app.py                  ← Flask app (main entry point)
├── requirements.txt        ← Python dependencies
├── .env                    ← Environment variables (not committed)
├── database/
│   ├── schema.sql          ← Table definitions
│   ├── db.py               ← All database functions
│   └── attendance.db       ← Auto-created on first run (not committed)
├── model/
│   └── face_engine.py      ← Face recognition logic
├── static/
│   ├── css/main.css
│   ├── js/main.js
│   ├── photos/             ← Student registration photos (not committed)
│   └── flags/              ← Unknown face snapshots (not committed)
└── templates/
    ├── base.html
    ├── index.html
    ├── admin.html
    ├── scan.html
    └── report.html
```

---

## Database Tables

```sql
person        -- registered students (name, matric, photo, face encoding)
class         -- course records (code, name, lecturer)
session       -- each exam sitting (class, date, start time, end time)
attendance    -- per-student per-session status (absent/present)
unknown_flag  -- snapshots of unrecognised faces per session
```

---

## Installation

### On Laptop (Windows) — for development and testing

```bash
# Clone the repository
git clone https://github.com/GoodnessOni/v-log-4.git examface
cd examface

# Create and activate virtual environment
python -m venv venv
venv\Scripts\activate

# Install dependencies (dlib compiles from source — takes ~5 mins)
pip install flask opencv-python-headless numpy pillow python-dotenv
pip install face-recognition

# Create .env file
echo SECRET_KEY=examface_secret_2024 > .env

# Create required folders
mkdir static\photos
mkdir static\flags

# Run the app
python app.py
```

Open `http://localhost:5000` in your browser.

---

### On Raspberry Pi 4 — for deployment

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install system dependencies
sudo apt install -y python3-pip cmake build-essential \
  libopenblas-dev liblapack-dev libhdf5-dev \
  libjpeg-dev libpng-dev libavcodec-dev \
  libavformat-dev libswscale-dev

# Install dlib first (takes 15-20 minutes — compiles from source)
pip install dlib --break-system-packages

# Install remaining packages
pip install flask opencv-python-headless numpy pillow \
  python-dotenv face-recognition --break-system-packages

# Clone the repository
cd ~
git clone https://github.com/GoodnessOni/v-log-4.git examface
cd examface

# Create .env file
echo "SECRET_KEY=examface_secret_2024
CAMERA_SOURCE=0" > .env

# Create required folders
mkdir -p static/photos static/flags

# Run the app
python app.py
```

Access from any device on the same network: `http://pi-ip-address:5000`

---

### Autostart on Boot (Raspberry Pi)

```bash
sudo nano /etc/systemd/system/examface.service
```

Paste:
```
[Unit]
Description=ExamFace Attendance System
After=network.target

[Service]
User=v-log-4
WorkingDirectory=/home/v-log-4/examface
ExecStart=/usr/bin/python3 app.py
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable examface
sudo systemctl start examface
```

---

## Usage — Step by Step

### Before Exam Day (Admin)

1. Go to `/admin` → **Students tab**
   - Enter student name and matric number
   - Upload a clear, front-facing photo (one face only)
   - Click Register

2. Go to **Classes tab**
   - Create the course (e.g. GEG 213, Engineering Maths, Dr. Oni)
   - Create an exam session — set date, start time, end time

3. Go to **Assign Roster tab**
   - Select the class
   - Choose which students are sitting that exam
   - Click Assign Selected

### On Exam Day (Lecturer)

1. Open browser on phone → `http://pi-ip:5000/scan`
2. Select the class — active session appears automatically
3. Click **Start Scan** — camera opens
4. Point camera at each student → tap **📷 Snap Face**
   - ✅ Green = Present, student marked
   - ❌ Red = Not recognised or not enrolled
   - 🟡 Yellow = No face detected
5. Click **Stop Scan** when done

### After Exam (Lecturer/Admin)

1. Go to `/report`
2. Select the class → list of all sessions appears
3. Tap the session → full attendance list loads
4. Click **Print** for paper copy

---

## Hardware Requirements

| Item | Spec | Purpose |
|---|---|---|
| Raspberry Pi 4 | 4GB RAM | Runs the server |
| MicroSD Card | 32GB Class 10 | Operating system + app |
| USB-C Power Supply | 5V/3A | Powers the Pi |
| USB Webcam (optional) | Any | Registration photos |
| WiFi Router | Any | Connects Pi and phones |
| Lecturer's Phone | Any browser | Controls scanning |

> The Pi webcam is only needed for student registration photos. Exam day scanning uses the lecturer's phone camera.

---

## Performance Notes

- Face matching: ~0.5–1 second per student on Pi 4
- Tolerance: `0.45` (strict — reduces false positives)
- Image resize: max 800px before processing (saves computation)
- Encodings cached in RAM at session start — no database reads during scanning

---

## Environment Variables

```env
SECRET_KEY=your_secret_key_here
CAMERA_SOURCE=0
```

`CAMERA_SOURCE=0` uses the default USB webcam. For an IP camera use the full URL.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3, Flask |
| Face Recognition | face_recognition, dlib (HOG model) |
| Camera | OpenCV, Browser MediaDevices API |
| Database | SQLite |
| Frontend | HTML, CSS, Vanilla JavaScript |
| Deployment | Raspberry Pi 4, systemd |

---

## Planned Features

- [ ] Login system (admin vs lecturer roles)
- [ ] Bulk student import from CSV
- [ ] Central database server for multi-hall deployment
- [ ] SMS/email alerts for unknown faces
- [ ] Export attendance to Excel

---

## Author

**Goodness Oni** — [@GoodnessOni](https://github.com/GoodnessOni)

Built as a practical solution for Nigerian university exam attendance management.

---

## License

MIT License — free to use, modify and distribute.
