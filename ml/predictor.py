import os
import random
import datetime
import joblib
import pandas as pd
import numpy as np
from typing import List, Tuple, Dict, Any, Optional
from sklearn.ensemble import RandomForestClassifier
from config import config
from utils.logger import setup_logger
from models.student import Student
from models.risk import RiskAssessment

logger = setup_logger("ml_predictor")

class RiskPredictor:
    def __init__(self, model_path: str = str(config.MODELS_DIR / "risk_predictor.joblib")):
        self.model_path = model_path
        self.model: Optional[RandomForestClassifier] = None
        self.load_model()

    def load_model(self) -> bool:
        """Load the trained Random Forest model from disk."""
        if os.path.exists(self.model_path):
            try:
                self.model = joblib.load(self.model_path)
                logger.info("Successfully loaded ML model from disk.")
                return True
            except Exception as e:
                logger.error(f"Failed to load ML model: {e}")
        self.model = None
        return False

    def save_model(self) -> bool:
        """Save the trained Random Forest model to disk."""
        if self.model is None:
            logger.error("No model exists to save.")
            return False
        try:
            os.makedirs(os.path.dirname(self.model_path), exist_ok=True)
            joblib.dump(self.model, self.model_path)
            logger.info(f"ML model saved successfully at {self.model_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to save ML model: {e}")
            return False

    def train_model(self, X: pd.DataFrame, y: pd.Series) -> bool:
        """Train the Random Forest model with engineered features."""
        logger.info(f"Training risk predictor with {len(X)} training samples.")
        try:
            self.model = RandomForestClassifier(n_estimators=50, random_state=42, max_depth=6)
            self.model.fit(X, y)
            self.save_model()
            return True
        except Exception as e:
            logger.error(f"Error training ML model: {e}", exc_info=True)
            return False

    def predict_risk(self, features: Dict[str, float]) -> Tuple[float, str, str]:
     
        # Feature columns
        cols = [
            "attendance_rate", 
            "recent_attendance_rate", 
            "consecutive_absences", 
            "trend_slope", 
            "monday_absence_rate", 
            "friday_absence_rate"
        ]
        
        # Prepare input
        input_data = [features.get(c, 0.0) for c in cols]
        
        # Rule-based fallback if ML model is not available
        if self.model is None:
            # Expert rule-based heuristic
            rate = features.get("attendance_rate", 1.0)
            recent_rate = features.get("recent_attendance_rate", 1.0)
            abs_streak = features.get("consecutive_absences", 0.0)
            trend = features.get("trend_slope", 0.0)
            
            # Heuristic calculation
            base_risk = 0.0
            if rate < 0.75:
                base_risk += 0.50
            if recent_rate < 0.70:
                base_risk += 0.25
            if abs_streak >= 3:
                base_risk += 0.15
            if trend < -0.10:
                base_risk += 0.15
            
            risk_prob = min(1.0, max(0.0, base_risk + (1.0 - rate) * 0.2))
        else:
            try:
                # Predict probability
                df_input = pd.DataFrame([input_data], columns=cols)
                risk_prob = float(self.model.predict_proba(df_input)[0][1])
            except Exception as e:
                logger.error(f"ML inference failed, falling back to rules: {e}")
                # Simple backup logic
                rate = features.get("attendance_rate", 1.0)
                risk_prob = 1.0 - rate

        # Categorize risk and generate recommendation
        if risk_prob < 0.30:
            category = "Low"
            recommendation = "Excellent performance. Student is safe. Keep it up!"
        elif risk_prob < 0.70:
            category = "Medium"
            recommendation = "Warning: Attendance is slipping. Monitor weekly. Send automatic email alert."
        else:
            category = "High"
            recommendation = "CRITICAL RISK: Attendance predicted to drop below 75%. Schedule parent-teacher meeting immediately."

        return risk_prob, category, recommendation


