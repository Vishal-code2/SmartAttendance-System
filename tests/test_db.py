import unittest
import os
import numpy as np
from pathlib import Path
from database.db_manager import DatabaseManager
from models.student import Student
from models.attendance import Attendance
from models.risk import RiskAssessment

TEST_DB = "test_smart_attend.db"

class TestDatabaseManager(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Ensure we use a clean test database file
        if os.path.exists(TEST_DB):
            os.remove(TEST_DB)
        cls.db = DatabaseManager(db_path=TEST_DB)

    @classmethod
    def tearDownClass(cls):
        if os.path.exists(TEST_DB):
            os.remove(TEST_DB)

    def test_1_db_initialization(self):
        self.assertTrue(os.path.exists(TEST_DB))

    def test_2_student_crud(self):
        student = Student(
            student_id="STU001",
            name="John Doe",
            roll_no="101",
            department="Computer Science",
            year="Third Year",
            division="A",
            email="john.doe@example.com",
            phone="1234567890",
            photo_path="photos/STU001"
        )
        # Mock encoding: 128 elements of float64
        enc = np.random.rand(128).astype(np.float64)
        
        # Test Add
        res = self.db.add_student(student, [enc])
        self.assertTrue(res)
        
        # Test Get
        retrieved = self.db.get_student("STU001")
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.name, "John Doe")
        self.assertEqual(retrieved.roll_no, "101")
        
        # Test Encodings Retrieve
        encodings = self.db.get_all_encodings()
        self.assertIn("STU001", encodings)
        self.assertEqual(len(encodings["STU001"]), 1)
        self.assertTrue(np.allclose(encodings["STU001"][0], enc))

    def test_3_attendance(self):
        attendance = Attendance(
            student_id="STU001",
            date="2026-06-23",
            time="10:00:00",
            confidence_score=0.92,
            verification_status="VERIFIED"
        )
        res = self.db.mark_attendance(attendance)
        self.assertTrue(res)
        
        # Retrieve attendance
        records = self.db.get_attendance_records(date="2026-06-23")
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["student_id"], "STU001")
        self.assertEqual(records[0]["verification_status"], "VERIFIED")

    def test_4_risk_assessment(self):
        risk = RiskAssessment(
            student_id="STU001",
            health_score=85.0,
            risk_score=0.25,
            category="Good"
        )
        res = self.db.update_risk_assessment(risk)
        self.assertTrue(res)
        
        retrieved = self.db.get_risk_assessment("STU001")
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.health_score, 85.0)
        self.assertEqual(retrieved.category, "Good")

    def test_5_audit_logs(self):
        res = self.db.log_action("Test Action", "Tester")
        self.assertTrue(res)
        
        logs = self.db.get_audit_logs(limit=5)
        self.assertGreater(len(logs), 0)
        self.assertEqual(logs[0].action, "Test Action")
        self.assertEqual(logs[0].user, "Tester")

    def test_6_cascade_delete(self):
        # Delete student STU001
        res = self.db.delete_student("STU001")
        self.assertTrue(res)
        
        # Verify student is deleted
        student = self.db.get_student("STU001")
        self.assertIsNone(student)
        
        # Verify encodings are deleted
        encodings = self.db.get_all_encodings()
        self.assertNotIn("STU001", encodings)
        
        # Verify attendance is deleted (cascaded)
        records = self.db.get_attendance_records(student_id="STU001")
        self.assertEqual(len(records), 0)

if __name__ == "__main__":
    unittest.main()
