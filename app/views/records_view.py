import datetime
import time
import pandas as pd
import streamlit as st
from app.ui_components import render_header
from models.attendance import Attendance

def render_records(db_manager):
    render_header(
        title="Attendance Records & Override Manager",
        subtitle="Search, filter, export, and manually override class attendance logs."
    )

    tab1, tab2 = st.tabs(["📋 Attendance Logs", "⚙️ Manual Logs Override"])

    # Fetch initial lists for dropdown filters
    students = db_manager.get_all_students()
    departments = ["All"] + list(set(s.department for s in students))

    # --- TAB 1: ATTENDANCE LOGS ---
    with tab1:
        st.subheader("Filter Log History")
        col1, col2, col3 = st.columns(3)
        with col1:
            selected_date = st.date_input("Filter Date", value=datetime.date.today())
            date_filter = selected_date.strftime("%Y-%m-%d")
        with col2:
            selected_dept = st.selectbox("Filter Department", departments, key="records_dept")
            dept_filter = None if selected_dept == "All" else selected_dept
        with col3:
            search_id = st.text_input("Filter Student ID (Exact Match)", value="")
            student_filter = search_id.strip() if search_id else None

        records = db_manager.get_attendance_records(
            date=date_filter,
            department=dept_filter,
            student_id=student_filter
        )

        if not records:
            st.info(f"No attendance logs found for {date_filter}.")
        else:
            st.write(f"Found **{len(records)}** attendance records.")
            
            # Format dataframe
            df = pd.DataFrame(records)
            df_display = df[[
                "student_id", "roll_no", "name", "department", 
                "year", "time", "confidence_score", "verification_status"
            ]]
            df_display.columns = [
                "Student ID", "Roll No", "Name", "Department", 
                "Year", "Log Time", "Match Confidence", "Verification"
            ]
            # Convert confidence to percentage
            df_display["Match Confidence"] = df_display["Match Confidence"].apply(lambda c: f"{int(c * 100)}%")

            st.dataframe(df_display, width="stretch")

            # Export actions
            st.write("---")
            st.subheader("Export Filtered Logs")
            
            col_csv, col_xlsx = st.columns(2)
            with col_csv:
                csv_data = df_display.to_csv(index=False).encode('utf-8')
                st.download_button(
                    "Download CSV Report",
                    data=csv_data,
                    file_name=f"Attendance_Report_{date_filter}.csv",
                    mime="text/csv"
                )
            with col_xlsx:
                # Store in export folder or stream directly in Streamlit
                # Let's stream a quick Excel file bytes if needed, but CSV is standard.
                # Since streamlit has no excel downloader built-in, writing to a temp buffer is easy.
                import io
                buffer = io.BytesIO()
                with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                    df_display.to_excel(writer, index=False, sheet_name="Attendance Details")
                st.download_button(
                    "Download Excel Report",
                    data=buffer.getvalue(),
                    file_name=f"Attendance_Report_{date_filter}.xlsx",
                    mime="application/vnd.ms-excel"
                )

    # --- TAB 2: MANUAL LOGS OVERRIDE ---
    with tab2:
        st.subheader("Add / Correct Attendance Logs")
        st.warning("⚠️ Manual overrides will directly alter the student's historical attendance record and update their risk metrics.")
        
        # Form to mark attendance manually
        with st.form("manual_override_form"):
            target_student_id = st.selectbox("Select Student ID", [""] + [s.student_id for s in students])
            override_date = st.date_input("Attendance Date", value=datetime.date.today())
            override_status = st.selectbox("Attendance Status", ["VERIFIED", "ABSENT", "PROXY_SUSPECT"])
            
            submit_override = st.form_submit_button("Override Attendance Record")

        if submit_override:
            if not target_student_id:
                st.error("Please select a student.")
            else:
                student_info = db_manager.get_student(target_student_id)
                if not student_info:
                    st.error("Student ID is invalid.")
                else:
                    date_str = override_date.strftime("%Y-%m-%d")
                    
                    if override_status == "ABSENT":
                        # We delete or insert as ABSENT record
                        # Since DB can log ABSENT, let's log it
                        new_att = Attendance(
                            student_id=target_student_id,
                            date=date_str,
                            time="00:00:00",
                            confidence_score=0.0,
                            verification_status="ABSENT"
                        )
                        success = db_manager.mark_attendance(new_att)
                    else:
                        now_time = datetime.datetime.now().strftime("%H:%M:%S")
                        new_att = Attendance(
                            student_id=target_student_id,
                            date=date_str,
                            time=now_time,
                            confidence_score=1.0,  # Manual override has 100% confidence
                            verification_status=override_status
                        )
                        success = db_manager.mark_attendance(new_att)
                        
                    if success:
                        st.success(f"Successfully overridden log for {student_info.name} on {date_str} to '{override_status}'.")
                        db_manager.log_action(f"Manual Override: {target_student_id} set to {override_status} on {date_str}")
                        
                        # Trigger risk assessment recalculation immediately!
                        recalculate_risk(db_manager, target_student_id)
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error("Failed to override attendance record.")


def recalculate_risk(db_manager, student_id: str):
    """Utility to recalculate a student's metrics and save it after an override."""
    try:
        from ml.predictor import calculate_student_features, RiskPredictor
        from models.risk import RiskAssessment
        
        # Calculate overall classes from date list in database
        records = db_manager.get_attendance_records()
        if not records:
            return
        df = pd.DataFrame(records)
        total_classes = df["date"].nunique()
        
        student_att = db_manager.get_attendance_records(student_id=student_id)
        if not student_att:
            return
            
        feats = calculate_student_features(student_att, total_classes)
        predictor = RiskPredictor()
        risk_prob, category, rec = predictor.predict_risk(feats)
        
        # Calculate health score
        streak_score = max(0.0, 100.0 - feats["consecutive_absences"] * 12.0)
        health_score = (feats["attendance_rate"] * 100.0 * 0.6) + (feats["recent_attendance_rate"] * 100.0 * 0.2) + (streak_score * 0.2)
        health_score = float(max(0.0, min(100.0, health_score)))
        
        if health_score >= 85.0:
            health_cat = "Excellent"
        elif health_score >= 75.0:
            health_cat = "Good"
        elif health_score >= 60.0:
            health_cat = "Warning"
        else:
            health_cat = "Critical"

        assessment = RiskAssessment(
            student_id=student_id,
            health_score=round(health_score, 1),
            risk_score=float(round(risk_prob * 100.0, 1)),
            category=health_cat
        )
        db_manager.update_risk_assessment(assessment)
        logger.info(f"Recalculated metrics for student {student_id} successfully.")
    except Exception as e:
        logger.error(f"Error recalculating risk during override: {e}")
