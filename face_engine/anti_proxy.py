import time
import numpy as np
from typing import List, Tuple, Dict, Optional, Any
from utils.logger import setup_logger
from config import config

logger = setup_logger("anti_proxy")

class TrackedFace:
    def __init__(self, face_id: int, bbox: Tuple[int, int, int, int]):
        self.face_id = face_id
        self.bbox = bbox  # (top, right, bottom, left)
        self.centroid = self._calculate_centroid(bbox)
        
        # History arrays
        self.bboxes: List[Tuple[int, int, int, int]] = [bbox]
        self.centroids: List[Tuple[int, int]] = [self.centroid]
        self.student_ids: List[Optional[str]] = []
        self.confidences: List[float] = []
        self.timestamps: List[float] = [time.time()]
        
        self.is_marked = False
        self.marked_student_id: Optional[str] = None
        self.verification_start_time = time.time()

    def _calculate_centroid(self, bbox: Tuple[int, int, int, int]) -> Tuple[int, int]:
        top, right, bottom, left = bbox
        return (int((left + right) / 2), int((top + bottom) / 2))

    def update(self, bbox: Tuple[int, int, int, int]):
        """Update tracked face with new frame data."""
        self.bbox = bbox
        self.centroid = self._calculate_centroid(bbox)
        self.bboxes.append(bbox)
        self.centroids.append(self.centroid)
        self.timestamps.append(time.time())
        
        # Keep history window capped to twice the minimum verification frames
        max_window = config.MIN_VERIFICATION_FRAMES * 2
        if len(self.bboxes) > max_window:
            self.bboxes.pop(0)
            self.centroids.pop(0)
            self.timestamps.pop(0)
            if self.student_ids:
                self.student_ids.pop(0)
            if self.confidences:
                self.confidences.pop(0)

    def add_match(self, student_id: Optional[str], confidence: float):
        """Record face recognition results for current frame."""
        self.student_ids.append(student_id)
        self.confidences.append(confidence)
        
        max_window = config.MIN_VERIFICATION_FRAMES * 2
        if len(self.student_ids) > max_window:
            self.student_ids.pop(0)
            self.confidences.pop(0)

    @property
    def tracking_duration(self) -> float:
        return time.time() - self.verification_start_time

    @property
    def frame_count(self) -> int:
        return len(self.student_ids)


