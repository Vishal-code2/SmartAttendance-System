import os
from pathlib import Path

try:
    from dotenv import load_dotenv
except ModuleNotFoundError:
    def load_dotenv(*args, **kwargs):
        return False

# Load env variables if .env file exists
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

# Directories
DATA_DIR = BASE_DIR / "data"
PHOTO_DIR = DATA_DIR / "student_photos"
LOG_DIR = BASE_DIR / "logs"
EXPORT_DIR = BASE_DIR / "exports"
MODELS_DIR = BASE_DIR / "models"

# Ensure directories exist
for directory in [DATA_DIR, PHOTO_DIR, LOG_DIR, EXPORT_DIR, MODELS_DIR]:
    directory.mkdir(parents=True, exist_ok=True)

# Database Configuration
DB_PATH = os.getenv("DB_PATH", str(DATA_DIR / "smart_attend.db"))

# Camera Configuration
CAMERA_INDEX = int(os.getenv("CAMERA_INDEX", 0))

# Face Recognition Settings
FACE_DISTANCE_THRESHOLD = float(os.getenv("FACE_DISTANCE_THRESHOLD", 0.55))
MIN_VERIFICATION_FRAMES = int(os.getenv("MIN_VERIFICATION_FRAMES", 8))
VERIFICATION_WINDOW_SECONDS = float(os.getenv("VERIFICATION_WINDOW_SECONDS", 3.0))
MIN_CONFIDENCE_THRESHOLD = float(os.getenv("MIN_CONFIDENCE_THRESHOLD", 0.70))

# Liveness / Anti-Proxy Settings
STABILITY_MAX_DEVIATION = float(os.getenv("STABILITY_MAX_DEVIATION", 15.0)) # pixels
MAX_FACES_ALLOWED = 1 # Only 1 face in frame to mark attendance, preventing side-by-side proxy attempts

# Attendance Settings
ATTENDANCE_RISK_THRESHOLD = 0.75  # 75% attendance threshold

# Logging Configuration
LOG_FILE = os.getenv("LOG_FILE", str(LOG_DIR / "app.log"))
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# App Version
VERSION = "1.0.0"
APP_NAME = "SmartAttend AI"
