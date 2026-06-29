import cv2
import face_recognition
import numpy as np
from typing import List, Tuple, Dict, Optional, Any
from utils.logger import setup_logger
from config import config

logger = setup_logger("face_detector")

class FaceDetector:
    def __init__(self):
        self.distance_threshold = config.FACE_DISTANCE_THRESHOLD
        logger.info(f"FaceDetector initialized with distance threshold: {self.distance_threshold}")

    def detect_faces(self, frame: np.ndarray) -> List[Tuple[int, int, int, int]]:
       
        try:
            # Resize frame for faster processing (optional, we do it at caller if needed)
            # face_recognition uses HOG detector by default on CPU
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            face_locations = face_recognition.face_locations(rgb_frame, model="hog")
            return face_locations
        except Exception as e:
            logger.error(f"Error in face detection: {e}", exc_info=True)
            return []

    def extract_encodings(self, frame: np.ndarray, face_locations: List[Tuple[int, int, int, int]]) -> List[np.ndarray]:
        
        try:
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            encodings = face_recognition.face_encodings(rgb_frame, face_locations)
            return encodings
        except Exception as e:
            logger.error(f"Error extracting face encodings: {e}", exc_info=True)
            return []

    def get_face_landmarks(self, frame: np.ndarray, face_locations: List[Tuple[int, int, int, int]]) -> List[Dict[str, List[Tuple[int, int]]]]:
       
        try:
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            landmarks = face_recognition.face_landmarks(rgb_frame, face_locations)
            return landmarks
        except Exception as e:
            logger.error(f"Error extracting landmarks: {e}")
            return []

    def distance_to_confidence(self, distance: float) -> float:
       
        if distance <= self.distance_threshold:
            # Linear mapping from 0.0 (100% confidence) to self.distance_threshold (75% confidence)
            confidence = 1.0 - (distance / self.distance_threshold) * 0.25
        else:
            # Mapping from 75% down to 0% as distance goes to 1.0
            diff = distance - self.distance_threshold
            range_left = 1.0 - self.distance_threshold
            confidence = 0.75 - (diff / range_left) * 0.75
        return float(max(0.0, min(1.0, confidence)))

    def match_face(self, unknown_encoding, known_encodings_dict):
        if not known_encodings_dict:
            print("No encodings loaded!")
            return None, 0.0

        best_student_id = None
        min_distance = 999

        for student_id, encodings in known_encodings_dict.items():
            distances = face_recognition.face_distance(encodings, unknown_encoding)

            if len(distances) == 0:
                continue

            student_min = float(np.min(distances))

            print(
                f"{student_id} -> "
                f"best={student_min:.3f} "
                f"threshold={self.distance_threshold}"
            )

            if student_min < min_distance:
                min_distance = student_min
                best_student_id = student_id

        print("BEST:", best_student_id, min_distance)

        confidence = self.distance_to_confidence(min_distance)

        if min_distance <= self.distance_threshold:
            return best_student_id, confidence

        return None, confidence
    
    