class AntiProxyEngine:
    def __init__(self):
        self.tracked_faces: List[TrackedFace] = []
        self.next_face_id = 0
        self.max_distance = 120.0  # Max distance in pixels to match face between frames

    def track_faces(self, current_bboxes: List[Tuple[int, int, int, int]]) -> List[TrackedFace]:
        """
        Track faces across frames using nearest‑neighbour centroid matching.
        """
        # Compute centroids for all current detections
        current_centroids = []
        for bbox in current_bboxes:
            top, right, bottom, left = bbox
            centroid = (int((left + right) / 2), int((top + bottom) / 2))
            current_centroids.append(centroid)

        updated_faces = []
        used_detections = set()          # indices of current_bboxes already assigned
        matched_faces = set()            # TrackedFace objects already updated

        # 1. Match each detection to the closest existing face
        for det_idx, (bbox, centroid) in enumerate(zip(current_bboxes, current_centroids)):
            best_face = None
            best_dist = float('inf')

            for face in self.tracked_faces:
                if face in matched_faces:
                    continue
                dist = np.sqrt(
                    (face.centroid[0] - centroid[0]) ** 2 +
                    (face.centroid[1] - centroid[1]) ** 2
                )
                if dist < best_dist and dist < self.max_distance:
                    best_dist = dist
                    best_face = face

            if best_face is not None:
                # Reuse existing face
                best_face.update(bbox)
                updated_faces.append(best_face)
                matched_faces.add(best_face)
                used_detections.add(det_idx)
                print(f"[TRACK] Reused Face #{best_face.face_id} "
                      f"centroid={best_face.centroid} "
                      f"history={len(best_face.student_ids)}")
            else:
                # No close face → create new
                new_face = TrackedFace(self.next_face_id, bbox)
                self.next_face_id += 1
                updated_faces.append(new_face)
                used_detections.add(det_idx)
                print(f"[TRACK] NEW Face #{new_face.face_id} "
                      f"bbox={bbox}")

        # 2. Handle unmatched existing faces (coast or drop)
        for face in self.tracked_faces:
            if face in matched_faces:
                continue
            # Keep the face if it was updated recently (coasting)
            if time.time() - face.timestamps[-1] < 0.5:
                updated_faces.append(face)

        # 3. (Safety) create new faces for any detections not assigned
        for idx, bbox in enumerate(current_bboxes):
            if idx not in used_detections:
                new_face = TrackedFace(self.next_face_id, bbox)
                self.next_face_id += 1
                updated_faces.append(new_face)
                print(f"[TRACK] NEW Face (fallback) #{new_face.face_id} bbox={bbox}")

        self.tracked_faces = updated_faces
        return self.tracked_faces

    def analyze_proxy_risk(self, face: TrackedFace, total_faces_in_frame: int) -> Dict[str, Any]:
        
        if face.frame_count < 3:
            return {
                "proxy_risk_score": 0.0,
                "stability_score": 50.0,
                "photo_spoof_suspect": False,
                "multi_face_suspect": False,
                "unstable_recognition": False
            }

        # 1. Bounding box micro-movements (Stability Score)
        # Check standard deviation of centroid coordinates.
        # Static photos will show standard deviations extremely close to 0.
        centroids_arr = np.array(face.centroids)
        std_x = np.std(centroids_arr[:, 0])
        std_y = np.std(centroids_arr[:, 1])
        overall_std = np.sqrt(std_x**2 + std_y**2)

        # Map centroid standard deviation to a stability metric
        # A normal face has micro-movements, so std dev is typically between 0.3 and 10 pixels.
        # If it is EXACTLY 0 or less than 0.1, it's highly suspect (photo spoof).
        photo_spoof_suspect = overall_std < 0.02
        
        # Stability of dimensions
        widths = [r - l for _, r, _, l in face.bboxes]
        std_w = np.std(widths)

        if overall_std < 0.02 and std_w < 0.02:
            photo_spoof_suspect = True
        else:
            photo_spoof_suspect = False

        # 2. Recognition Stability
        # Check consistency of matched student IDs in history window.
        valid_ids = [sid for sid in face.student_ids if sid is not None]
        if not valid_ids:
            recognition_stability = 0.0
            unstable_recognition = True
            most_frequent_id = None
        else:
            # Find the most common student ID in the window
            unique_ids, counts = np.unique(valid_ids, return_counts=True)
            most_frequent_id = unique_ids[np.argmax(counts)]
            match_ratio = np.max(counts) / len(face.student_ids)
            recognition_stability = match_ratio * 100.0
            unstable_recognition = match_ratio < 0.70

        # 3. Multi-Face Detection Penalty
        # If multiple faces are detected, increase risk
        multi_face_suspect = total_faces_in_frame > config.MAX_FACES_ALLOWED

        # Compute Proxy Risk Score (0 - 100)
        risk_components = []
        
        # Photo spoofing risk
        if photo_spoof_suspect:
            risk_components.append(85.0)  # Very high risk if box is static
        else:
            # Map low movements to higher risk smoothly
            if overall_std < 0.4:
                risk_components.append((0.4 - overall_std) / 0.4 * 50)
            else:
                risk_components.append(0.0)

        # Multi face risk
        if multi_face_suspect:
            risk_components.append(75.0)
        else:
            risk_components.append(0.0)

        # Recognition instability risk
        instability_risk = (100.0 - recognition_stability) * 0.6
        risk_components.append(instability_risk)

        proxy_risk_score = min(100.0, np.max(risk_components))
        
        # Stability Score is inverse of jitter + recognition stability
        # A good stability score is high (80-100) when movements are micro but consistent and recognition is stable
        stability_score = float(recognition_stability)

        return {
            "proxy_risk_score": float(round(proxy_risk_score, 1)),
            "stability_score": float(round(stability_score, 1)),
            "photo_spoof_suspect": bool(photo_spoof_suspect),
            "multi_face_suspect": bool(multi_face_suspect),
            "unstable_recognition": bool(unstable_recognition),
            "micro_movement_std": float(overall_std),
            "candidate_student_id": most_frequent_id
        }

    def verify_face_for_attendance(self, face: TrackedFace, total_faces_in_frame: int) -> Tuple[bool, Optional[str], float, str]:
      
        # 1. Require minimum frame window
        if face.frame_count < config.MIN_VERIFICATION_FRAMES:
            remaining = config.MIN_VERIFICATION_FRAMES - face.frame_count
            return False, face.student_ids[-1] if face.student_ids else None, 0.0, f"Analyzing (gather {remaining} more frames...)"

        # 2. Check risk metrics
        risk_analysis = self.analyze_proxy_risk(face, total_faces_in_frame)

        candidate_student_id = risk_analysis["candidate_student_id"]
        avg_confidence = np.mean(face.confidences) if face.confidences else 0.0

        if risk_analysis["photo_spoof_suspect"]:
            return False, candidate_student_id, avg_confidence, "Proxy Warning: Static Photo Suspected"

        if risk_analysis["multi_face_suspect"]:
            return False, candidate_student_id, avg_confidence, "Proxy Warning: Multiple Faces Detected"

        if risk_analysis["unstable_recognition"]:
            return False, candidate_student_id, avg_confidence, "Analyzing (unstable tracking)"

        # 3. Check matched student ID
        if not candidate_student_id:
            return False, None, 0.0, "Unknown Face"

        # 4. Check confidence average
        if avg_confidence < config.MIN_CONFIDENCE_THRESHOLD:
            return False, candidate_student_id, avg_confidence, f"Low matching confidence ({int(avg_confidence*100)}%)"

        # 5. Check tracking duration (duration verification)
        if face.tracking_duration < config.VERIFICATION_WINDOW_SECONDS:
            rem = round(config.VERIFICATION_WINDOW_SECONDS - face.tracking_duration, 1)
            return False, candidate_student_id, avg_confidence, f"Verifying presence (hold still for {rem}s)"

        # All checks passed!
        status_msg = "VERIFIED"
        if risk_analysis["proxy_risk_score"] > 35.0:
            status_msg = "PROXY_SUSPECT"

        print(risk_analysis)
        return True, candidate_student_id, float(avg_confidence), status_msg