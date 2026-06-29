import datetime
import pandas as pd
import numpy as np
from typing import List, Dict, Any, Tuple
from utils.logger import setup_logger
from config import config

logger = setup_logger("analytics_engine")

class AnalyticsEngine:
    def __init__(self, db_manager):
        self.db = db_manager

    def get_kpis_today(self) -> Dict[str, Any]:
        today_str = datetime.date.today().strftime("%Y-%m-%d")
        all_students = self.db.get_all_students()
        total_students = len(all_students)
        
        if total_students == 0:
            return {
                "total_students": 0,
                "present_count": 0,
                "absent_count": 0,
                "attendance_rate": 0.0,
                "defaulters_count": 0
            }

        # Fetch today's records
        today_records = self.db.get_attendance_records(date=today_str)
        
        # In our SQLite, if a student isn't explicitly marked ABSENT but doesn't have a record, they are absent.
        # But to be robust, we fetch all students, and see which ones are in today's records.
        present_sids = {r["student_id"] for r in today_records if r["verification_status"] in ("VERIFIED", "PROXY_SUSPECT")}
        absent_sids = {r["student_id"] for r in today_records if r["verification_status"] == "ABSENT"}
        
        # Calculate totals
        present_count = len(present_sids)
        # Any student not present is absent
        absent_count = total_students - present_count
        attendance_rate = (present_count / total_students) * 100.0

        # Defaulters (overall health < 75%)
        risk_assessments = self.db.get_risk_assessments()
        defaulters_count = len([r for r in risk_assessments if r["health_score"] < (config.ATTENDANCE_RISK_THRESHOLD * 100)])

        return {
            "total_students": total_students,
            "present_count": present_count,
            "absent_count": absent_count,
            "attendance_rate": round(attendance_rate, 1),
            "defaulters_count": defaulters_count
        }

    def get_attendance_trends(self) -> Tuple[pd.DataFrame, pd.DataFrame]:
    
        records = self.db.get_attendance_records()
        if not records:
            return pd.DataFrame(), pd.DataFrame()

        df = pd.DataFrame(records)
        
        # 1. Daily Aggregation
        # Count present/absent per date
        daily_stats = []
        all_dates = df["date"].unique()
        all_students = self.db.get_all_students()
        total_enrolled = len(all_students)

        for date in all_dates:
            date_df = df[df["date"] == date]
            presents = len(date_df[date_df["verification_status"].isin(["VERIFIED", "PROXY_SUSPECT"])])
            absents = total_enrolled - presents
            rate = (presents / total_enrolled) * 100.0 if total_enrolled > 0 else 0.0
            
            daily_stats.append({
                "date": date,
                "present": presents,
                "absent": absents,
                "rate": round(rate, 1)
            })

        df_daily = pd.DataFrame(daily_stats).sort_values("date")

        # 2. Department-wise Aggregation
        # Group by department, calculate percentage of presence out of total sessions per student
        dept_stats = []
        if not df.empty:
            # We must calculate: (presents per dept) / (total capacity per dept across dates)
            # Count unique dates in history
            num_dates = len(all_dates)
            
            for dept in df["department"].unique():
                dept_df = df[df["department"] == dept]
                dept_students = [s for s in all_students if s.department == dept]
                dept_size = len(dept_students)
                
                # Capacity = students in dept * number of class days
                total_capacity = dept_size * num_dates
                
                presents = len(dept_df[dept_df["verification_status"].isin(["VERIFIED", "PROXY_SUSPECT"])])
                rate = (presents / total_capacity) * 100.0 if total_capacity > 0 else 0.0
                
                dept_stats.append({
                    "department": dept,
                    "rate": round(rate, 1)
                })
        
        df_dept = pd.DataFrame(dept_stats)
        return df_daily, df_dept

    def get_student_rankings(self) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        
        assessments = self.db.get_risk_assessments()
        if not assessments:
            return [], []

        # Sort for top performers
        top_performers = sorted(assessments, key=lambda x: x["health_score"], reverse=True)[:5]
        
        # Sort for defaulters
        defaulters = [r for r in assessments if r["health_score"] < (config.ATTENDANCE_RISK_THRESHOLD * 100)]
        defaulters = sorted(defaulters, key=lambda x: x["health_score"])

        return top_performers, defaulters

    def generate_ai_insights(self) -> List[str]:
       
        insights = []
        records = self.db.get_attendance_records()
        all_students = self.db.get_all_students()
        
        if not records or not all_students:
            return ["No data available to generate insights yet. Please register students and log attendance."]

        df = pd.DataFrame(records)
        df_presents = df[df["verification_status"].isin(["VERIFIED", "PROXY_SUSPECT"])]
        
        # Total dates tracked
        unique_dates = sorted(df["date"].unique())
        if len(unique_dates) < 5:
            return [
                "Seeding complete. Gather more attendance sessions to unlock advanced comparative trends.",
                f"Currently tracking {len(all_students)} students across {len(unique_dates)} dates."
            ]

        # 1. Defaulter Alert
        risk_assessments = self.db.get_risk_assessments()
        defaulters = [r for r in risk_assessments if r["health_score"] < (config.ATTENDANCE_RISK_THRESHOLD * 100)]
        critical_count = len([r for r in risk_assessments if r["category"] == "Critical"])
        
        if len(defaulters) > 0:
            insights.append(
                f"🚨 **Defaulter Threshold Warning**: {len(defaulters)} students ({round(len(defaulters)/len(all_students)*100, 1)}%) "
                f"are below the mandatory 75% attendance threshold. {critical_count} are in the Critical zone."
            )
        else:
            insights.append("🎉 **Perfect Compliance**: All students currently maintain attendance health above the 75% threshold.")

        # 2. Weekly Trend comparison
        # Get dates for this week (last 5 dates) vs last week (previous 5 dates)
        if len(unique_dates) >= 10:
            last_5_dates = unique_dates[-5:]
            prev_5_dates = unique_dates[-10:-5]
            
            presents_this_week = len(df_presents[df_presents["date"].isin(last_5_dates)])
            presents_last_week = len(df_presents[df_presents["date"].isin(prev_5_dates)])
            
            this_week_rate = (presents_this_week / (len(all_students) * 5)) * 100.0
            last_week_rate = (presents_last_week / (len(all_students) * 5)) * 100.0
            
            diff = this_week_rate - last_week_rate
            if diff > 1.0:
                insights.append(f"📈 **Weekly Performance**: Average attendance increased by {round(diff, 1)}% this week compared to last week.")
            elif diff < -1.0:
                insights.append(f"📉 **Weekly Performance**: Average attendance dropped by {round(abs(diff), 1)}% this week. Monitor closely.")
            else:
                insights.append("📊 **Weekly Performance**: Attendance rates remain stable compared to last week.")

        # 3. Day of Week Analysis
        # Map dates to weekday names
        df["weekday"] = df["date"].apply(lambda d: datetime.datetime.strptime(d, "%Y-%m-%d").strftime("%A"))
        
        # Calculate attendance rate per weekday
        weekday_rates = {}
        for day in df["weekday"].unique():
            day_df = df[df["weekday"] == day]
            day_dates = day_df["date"].nunique()
            capacity = len(all_students) * day_dates
            presents = len(day_df[day_df["verification_status"].isin(["VERIFIED", "PROXY_SUSPECT"])])
            
            rate = (presents / capacity) * 100.0 if capacity > 0 else 0.0
            weekday_rates[day] = rate

        if weekday_rates:
            worst_day = min(weekday_rates, key=weekday_rates.get)
            best_day = max(weekday_rates, key=weekday_rates.get)
            
            if worst_day in ["Monday", "Friday"] and weekday_rates[worst_day] < 80.0:
                insights.append(
                    f"📅 **Weekend Extension Pattern**: {worst_day}s have the lowest attendance rate ({round(weekday_rates[worst_day], 1)}%). "
                    "Students show a high tendency to skip classes adjacent to weekends."
                )
            else:
                insights.append(f"📅 **Peak Engagement**: {best_day}s show the highest student attendance ({round(weekday_rates[best_day], 1)}%).")

        # 4. Department Performance
        # Find highest and lowest performing departments
        dept_rates = {}
        for dept in df["department"].unique():
            dept_df = df[df["department"] == dept]
            dept_students = len([s for s in all_students if s.department == dept])
            capacity = dept_students * len(unique_dates)
            presents = len(dept_df[dept_df["verification_status"].isin(["VERIFIED", "PROXY_SUSPECT"])])
            rate = (presents / capacity) * 100.0 if capacity > 0 else 0.0
            dept_rates[dept] = rate

        if len(dept_rates) > 1:
            best_dept = max(dept_rates, key=dept_rates.get)
            worst_dept = min(dept_rates, key=dept_rates.get)
            insights.append(
                f"🏫 **Departmental Focus**: The **{best_dept}** department leads with {round(dept_rates[best_dept], 1)}% attendance, "
                f"while **{worst_dept}** records the lowest average of {round(dept_rates[worst_dept], 1)}%."
            )

        # 5. Anti-Proxy / Risk flag
        proxy_records = df[df["verification_status"] == "PROXY_SUSPECT"]
        if len(proxy_records) > 0:
            suspect_names = []
            for sid in proxy_records["student_id"].unique()[:3]:
                stu = self.db.get_student(sid)
                if stu:
                    suspect_names.append(stu.name)
            
            insights.append(
                f"🛡️ **Security Alert**: The anti-proxy system flagged {len(proxy_records)} suspicious verification logs. "
                f"Top profiles requiring manual review: {', '.join(suspect_names)}."
            )

        return insights
