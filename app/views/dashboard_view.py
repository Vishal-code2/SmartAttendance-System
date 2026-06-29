import time
import cv2
import datetime
import numpy as np
import streamlit as st
from config import config
from utils.logger import setup_logger
from app.ui_components import render_header
from models.attendance import Attendance

logger = setup_logger("dashboard_view")

def render_dashboard(db_manager, detector, anti_proxy_engine):
    render_header(
        title="Classroom Intelligence Hub",
        subtitle="Real-time face detection, anti-proxy verification, and automated attendance logging."
    )

    # 1. KPIs Section (Dynamic Metrics)
    from analytics.engine import AnalyticsEngine
    analytics = AnalyticsEngine(db_manager)
    kpis = analytics.get_kpis_today()

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Enrolled", kpis["total_students"])
    with col2:
        st.metric("Present Today", kpis["present_count"])
    with col3:
        st.metric("Absent Today", kpis["absent_count"])
    with col4:
        st.metric("Attendance % Today", f"{kpis['attendance_rate']}%")

    st.divider()

    # Create Columns for Live Feed and Tracking Analytics side-by-side
    feed_col, tracking_col = st.columns([3, 2])

    with feed_col:
        st.subheader("Live Video Analysis Feed")
        
        # Load all enrolled encodings
        known_encodings = db_manager.get_all_encodings()
        
        if not known_encodings:
            st.warning("⚠️ No student faces enrolled yet. Please go to the 'Student Registration' page to enroll students first.")
            return

        # Start / Stop Session
        session_active = st.checkbox("🟢 Start Attendance Session", value=False)
        
        # Image placeholder in Streamlit
        frame_placeholder = st.empty()

    with tracking_col:
        st.subheader("Live Verification Panel")
        tracking_placeholder = st.empty()
        st.subheader("Session Activity Log")
        log_placeholder = st.empty()

    # Main Live Loop
    if session_active:
        cap = cv2.VideoCapture(config.CAMERA_INDEX)
        if not cap.isOpened():
            st.error("Error: Could not access the webcam. Check camera index configuration.")
            logger.error(f"Failed to open webcam at index {config.CAMERA_INDEX}")
            return

        logger.info("Live attendance session started.")
        db_manager.log_action("Live Attendance Session Started")

        # Session log helper
        session_logs = ["Session initialized. Monitoring camera..."]

        while session_active:
            ret, frame = cap.read()
            if not ret:
                st.error("Error reading from webcam.")
                break

            # Mirror frame for intuitive view
            frame = cv2.flip(frame, 1)
            
            # Detect faces
            face_locations = detector.detect_faces(frame)
            total_faces = len(face_locations)
            
            # Extract encodings
            encodings = detector.extract_encodings(frame, face_locations)
            
            # Track faces across frames
            tracked_faces = anti_proxy_engine.track_faces(face_locations)

            # Verification tracking list for sidebar panel
            tracking_info_list = []

            # Map coordinates and draw
            for i, face_loc in enumerate(face_locations):
                top, right, bottom, left = face_loc
                
                # Find matching tracked face object
                # Centroid match
                centroid_x = int((left + right) / 2)
                centroid_y = int((top + bottom) / 2)
                
                current_face = None
                best_dist = float("inf")
                for tf in tracked_faces:
                    dx = tf.centroid[0] - centroid_x
                    dy = tf.centroid[1] - centroid_y
                    dist = (dx*dx + dy*dy) ** 0.5
                    if dist < best_dist:
                        best_dist = dist
                        current_face = tf

                if current_face is not None and best_dist > anti_proxy_engine.max_distance:
                    current_face = None
                
                if not current_face:
                    continue

                # Recognize encoding
                encoding = encodings[i] if i < len(encodings) else None
                matched_id = None
                confidence = 0.0

                if encoding is not None:
                    matched_id, confidence = detector.match_face(encoding, known_encodings)
                    current_face.add_match(matched_id, confidence)
                    print(
                    f"[VERIFY] FaceID={current_face.face_id} "
                    f"Matches={len(current_face.student_ids)} "
                    f"Matched={matched_id} "
                    f"Conf={confidence:.2f}"
                    )

                # Analyze anti-proxy risk and validation requirements
                is_verified, student_id, avg_conf, status_msg = anti_proxy_engine.verify_face_for_attendance(
                    current_face, total_faces
                )

                # Determine overlay variables
                box_color = (0, 0, 255)  # Red for unknown/alert default
                label_text = "Analyzing..."

                # Determine which identity to display immediately
                display_id = student_id if student_id else matched_id

                if display_id:
                    student = db_manager.get_student(display_id)
                    student_name = student.name if student else display_id

                    today_str = datetime.date.today().strftime("%Y-%m-%d")
                    already_marked = len(
                        db_manager.get_attendance_records(
                            date=today_str,
                            student_id=display_id
                        )
                    ) > 0

                    if already_marked:
                        box_color = (0,255,0)
                        label_text = f"✓ Marked: {student_name}"
                        current_face.is_marked = True
                        current_face.marked_student_id = display_id

                    elif is_verified and student_id:
                        now = datetime.datetime.now()
                        new_att = Attendance(
                            student_id=student_id,
                            date=today_str,
                            time=now.strftime("%H:%M:%S"),
                            confidence_score=avg_conf,
                            verification_status=status_msg
                        )
                        if db_manager.mark_attendance(new_att):
                            log_msg=f"Marked {student_name} present at {now.strftime('%H:%M:%S')} ({status_msg})"
                            session_logs.insert(0,log_msg)
                            logger.info(log_msg)

                        box_color=(0,255,0)
                        label_text=f"✓ MARKED: {student_name}"
                        current_face.is_marked=True
                        current_face.marked_student_id=student_id

                    else:
                        box_color=(0,255,255)
                        progress=min(int((current_face.frame_count/config.MIN_VERIFICATION_FRAMES)*100),100)
                        label_text=f"{student_name} ({confidence*100:.1f}%) - Verifying {progress}%"

                else:
                    if "Proxy Warning" in status_msg:
                        box_color=(0,165,255)
                        label_text=status_msg
                    else:
                        box_color=(0,0,255)
                        label_text="Unknown Face"

                # Draw Bounding Box & Label
                cv2.rectangle(frame, (left, top), (right, bottom), box_color, 2)
                cv2.rectangle(frame, (left, top - 25), (right, top), box_color, cv2.FILLED)
                cv2.putText(
                    frame, label_text, (left + 6, top - 6),
                    cv2.FONT_HERSHEY_DUPLEX, 0.5, (0, 0, 0), 1
                )

                # Gather panel info
                risk_analysis = anti_proxy_engine.analyze_proxy_risk(current_face, total_faces)
                tracking_info_list.append({
                    "face_id": current_face.face_id,
                    "student_name": db_manager.get_student(display_id).name if display_id and db_manager.get_student(display_id) else (display_id or "Unknown"),
                    "frames": f"{current_face.frame_count}/{config.MIN_VERIFICATION_FRAMES}",
                    "confidence": f"{int(avg_conf * 100)}%" if avg_conf > 0 else "0%",
                    "proxy_risk": f"{risk_analysis['proxy_risk_score']}%",
                    "status": status_msg
                })

            # Render live image in streamlit
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            frame_placeholder.image(frame_rgb, channels="RGB", width="stretch")

            # Update live verification stats panel
            if tracking_info_list:
                panel_html = "<div style='font-size:13px; line-height:1.6;'>"
                for item in tracking_info_list:
                    risk_color = "red" if float(item["proxy_risk"].replace("%","")) > 40 else ("orange" if float(item["proxy_risk"].replace("%","")) > 20 else "green")
                    panel_html += f"""
                    <div style='background-color: black; border: 1px solid #E2E8F0; padding: 12px; border-radius: 8px; margin-bottom: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.05);'>
                        <b>Face ID:</b> #{item['face_id']} | <b>Target Student:</b> {item['student_name']}<br/>
                        <b>Samples Tracked:</b> {item['frames']} | <b>Match Match:</b> {item['confidence']}<br/>
                        <b>Anti-Proxy Risk:</b> <span style='color: {risk_color}; font-weight: bold;'>{item['proxy_risk']}</span><br/>
                        <b>Status:</b> <span style='color: #4A5568; font-weight: bold;'>{item['status']}</span>
                    </div>
                    """
                panel_html += "</div>"
                tracking_placeholder.markdown(panel_html, unsafe_allow_html=True)
            else:
                tracking_placeholder.info("No active faces in view.")

            # Update Log Panel
            log_placeholder.markdown(
                f"<div style='background-color:#0F172A; color:#10B981; font-family:Courier, monospace; padding:15px; border-radius:8px; height:180px; overflow-y:auto; font-size:12px; line-height:1.5;'>"
                f"{'<br/>'.join(session_logs[:8])}</div>",
                unsafe_allow_html=True
            )

            # Small sleep to yield CPU cycles
            time.sleep(0.03)

        # Release webcam when session is toggled off
        cap.release()
        logger.info("Live attendance session ended.")
        db_manager.log_action("Live Attendance Session Stopped")
        st.success("Attendance session stopped. Camera released.")

        
