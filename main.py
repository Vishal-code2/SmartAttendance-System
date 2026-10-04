import streamlit as st
import sys
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).resolve().parent))

from config import config
from database.db_manager import DatabaseManager
from app.ui_components import inject_custom_css

# Page Configuration
st.set_page_config(
    page_title="SmartAttend AI - Classroom Analytics",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Load global CSS
inject_custom_css()


def get_biometric_status():
    try:
        import cv2  # noqa: F401
        import face_recognition  # noqa: F401
        return True, None
    except Exception as exc:
        return False, str(exc)


# Initialize Database Manager in session state
if "db_manager" not in st.session_state:
    st.session_state.db_manager = DatabaseManager()

# Initialize Face Engine (Lazy load detector to improve load times for non-CV tabs)
if "detector" not in st.session_state:
    biometric_ready, biometric_error = get_biometric_status()
    if biometric_ready:
        try:
            from face_engine.detector import FaceDetector
            st.session_state.detector = FaceDetector()
        except Exception as e:
            st.session_state.detector = None
            st.warning(
                "Camera-based attendance features are unavailable right now. "
                f"The face engine could not initialize: {e}. "
                "Install the dependencies with: "
                "C:/Users/visha/AppData/Local/Programs/Python/Python312/python.exe -m pip install -r requirements.txt"
            )
    else:
        st.session_state.detector = None
        st.info(
            "Camera-based attendance features are disabled because OpenCV / face-recognition are not available on this machine. "
            f"Detected issue: {biometric_error}. "
            "Install Visual Studio C++ Build Tools if you want facial recognition enabled, then run: "
            "C:/Users/visha/AppData/Local/Programs/Python/Python312/python.exe -m pip install -r requirements.txt"
        )

# Initialize Anti-Proxy Engine in session state so it maintains tracking logs across redraws
if "anti_proxy" not in st.session_state:
    biometric_ready, biometric_error = get_biometric_status()
    if biometric_ready:
        try:
            from face_engine.anti_proxy import AntiProxyEngine
            st.session_state.anti_proxy = AntiProxyEngine()
        except Exception as e:
            st.session_state.anti_proxy = None
            st.warning(
                "Anti-proxy verification is unavailable right now because the face engine did not initialize: "
                f"{e}"
            )
    else:
        st.session_state.anti_proxy = None
        st.info(
            "Anti-proxy verification remains off until the biometric dependencies are installed. "
            f"Reason: {biometric_error}"
        )

db_manager = st.session_state.db_manager
detector = st.session_state.detector
anti_proxy = st.session_state.anti_proxy

# Sidebar Header
st.sidebar.markdown(f"""
    <div style="text-align: center; margin-bottom: 20px;">
        <h2 style="color: #3182CE; margin-bottom: 0px;">🛡️ SmartAttend AI</h2>
        <span style="color: #718096; font-size: 11px;">v{config.VERSION} | Classroom Intelligence</span>
    </div>
    """, unsafe_allow_html=True)
st.sidebar.divider()

# Navigation
menu_options = [
    "🏠 Live Dashboard",
    "👤 Student Registration",
    "📝 Attendance Records",
    "📊 Performance Analytics",
    "🔮 Predictive Risk & Insights",
    "📁 Report Generation",
    "⚙️ System Administration"
]
selected_menu = st.sidebar.radio("Navigate Menu", menu_options)

st.sidebar.divider()
st.sidebar.markdown("""
    <div style="font-size: 11px; color: #718096;">
        <b>Anti-Proxy Settings:</b><br/>
        • Window: 8 samples<br/>
        • Strictness: 55% matching<br/>
        • Multi-face block: Enabled<br/>
        • Photo spoof protect: Active
    </div>
    """, unsafe_allow_html=True)

# Route Menu options to Views
if selected_menu == "🏠 Live Dashboard":
    if detector is None or anti_proxy is None:
        st.info(
            "Live camera and anti-proxy features are unavailable in this environment until the biometric dependencies are installed. "
            "Use the attendance records and analytics pages, or install the camera stack to enable live verification."
        )
    else:
        from app.views.dashboard_view import render_dashboard
        render_dashboard(db_manager, detector, anti_proxy)

elif selected_menu == "👤 Student Registration":
    if detector is None:
        st.info(
            "Student registration with live face capture is unavailable until OpenCV and face-recognition are installed."
        )
    else:
        from app.views.registration_view import render_registration
        render_registration(db_manager, detector)

elif selected_menu == "📝 Attendance Records":
    from app.views.records_view import render_records
    render_records(db_manager)

elif selected_menu == "📊 Performance Analytics":
    from app.views.analytics_view import render_analytics
    render_analytics(db_manager)

elif selected_menu == "🔮 Predictive Risk & Insights":
    from app.views.predictions_view import render_predictions
    render_predictions(db_manager)

elif selected_menu == "📁 Report Generation":
    from app.views.reports_view import render_reports
    render_reports(db_manager)

elif selected_menu == "⚙️ System Administration":
    from app.views.audit_view import render_audit
    render_audit(db_manager)
