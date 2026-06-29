import numpy as np
from datetime import datetime


def calculate_student_features(attendance_records, total_classes):
    """
    Generate ML features from a student's attendance history.

    attendance_records:
        List of dicts containing at least:
            date
            status (Present/Absent)

    total_classes:
        Total number of classes held.
    """

    if not attendance_records:
        return {
            "attendance_rate": 0.0,
            "recent_attendance_rate": 0.0,
            "consecutive_absences": 0,
            "trend_slope": 0.0,
            "monday_absence_rate": 0.0,
            "friday_absence_rate": 0.0,
        }

    # Sort chronologically
    attendance_records = sorted(
        attendance_records,
        key=lambda x: x.get("date", "")
    )

    present = 0
    absent = 0

    values = []

    consecutive_absences = 0
    current_absence_streak = 0

    monday_total = 0
    monday_absent = 0

    friday_total = 0
    friday_absent = 0

    for record in attendance_records:

        status = str(record.get("status", "")).lower()

        is_present = status in [
            "present",
            "p",
            "1",
            "true",
            "yes"
        ]

        if is_present:
            present += 1
            current_absence_streak = 0
            values.append(1)
        else:
            absent += 1
            current_absence_streak += 1
            consecutive_absences = max(
                consecutive_absences,
                current_absence_streak
            )
            values.append(0)

        # Weekday statistics
        try:
            d = datetime.fromisoformat(record["date"])
            weekday = d.weekday()

            if weekday == 0:
                monday_total += 1
                if not is_present:
                    monday_absent += 1

            if weekday == 4:
                friday_total += 1
                if not is_present:
                    friday_absent += 1

        except Exception:
            pass

    attendance_rate = present / max(total_classes, 1)

    recent = values[-10:]
    recent_attendance_rate = (
        sum(recent) / len(recent)
        if recent else attendance_rate
    )

    trend_slope = 0.0
    if len(values) > 1:
        x = np.arange(len(values))
        trend_slope = float(np.polyfit(x, values, 1)[0])

    monday_absence_rate = (
        monday_absent / monday_total
        if monday_total else 0.0
    )

    friday_absence_rate = (
        friday_absent / friday_total
        if friday_total else 0.0
    )

    return {
        "attendance_rate": attendance_rate,
        "recent_attendance_rate": recent_attendance_rate,
        "consecutive_absences": consecutive_absences,
        "trend_slope": trend_slope,
        "monday_absence_rate": monday_absence_rate,
        "friday_absence_rate": friday_absence_rate,
    }