def calculate_student_features(student_attendance: List[Dict[str, Any]], total_classes: int) -> Dict[str, float]:
   
    if not student_attendance or total_classes == 0:
        return {
            "attendance_rate": 1.0,
            "recent_attendance_rate": 1.0,
            "consecutive_absences": 0.0,
            "trend_slope": 0.0,
            "monday_absence_rate": 0.0,
            "friday_absence_rate": 0.0
        }

    # Sort by date
    records = sorted(student_attendance, key=lambda x: x["date"])
    
    # Calculate present count
    presents = [r for r in records if r["verification_status"] in ("VERIFIED", "PROXY_SUSPECT")]
    attendance_rate = len(presents) / total_classes

    # Separate into weekdays
    mondays = [r for r in records if datetime.datetime.strptime(r["date"], "%Y-%m-%d").weekday() == 0]
    fridays = [r for r in records if datetime.datetime.strptime(r["date"], "%Y-%m-%d").weekday() == 4]
    
    monday_absence_rate = 0.0
    if mondays:
        monday_absent = len([r for r in mondays if r["verification_status"] == "ABSENT"])
        monday_absence_rate = monday_absent / len(mondays)

    friday_absence_rate = 0.0
    if fridays:
        friday_absent = len([r for r in fridays if r["verification_status"] == "ABSENT"])
        friday_absence_rate = friday_absent / len(fridays)

    # Recent attendance (last 14 classes or days)
    recent_records = records[-14:] if len(records) > 14 else records
    recent_presents = [r for r in recent_records if r["verification_status"] in ("VERIFIED", "PROXY_SUSPECT")]
    recent_attendance_rate = len(recent_presents) / len(recent_records) if recent_records else 1.0

    # Trend slope (difference between recent rate and past rate)
    past_records = records[:-14] if len(records) > 14 else records
    past_presents = [r for r in past_records if r["verification_status"] in ("VERIFIED", "PROXY_SUSPECT")]
    past_attendance_rate = len(past_presents) / len(past_records) if past_records else 1.0
    trend_slope = recent_attendance_rate - past_attendance_rate

    # Consecutive Absences streak
    consecutive_absences = 0
    for r in reversed(records):
        if r["verification_status"] == "ABSENT":
            consecutive_absences += 1
        else:
            break

    return {
        "attendance_rate": float(attendance_rate),
        "recent_attendance_rate": float(recent_attendance_rate),
        "consecutive_absences": float(consecutive_absences),
        "trend_slope": float(trend_slope),
        "monday_absence_rate": float(monday_absence_rate),
        "friday_absence_rate": float(friday_absence_rate)
    }


