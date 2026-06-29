import sqlite3
import datetime
from typing import List, Dict, Any, Optional, Tuple
import numpy as np
from config import config
from utils.logger import setup_logger
from utils.helpers import serialize_encoding, deserialize_encoding
from models.student import Student
from models.attendance import Attendance
from models.risk import RiskAssessment
from models.audit_log import AuditLog

logger = setup_logger("database")

class DatabaseManager:
    def __init__(self, db_path: str = config.DB_PATH):
        self.db_path = db_path
        self.init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn

    def init_db(self):
        
        logger.info(f"Initializing database at: {self.db_path}")
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                # Students table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS Students (
                        student_id TEXT PRIMARY KEY,
                        name TEXT NOT NULL,
                        roll_no TEXT NOT NULL,
                        department TEXT NOT NULL,
                        year TEXT NOT NULL,
                        division TEXT NOT NULL,
                        email TEXT NOT NULL,
                        phone TEXT NOT NULL,
                        photo_path TEXT NOT NULL
                    );
                """)

                # Face Encodings table (Multiple encodings per student allowed)
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS Face_Encodings (
                        encoding_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        student_id TEXT NOT NULL,
                        encoding_data BLOB NOT NULL,
                        FOREIGN KEY (student_id) REFERENCES Students (student_id) ON DELETE CASCADE
                    );
                """)

                # Attendance table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS Attendance (
                        attendance_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        student_id TEXT NOT NULL,
                        date TEXT NOT NULL,
                        time TEXT NOT NULL,
                        confidence_score REAL NOT NULL,
                        verification_status TEXT NOT NULL,
                        FOREIGN KEY (student_id) REFERENCES Students (student_id) ON DELETE CASCADE,
                        UNIQUE(student_id, date) -- Prevents marking attendance multiple times a day
                    );
                """)

                # Risk Assessment table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS Risk_Assessment (
                        student_id TEXT PRIMARY KEY,
                        health_score REAL NOT NULL,
                        risk_score REAL NOT NULL,
                        category TEXT NOT NULL,
                        FOREIGN KEY (student_id) REFERENCES Students (student_id) ON DELETE CASCADE
                    );
                """)

                # Audit Logs table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS Audit_Logs (
                        log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp TEXT NOT NULL,
                        action TEXT NOT NULL,
                        user TEXT NOT NULL
                    );
                """)

                conn.commit()
                logger.info("Database initialized successfully.")
        except Exception as e:
            logger.critical(f"Failed to initialize database: {e}", exc_info=True)
            raise e

    # --- AUDIT LOG METHODS ---
    def log_action(self, action: str, user: str = "Admin") -> bool:
     
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            with self._get_connection() as conn:
                conn.execute(
                    "INSERT INTO Audit_Logs (timestamp, action, user) VALUES (?, ?, ?)",
                    (timestamp, action, user)
                )
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Failed to write audit log: {e}")
            return False

    def get_audit_logs(self, limit: int = 100) -> List[AuditLog]:
   
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT log_id, timestamp, action, user FROM Audit_Logs ORDER BY log_id DESC LIMIT ?",
                    (limit,)
                )
                rows = cursor.fetchall()
                return [AuditLog.from_row(row) for row in rows]
        except Exception as e:
            logger.error(f"Failed to get audit logs: {e}")
            return []

    # --- STUDENT METHODS ---
    def add_student(self, student: Student, encodings: List[np.ndarray]) -> bool:
       
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                # Insert Student
                cursor.execute(
                    """INSERT INTO Students (student_id, name, roll_no, department, year, division, email, phone, photo_path)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (student.student_id, student.name, student.roll_no, student.department, 
                     student.year, student.division, student.email, student.phone, student.photo_path)
                )
                # Insert Encodings
                for enc in encodings:
                    enc_bytes = serialize_encoding(enc)
                    cursor.execute(
                        "INSERT INTO Face_Encodings (student_id, encoding_data) VALUES (?, ?)",
                        (student.student_id, enc_bytes)
                    )
                
                # Initialize default risk assessment
                cursor.execute(
                    """INSERT OR IGNORE INTO Risk_Assessment (student_id, health_score, risk_score, category) 
                       VALUES (?, ?, ?, ?)""",
                    (student.student_id, 100.0, 0.0, "Excellent")
                )
                
                conn.commit()
                self.log_action(f"Registered Student: {student.name} ({student.student_id})")
                logger.info(f"Student {student.name} ({student.student_id}) added successfully with {len(encodings)} encodings.")
                return True
        except Exception as e:
            logger.error(f"Failed to add student: {e}", exc_info=True)
            return False

    def update_student(self, student: Student, new_encodings: Optional[List[np.ndarray]] = None) -> bool:
       
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """UPDATE Students 
                       SET name = ?, roll_no = ?, department = ?, year = ?, division = ?, email = ?, phone = ?, photo_path = ?
                       WHERE student_id = ?""",
                    (student.name, student.roll_no, student.department, student.year, student.division, 
                     student.email, student.phone, student.photo_path, student.student_id)
                )
                
                if new_encodings is not None:
                    # Clear old encodings
                    cursor.execute("DELETE FROM Face_Encodings WHERE student_id = ?", (student.student_id,))
                    # Insert new ones
                    for enc in new_encodings:
                        enc_bytes = serialize_encoding(enc)
                        cursor.execute(
                            "INSERT INTO Face_Encodings (student_id, encoding_data) VALUES (?, ?)",
                            (student.student_id, enc_bytes)
                        )
                
                conn.commit()
                self.log_action(f"Updated Student: {student.name} ({student.student_id})")
                logger.info(f"Student {student.name} ({student.student_id}) updated successfully.")
                return True
        except Exception as e:
            logger.error(f"Failed to update student: {e}", exc_info=True)
            return False

    def delete_student(self, student_id: str) -> bool:
     
        try:
            # Get student name for audit logging before delete
            student = self.get_student(student_id)
            student_name = student.name if student else student_id

            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM Students WHERE student_id = ?", (student_id,))
                conn.commit()
                
                self.log_action(f"Deleted Student: {student_name} ({student_id})")
                logger.info(f"Student {student_id} deleted successfully.")
                return True
        except Exception as e:
            logger.error(f"Failed to delete student: {e}", exc_info=True)
            return False

    def get_student(self, student_id: str) -> Optional[Student]:
   
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM Students WHERE student_id = ?", (student_id,))
                row = cursor.fetchone()
                if row:
                    return Student.from_row(row)
                return None
        except Exception as e:
            logger.error(f"Failed to fetch student {student_id}: {e}")
            return None

    def get_all_students(self, department: Optional[str] = None, search_query: Optional[str] = None) -> List[Student]:
   
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                query = "SELECT * FROM Students WHERE 1=1"
                params = []
                
                if department:
                    query += " AND department = ?"
                    params.append(department)
                
                if search_query:
                    query += " AND (student_id LIKE ? OR name LIKE ? OR roll_no LIKE ?)"
                    search_pat = f"%{search_query}%"
                    params.extend([search_pat, search_pat, search_pat])
                
                query += " ORDER BY roll_no ASC"
                cursor.execute(query, params)
                rows = cursor.fetchall()
                return [Student.from_row(row) for row in rows]
        except Exception as e:
            logger.error(f"Failed to get students: {e}")
            return []

    # --- FACE ENCODINGS METHODS ---
    def get_all_encodings(self) -> Dict[str, List[np.ndarray]]:
    
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT student_id, encoding_data FROM Face_Encodings")
                rows = cursor.fetchall()
                
                encodings_dict = {}
                for student_id, enc_bytes in rows:
                    if student_id not in encodings_dict:
                        encodings_dict[student_id] = []
                    encodings_dict[student_id].append(deserialize_encoding(enc_bytes))
                return encodings_dict
        except Exception as e:
            logger.error(f"Failed to load face encodings: {e}")
            return {}

    # --- ATTENDANCE METHODS ---
    def mark_attendance(self, attendance: Attendance) -> bool:
       
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """INSERT INTO Attendance (student_id, date, time, confidence_score, verification_status)
                       VALUES (?, ?, ?, ?, ?)
                       ON CONFLICT(student_id, date) DO UPDATE SET
                       time = excluded.time,
                       confidence_score = excluded.confidence_score,
                       verification_status = excluded.verification_status""",
                    (attendance.student_id, attendance.date, attendance.time, 
                     attendance.confidence_score, attendance.verification_status)
                )
                conn.commit()
                self.log_action(f"Marked Attendance: Student ID {attendance.student_id} as {attendance.verification_status}")
                return True
        except Exception as e:
            logger.error(f"Failed to mark attendance for {attendance.student_id}: {e}")
            return False

    def delete_attendance(self, student_id: str, date: str) -> bool:
      
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM Attendance WHERE student_id = ? AND date = ?", (student_id, date))
                conn.commit()
                self.log_action(f"Deleted Attendance: Student ID {student_id} on {date}")
                return True
        except Exception as e:
            logger.error(f"Failed to delete attendance for {student_id} on {date}: {e}")
            return False

    def get_attendance_records(self, date: Optional[str] = None, department: Optional[str] = None, 
                               student_id: Optional[str] = None) -> List[Dict[str, Any]]:
       
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                query = """
                    SELECT 
                        a.attendance_id, a.student_id, s.name, s.roll_no, 
                        s.department, s.year, s.division, a.date, a.time, 
                        a.confidence_score, a.verification_status
                    FROM Attendance a
                    JOIN Students s ON a.student_id = s.student_id
                    WHERE 1=1
                """
                params = []
                if date:
                    query += " AND a.date = ?"
                    params.append(date)
                if department:
                    query += " AND s.department = ?"
                    params.append(department)
                if student_id:
                    query += " AND a.student_id = ?"
                    params.append(student_id)
                
                query += " ORDER BY a.date DESC, s.roll_no ASC"
                cursor.execute(query, params)
                rows = cursor.fetchall()
                
                records = []
                for r in rows:
                    records.append({
                        "attendance_id": r[0],
                        "student_id": r[1],
                        "name": r[2],
                        "roll_no": r[3],
                        "department": r[4],
                        "year": r[5],
                        "division": r[6],
                        "date": r[7],
                        "time": r[8],
                        "confidence_score": r[9],
                        "verification_status": r[10]
                    })
                return records
        except Exception as e:
            logger.error(f"Failed to get attendance records: {e}")
            return []

    # --- RISK ASSESSMENT METHODS ---
    def update_risk_assessment(self, risk: RiskAssessment) -> bool:
     
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """INSERT INTO Risk_Assessment (student_id, health_score, risk_score, category)
                       VALUES (?, ?, ?, ?)
                       ON CONFLICT(student_id) DO UPDATE SET
                       health_score = excluded.health_score,
                       risk_score = excluded.risk_score,
                       category = excluded.category""",
                    (risk.student_id, risk.health_score, risk.risk_score, risk.category)
                )
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Failed to update risk assessment for {risk.student_id}: {e}")
            return False

    def get_risk_assessments(self) -> List[Dict[str, Any]]:
      
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                query = """
                    SELECT 
                        r.student_id, s.name, s.roll_no, s.department, s.year, 
                        r.health_score, r.risk_score, r.category
                    FROM Risk_Assessment r
                    JOIN Students s ON r.student_id = s.student_id
                    ORDER BY r.risk_score DESC
                """
                cursor.execute(query)
                rows = cursor.fetchall()
                
                assessments = []
                for r in rows:
                    assessments.append({
                        "student_id": r[0],
                        "name": r[1],
                        "roll_no": r[2],
                        "department": r[3],
                        "year": r[4],
                        "health_score": r[5],
                        "risk_score": r[6],
                        "category": r[7]
                    })
                return assessments
        except Exception as e:
            logger.error(f"Failed to get risk assessments: {e}")
            return []
            
    def get_risk_assessment(self, student_id: str) -> Optional[RiskAssessment]:
      
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM Risk_Assessment WHERE student_id = ?", (student_id,))
                row = cursor.fetchone()
                if row:
                    return RiskAssessment.from_row(row)
                return None
        except Exception as e:
            logger.error(f"Failed to fetch risk assessment for {student_id}: {e}")
            return None
            
    def bulk_insert_attendance(self, records: List[Tuple[str, str, str, float, str]]) -> bool:
    
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.executemany(
                    """INSERT OR IGNORE INTO Attendance 
                       (student_id, date, time, confidence_score, verification_status) 
                       VALUES (?, ?, ?, ?, ?)""",
                    records
                )
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Failed to bulk insert attendance: {e}")
            return False
            
    def clear_historical_data(self) -> bool:
      
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM Attendance")
                cursor.execute("DELETE FROM Risk_Assessment")
                cursor.execute("DELETE FROM Audit_Logs")
                conn.commit()
                self.log_action("Cleared all attendance and historical data")
                return True
        except Exception as e:
            logger.error(f"Failed to clear data: {e}")
            return False
