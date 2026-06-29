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

# Initialize Database Manager in session state
if "db_manager" not in st.session_state:
    st.session_state.db_manager = DatabaseManager()

# Initialize Face Engine (Lazy load detector to improve load times for non-CV tabs)
if "detector" not in st.session_state:
    try:
        from face_engine.detector import FaceDetector
        st.session_state.detector = FaceDetector()
    except Exception as e:
        st.session_state.detector = None
        st.error(f"Failed to load biometric detection engine: {e}")

# Initialize Anti-Proxy Engine in session state so it maintains tracking logs across redraws
if "anti_proxy" not in st.session_state:
    try:
        from face_engine.anti_proxy import AntiProxyEngine
        st.session_state.anti_proxy = AntiProxyEngine()
    except Exception as e:
        st.session_state.anti_proxy = None
        st.error(f"Failed to load anti-proxy engine: {e}")

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
        st.error("Biometric libraries (face_recognition/cv2) failed to load. Check installation logs.")
    else:
        from app.views.dashboard_view import render_dashboard
        render_dashboard(db_manager, detector, anti_proxy)

elif selected_menu == "👤 Student Registration":
    if detector is None:
        st.error("Biometric libraries failed to load.")
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