def seed_historical_data(db_manager) -> bool:
 
    logger.info("Starting historical data seeding process...")
    try:
        # Clear existing data first
        db_manager.clear_historical_data()

        # 1. Add synthetic students
        departments = ["Computer Science", "Information Technology", "Electrical", "Mechanical"]
        years = ["First Year", "Second Year", "Third Year", "Final Year"]
        divisions = ["A", "B"]

        students = [
            # ID, Name, Roll No, Department, Year, Division, Email, Phone
            Student("STU101", "Aarav Sharma", "CS101", "Computer Science", "Third Year", "A", "aarav.sharma@example.com", "9876543210"),
            Student("STU102", "Ananya Verma", "CS102", "Computer Science", "Third Year", "A", "ananya.verma@example.com", "9876543211"),
            Student("STU103", "Kabir Singh", "CS103", "Computer Science", "Third Year", "A", "kabir.singh@example.com", "9876543212"),
            Student("STU104", "Diya Patel", "CS104", "Computer Science", "Third Year", "A", "diya.patel@example.com", "9876543213"),
            Student("STU105", "Rohan Mehta", "CS105", "Computer Science", "Third Year", "A", "rohan.mehta@example.com", "9876543214"),
            
            Student("STU201", "Vivaan Joshi", "IT201", "Information Technology", "Third Year", "B", "vivaan.joshi@example.com", "9876543215"),
            Student("STU202", "Ira Trivedi", "IT202", "Information Technology", "Third Year", "B", "ira.trivedi@example.com", "9876543216"),
            
            Student("STU301", "Aditya Nair", "EE301", "Electrical", "Second Year", "A", "aditya.nair@example.com", "9876543217"),
            Student("STU302", "Zara Sheikh", "EE302", "Electrical", "Second Year", "A", "zara.sheikh@example.com", "9876543218"),
            
            Student("STU401", "Devendra Rao", "ME401", "Mechanical", "Final Year", "B", "dev.rao@example.com", "9876543219"),
        ]

        # Generate fake face encodings (128 dimensions)
        for student in students:
            # 15 face samples per student to simulate multiple captures
            encodings = [np.random.rand(128).astype(np.float64) for _ in range(15)]
            db_manager.add_student(student, encodings)

        # 2. Generate historical attendance over past 60 days (excluding weekends)
        today = datetime.date.today()
        history_days = 60
        attendance_records = []

        # Attendance behavior profiles
        # STU101: Excellent (95% attendance)
        # STU102: Slipping (starts high, drops rapidly in last 15 days)
        # STU103: Sick (good, then absent for 8 consecutive days, then returns)
        # STU104: Low Attender (constant ~60% attendance, misses Mondays/Fridays)
        # STU105: Proxy Suspect (marks attendance but has lower matching confidence)
        # Others: Good (80-88% attendance)

        dates = []
        for d in range(history_days, 0, -1):
            date_val = today - datetime.timedelta(days=d)
            if date_val.weekday() < 5:  # Monday to Friday
                dates.append(date_val.strftime("%Y-%m-%d"))

        for date_str in dates:
            for s in students:
                sid = s.student_id
                
                # Check weekday
                dt_obj = datetime.datetime.strptime(date_str, "%Y-%m-%d")
                is_monday = dt_obj.weekday() == 0
                is_friday = dt_obj.weekday() == 4

                # Determine presence
                present = True
                conf = round(random.uniform(0.78, 0.96), 2)
                status = "VERIFIED"

                if sid == "STU101":
                    # Excellent student: 97% present
                    present = random.random() < 0.97
                elif sid == "STU102":
                    # Slipping student: 90% in first half, 40% in second half
                    day_idx = dates.index(date_str)
                    if day_idx < len(dates) // 2:
                        present = random.random() < 0.90
                    else:
                        present = random.random() < 0.40
                elif sid == "STU103":
                    # Sick student: Absent for days 30 to 38
                    day_idx = dates.index(date_str)
                    if 30 <= day_idx <= 37:
                        present = False
                    else:
                        present = random.random() < 0.90
                elif sid == "STU104":
                    # Constant low: 60% attendance. Higher absence on Mondays/Fridays.
                    if is_monday or is_friday:
                        present = random.random() < 0.40
                    else:
                        present = random.random() < 0.70
                elif sid == "STU105":
                    # Marks attendance but has proxy flags
                    present = random.random() < 0.85
                    if present and random.random() < 0.25:
                        status = "PROXY_SUSPECT"
                        conf = round(random.uniform(0.65, 0.74), 2)
                else:
                    # Others: standard 85% attendance
                    present = random.random() < 0.85

                if present:
                    time_str = f"{random.choice(['08', '09'])}:{random.choice(['55', '56', '57', '58', '59'])}:{random.choice(['10', '20', '30', '40', '50'])}"
                    attendance_records.append((sid, date_str, time_str, conf, status))
                else:
                    # Absent record is not inserted, or let's insert it explicitly
                    # Our DB allows storing ABSENT status records too, which simplifies analytics
                    time_str = "00:00:00"
                    attendance_records.append((sid, date_str, time_str, 0.0, "ABSENT"))

        # Bulk insert attendance records
        db_manager.bulk_insert_attendance(attendance_records)
        logger.info(f"Inserted {len(attendance_records)} attendance logs into database.")

        # 3. Train the ML Model using the seeded data
        # We need to construct a training dataset.
        # To make it realistic, we train on a larger population by simulating 100 students
        X_train_list = []
        y_train_list = []
        
        simulated_profiles = [
            # (attendance_rate_range, recent_drop, streak_range, mon_fri_bias, label)
            ((0.85, 0.98), False, (0, 1), 0.05, 0),  # Excellent
            ((0.78, 0.85), False, (0, 2), 0.10, 0),  # Good
            ((0.68, 0.76), True, (1, 3), 0.15, 1),   # Slipping/Borderline
            ((0.45, 0.65), False, (1, 4), 0.40, 1),  # Low attendance
            ((0.70, 0.80), True, (3, 7), 0.20, 1),   # Extended sickness/drops
        ]

        for _ in range(100):
            prof = random.choice(simulated_profiles)
            rate = random.uniform(prof[0][0], prof[0][1])
            recent_drop = prof[1]
            streak = random.randint(prof[2][0], prof[2][1])
            mon_fri_bias = prof[3]
            label = prof[4]
            
            recent_rate = rate - random.uniform(0.15, 0.35) if recent_drop else rate + random.uniform(-0.05, 0.05)
            recent_rate = max(0.0, min(1.0, recent_rate))
            trend = recent_rate - rate
            
            # Mondays/Fridays absence rates
            mon_abs = max(0.0, min(1.0, (1.0 - rate) + mon_fri_bias + random.uniform(-0.05, 0.05)))
            fri_abs = max(0.0, min(1.0, (1.0 - rate) + mon_fri_bias + random.uniform(-0.05, 0.05)))
            
            X_train_list.append([rate, recent_rate, float(streak), trend, mon_abs, fri_abs])
            y_train_list.append(label)

        X_train = pd.DataFrame(X_train_list, columns=[
            "attendance_rate", "recent_attendance_rate", "consecutive_absences", 
            "trend_slope", "monday_absence_rate", "friday_absence_rate"
        ])
        y_train = pd.Series(y_train_list)

        predictor = RiskPredictor()
        predictor.train_model(X_train, y_train)

        # 4. Compute Health Score & Risk Assessment for each student and save in DB
        total_classes = len(dates)
        for s in students:
            student_att = db_manager.get_attendance_records(student_id=s.student_id)
            # Calculate features
            feats = calculate_student_features(student_att, total_classes)
            
            # Predict risk
            risk_prob, category, rec = predictor.predict_risk(feats)
            
            # Calculate health score: 
            # - attendance rate (60%)
            # - recent attendance (20%)
            # - penalty for streak: max(0, 100 - streak * 10) (20%)
            # Max health score is 100
            streak_score = max(0.0, 100.0 - feats["consecutive_absences"] * 12.0)
            health_score = (feats["attendance_rate"] * 100.0 * 0.6) + (feats["recent_attendance_rate"] * 100.0 * 0.2) + (streak_score * 0.2)
            health_score = float(max(0.0, min(100.0, health_score)))
            
            # Determine health category based on score
            if health_score >= 85.0:
                health_cat = "Excellent"
            elif health_score >= 75.0:
                health_cat = "Good"
            elif health_score >= 60.0:
                health_cat = "Warning"
            else:
                health_cat = "Critical"

            assessment = RiskAssessment(
                student_id=s.student_id,
                health_score=round(health_score, 1),
                risk_score=float(round(risk_prob * 100.0, 1)),
                category=health_cat
            )
            db_manager.update_risk_assessment(assessment)
            
        logger.info("Database seeding completed successfully.")
        db_manager.log_action("Database Seeded with Historical Student Data")
        return True
    except Exception as e:
        logger.error(f"Seeding process failed: {e}", exc_info=True)
        return False
