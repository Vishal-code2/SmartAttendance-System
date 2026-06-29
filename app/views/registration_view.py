import os
import cv2
import time
import numpy as np
import streamlit as st
from config import config
from utils.logger import setup_logger
from app.ui_components import render_header
from models.student import Student

logger = setup_logger("registration_view")

def render_registration(db_manager, detector):
    render_header(
        title="Student Registration & Enrolment",
        subtitle="Manage student directory and enrol biometric facial profiles."
    )

    tab1, tab2 = st.tabs(["👥 Student Directory", "🆕 Enrol New Student"])

    # --- TAB 1: STUDENT DIRECTORY ---
    with tab1:
        st.subheader("Registered Students")
        
        # Search & Filter
        col1, col2 = st.columns([3, 1])
        with col1:
            search_q = st.text_input("🔍 Search Students by Name, ID, or Roll Number", value="")
        with col2:
            depts = ["All", "Computer Science", "Information Technology", "Electrical", "Mechanical"]
            selected_dept = st.selectbox("Filter Department", depts)
            dept_filter = None if selected_dept == "All" else selected_dept

        students = db_manager.get_all_students(department=dept_filter, search_query=search_q if search_q else None)

        if not students:
            st.info("No students found matching your criteria.")
        else:
            # Display directory list
            student_data = []
            for s in students:
                student_data.append({
                    "Student ID": s.student_id,
                    "Roll No": s.roll_no,
                    "Name": s.name,
                    "Department": s.department,
                    "Year / Div": f"{s.year} - {s.division}",
                    "Email": s.email,
                    "Phone": s.phone
                })
            
            st.dataframe(student_data, width="stretch")

            # Actions: Edit / Delete student
            st.write("---")
            st.subheader("Manage student record")
            target_id = st.selectbox("Select Student ID for action", [""] + [s.student_id for s in students])

            if target_id:
                target_student = db_manager.get_student(target_id)
                if target_student:
                    # Edit Form
                    with st.form("edit_student_form"):
                        st.write(f"✏️ **Editing Student: {target_student.name}**")
                        
                        e_name = st.text_input("Name", target_student.name)
                        col1, col2 = st.columns(2)
                        with col1:
                            e_roll = st.text_input("Roll Number", target_student.roll_no)
                            e_dept = st.selectbox("Department", ["Computer Science", "Information Technology", "Electrical", "Mechanical"], index=["Computer Science", "Information Technology", "Electrical", "Mechanical"].index(target_student.department))
                        with col2:
                            e_year = st.selectbox("Year", ["First Year", "Second Year", "Third Year", "Final Year"], index=["First Year", "Second Year", "Third Year", "Final Year"].index(target_student.year))
                            e_div = st.text_input("Division", target_student.division)
                        
                        e_email = st.text_input("Email", target_student.email)
                        e_phone = st.text_input("Phone Number", target_student.phone)
                        
                        col_submit, col_delete = st.columns([4, 1])
                        
                        with col_submit:
                            submitted = st.form_submit_button("Update Details")
                        
                        if submitted:
                            updated_stu = Student(
                                student_id=target_student.student_id,
                                name=e_name,
                                roll_no=e_roll,
                                department=e_dept,
                                year=e_year,
                                division=e_div,
                                email=e_email,
                                phone=e_phone,
                                photo_path=target_student.photo_path
                            )
                            success = db_manager.update_student(updated_stu)
                            if success:
                                st.success(f"Successfully updated record for {e_name}.")
                                time.sleep(1)
                                st.rerun()
                            else:
                                st.error("Failed to update student.")

                    # Delete action outside the form to avoid nested issues
                    if st.button("🗑️ Delete Student Permanent (Cascades All Attendance Logs)"):
                        # Delete photo if exists
                        if target_student.photo_path and os.path.exists(target_student.photo_path):
                            try:
                                os.remove(target_student.photo_path)
                            except Exception as e:
                                logger.error(f"Failed to delete student photo file: {e}")
                        
                        success = db_manager.delete_student(target_student.student_id)
                        if success:
                            st.success(f"Successfully deleted student {target_student.name}.")
                            time.sleep(1)
                            st.rerun()
                        else:
                            st.error("Failed to delete student.")

    # --- TAB 2: ENROL NEW STUDENT ---
    with tab2:
        st.subheader("Enrollment Wizard")
        st.info("ℹ️ Enter the student's personal details first. Then start the Biometric face profile capture.")

        with st.form("enroll_details_form"):
            col1, col2 = st.columns(2)
            with col1:
                student_id = st.text_input("Student ID (Unique, e.g. STU110)", "").strip()
                name = st.text_input("Full Name", "").strip()
                roll_no = st.text_input("Roll Number", "").strip()
                department = st.selectbox("Department", ["Computer Science", "Information Technology", "Electrical", "Mechanical"])
            with col2:
                year = st.selectbox("Year", ["First Year", "Second Year", "Third Year", "Final Year"])
                division = st.text_input("Division / Batch", "A").strip()
                email = st.text_input("Email ID", "").strip()
                phone = st.text_input("Phone Number", "").strip()
            
            submit_details = st.form_submit_button("Confirm Enrolment Fields")

        # Session state for registration logic
        if "reg_details" not in st.session_state:
            st.session_state.reg_details = None

        if submit_details:
            if not student_id or not name or not roll_no or not email or not phone:
                st.error("⚠️ Please fill in all details before confirming.")
            else:
                # Check duplication
                existing = db_manager.get_student(student_id)
                if existing:
                    st.error(f"⚠️ Student ID '{student_id}' is already registered to '{existing.name}'. Please use a unique ID.")
                else:
                    st.session_state.reg_details = {
                        "student_id": student_id,
                        "name": name,
                        "roll_no": roll_no,
                        "department": department,
                        "year": year,
                        "division": division,
                        "email": email,
                        "phone": phone
                    }
                    st.success("Details confirmed! Proceed to face scan below.")

        if st.session_state.reg_details:
            details = st.session_state.reg_details
            st.write("---")
            st.subheader("Biometric Profile Registration")
            st.write(f"Enrolling face profile for: **{details['name']}**")
            
            # Setup poses instructions
            pose_instructions = [
                "1. Look directly at the camera (Front view)",
                "2. Turn head slightly LEFT",
                "3. Turn head slightly RIGHT",
                "4. Tilt head up/down or smile"
            ]
            
            st.markdown("### 📸 Instructions:")
            for instr in pose_instructions:
                st.markdown(f"- {instr}")

            # Streamlit Webcam Capture
            start_capture = st.checkbox("🎥 Start Biometric Scan")
            
            if start_capture:
                cap = cv2.VideoCapture(config.CAMERA_INDEX)
                if not cap.isOpened():
                    st.error("Error: Could not open camera.")
                    return

                # Placeholders for image feed and capture progress
                feed_placeholder = st.empty()
                progress_placeholder = st.empty()
                
                captured_encodings = []
                # Keep a single photo frame to save as profile thumbnail
                thumbnail_frame = None

                max_samples = 15
                
                # Setup instructions timer
                sample_interval = 0.4
                last_sample_time = time.time()

                while len(captured_encodings) < max_samples and start_capture:
                    ret, frame = cap.read()
                    if not ret:
                        st.error("Failed to read camera stream.")
                        break

                    frame = cv2.flip(frame, 1)
                    
                    # Current pose selection based on samples gathered
                    current_sample_idx = len(captured_encodings)
                    if current_sample_idx < 4:
                        pose_msg = "Pose: LOOK FRONT"
                    elif current_sample_idx < 8:
                        pose_msg = "Pose: TURN LEFT"
                    elif current_sample_idx < 12:
                        pose_msg = "Pose: TURN RIGHT"
                    else:
                        pose_msg = "Pose: SMILE / TILT"

                    # Run detection for feedback bounding box
                    face_locations = detector.detect_faces(frame)
                    
                    # Draw visual feedback
                    frame_draw = frame.copy()
                    
                    # Header instructions drawn on camera overlay
                    cv2.rectangle(frame_draw, (0, 0), (frame_draw.shape[1], 40), (26, 54, 93), cv2.FILLED)
                    cv2.putText(
                        frame_draw, f"{pose_msg} | Captured: {current_sample_idx}/{max_samples}",
                        (10, 25), cv2.FONT_HERSHEY_DUPLEX, 0.6, (255, 255, 255), 1
                    )

                    if len(face_locations) == 1:
                        top, right, bottom, left = face_locations[0]
                        # Draw green box indicating good frame
                        cv2.rectangle(frame_draw, (left, top), (right, bottom), (0, 255, 0), 2)
                        
                        # Grab encoding periodically
                        now = time.time()
                        if now - last_sample_time > sample_interval:
                            encodings = detector.extract_encodings(frame, face_locations)
                            if encodings:
                                captured_encodings.append(encodings[0])
                                last_sample_time = now
                                if thumbnail_frame is None:
                                    # Crop and store face thumbnail frame
                                    thumbnail_frame = frame[top:bottom, left:right]
                    elif len(face_locations) > 1:
                        # Too many faces
                        for (t, r, b, l) in face_locations:
                            cv2.rectangle(frame_draw, (l, t), (r, b), (0, 0, 255), 2)
                        cv2.putText(
                            frame_draw, "MULTIPLE FACES DETECTED. SCAN BLOCKED.",
                            (10, frame_draw.shape[0] - 20), cv2.FONT_HERSHEY_DUPLEX, 0.5, (0, 0, 255), 1
                        )
                    else:
                        # No face
                        cv2.putText(
                            frame_draw, "NO FACE DETECTED. ALIGN FACE IN FRAME.",
                            (10, frame_draw.shape[0] - 20), cv2.FONT_HERSHEY_DUPLEX, 0.5, (0, 0, 255), 1
                        )

                    # Show feed
                    frame_rgb = cv2.cvtColor(frame_draw, cv2.COLOR_BGR2RGB)
                    feed_placeholder.image(frame_rgb, channels="RGB", width="stretch")

                    # Show progress bar
                    progress_placeholder.progress(len(captured_encodings) / max_samples)
                    
                    time.sleep(0.03)

                # Release webcam
                cap.release()
                
                # Check if we successfully captured all profiles
                if len(captured_encodings) == max_samples:
                    st.success("✅ Facial profile scans completed successfully!")
                    
                    # Save profile thumbnail image
                    photo_filename = f"{details['student_id']}.jpg"
                    photo_path = str(config.PHOTO_DIR / photo_filename)
                    
                    if thumbnail_frame is not None and thumbnail_frame.size > 0:
                        cv2.imwrite(photo_path, thumbnail_frame)
                    else:
                        # Fail-safe write standard placeholder image
                        cv2.imwrite(photo_path, np.zeros((200, 200, 3), dtype=np.uint8))
                    
                    # Create student
                    new_student = Student(
                        student_id=details["student_id"],
                        name=details["name"],
                        roll_no=details["roll_no"],
                        department=details["department"],
                        year=details["year"],
                        division=details["division"],
                        email=details["email"],
                        phone=details["phone"],
                        photo_path=photo_path
                    )
                    
                    # Save to DB
                    success = db_manager.add_student(new_student, captured_encodings)
                    if success:
                        st.balloons()
                        st.session_state.reg_details = None
                        st.info("Registration fully saved. Rerunning directory...")
                        time.sleep(2)
                        st.rerun()
                    else:
                        st.error("Failed to save student profile to the database.")
                else:
                    st.warning("⚠️ Scan cancelled or incomplete. Please toggle off the scan and try again.")
