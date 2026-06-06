# =============================================================================
# Private Chat App -- Google Gemini 2.5 Flash + Zscaler AI Guard (DAS/API Mode)
# Option 2: resolve-and-execute-policy (no Policy ID required)
# =============================================================================
# Requirements (requirements.txt):
#   streamlit
#   google-generativeai
#   requests
# =============================================================================

import os
import base64
import mimetypes
import requests
import streamlit as st
import google.generativeai as genai

# -----------------------------------------------------------------------------
# CONSTANTS
# -----------------------------------------------------------------------------
ZSCALER_ENDPOINT = "https://api.zseclipse.net/v1/detection/resolve-and-execute-policy"
GEMINI_MODEL     = "gemini-2.5-flash"
DEFAULT_USER     = "lkrishnamoorthy@zscaler.com"

# -----------------------------------------------------------------------------
# PAGE CONFIG
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="Private AI Chat",
    page_icon="🔒",
    layout="wide",
    initial_sidebar_state="expanded",
)

# -----------------------------------------------------------------------------
# CUSTOM CSS
# -----------------------------------------------------------------------------
st.markdown("""
<style>
    .block-banner {
        background-color: #ff4b4b22;
        border: 1px solid #ff4b4b;
        border-radius: 8px;
        padding: 12px 16px;
        color: #ff4b4b;
        font-weight: 600;
        margin-bottom: 8px;
    }
    .caution-banner {
        background-color: #ffa50022;
        border: 1px solid #ffa500;
        border-radius: 8px;
        padding: 12px 16px;
        color: #ffa500;
        font-weight: 600;
        margin-bottom: 8px;
    }
    .allow-badge {
        font-size: 0.75em;
        color: #00cc88;
        font-weight: 600;
    }
    .sidebar-label {
        font-size: 0.85em;
        color: #aaaaaa;
        margin-bottom: 2px;
    }
    .debug-box {
        background-color: #1e1e2e;
        border: 1px solid #444466;
        border-radius: 8px;
        padding: 10px 14px;
        font-size: 0.78em;
        margin-bottom: 6px;
    }
</style>
""", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# SESSION STATE INIT
# -----------------------------------------------------------------------------
if "messages" not in st.session_state:
    st.session_state.messages = []
if "uploaded_file_data" not in st.session_state:
    st.session_state.uploaded_file_data = []
if "debug_logs" not in st.session_state:
    st.session_state.debug_logs = []

# -----------------------------------------------------------------------------
# SIDEBAR
# -----------------------------------------------------------------------------
with st.sidebar:
    st.title("🔒 Private AI Chat")
    st.caption("Powered by Gemini + Zscaler AI Guard")
    st.divider()

    # Model display (read-only)
    st.markdown('<p class="sidebar-label">🤖 LLM Model</p>', unsafe_allow_html=True)
    st.info(f"**{GEMINI_MODEL}**", icon="🧠")

    st.divider()

    # API Keys
    st.markdown("### 🔑 API Keys")
    gemini_key = st.text_input(
        "Google Gemini API Key",
        value=st.secrets.get("GEMINI_API_KEY", ""),
        type="password",
        placeholder="AIza...",
        help="Get your key from https://aistudio.google.com/",
    )
    zscaler_key = st.text_input(
        "Zscaler AI Guard API Key",
        value=st.secrets.get("ZSCALER_API_KEY", ""),
        type="password",
        placeholder="Bearer token from ZIA console",
        help="ZIA Admin > AI Security > AI Guard > Application Key",
    )
    user_email = st.text_input(
        "User Email (optional)",
        value=st.secrets.get("USER_EMAIL", DEFAULT_USER),
        placeholder="you@example.com",
        help="Optional. Leave blank if your AI Guard policy is not user-scoped.",
    )

    st.divider()

    # Guard settings
    st.markdown("### ⚙️ Guard Settings")
    caution_action = st.radio(
        "CAUTION action",
        options=["Allow with warning", "Block"],
        index=0,
        help="What to do when AI Guard returns CAUTION on a prompt or response.",
    )

    # Debug mode toggle
    debug_mode = st.toggle(
        "🔬 Debug Mode",
        value=False,
        help="Show raw AI Guard API responses in the chat for every message turn.",
    )

    st.divider()

    # File uploader -- all formats
    st.markdown("### 📎 Attach Files / Images")
    uploaded_files = st.file_uploader(
        "Upload any file(s)",
        accept_multiple_files=True,
        type=None,
        help="Attach files to include in your next message to Gemini.",
        label_visibility="collapsed",
    )

    if uploaded_files:
        st.success(f"{len(uploaded_files)} file(s) ready to send")
        for f in uploaded_files:
            st.caption(f"📄 {f.name}  `{round(f.size / 1024, 1)} KB`")

    st.divider()

    # Clear chat
    if st.button("🗑️ Clear Chat", use_container_width=True, type="secondary"):
        st.session_state.messages = []
        st.session_state.uploaded_file_data = []
        st.session_state.debug_logs = []
        st.rerun()

    # Endpoint info
    st.markdown('<p class="sidebar-label">🛡️ AI Guard Endpoint</p>', unsafe_allow_html=True)
    st.code("resolve-and-execute-policy", language=None)
    st.caption("Option 2 - No Policy ID required")


# -----------------------------------------------------------------------------
# HELPER: Zscaler AI Guard Inspection
# -----------------------------------------------------------------------------
def inspect_with_ai_guard(content: str, direction: str, api_key: str, email: str) -> tuple:
    """
    Call Zscaler AI Guard Option 2 - resolve-and-execute-policy.
    direction: 'outbound' for user prompt -> LLM
               'inbound'  for LLM response -> user
    userEmail is optional -- only included if provided.
    Returns (result_dict, debug_dict). Fails open on any error.
    """
    debug = {
        "direction":    direction,
        "http_status":  None,
        "raw_response": None,
        "error":        None,
    }

    if not api_key:
        result = {
            "action": "ALLOW",
            "message": "AI Guard not configured (no API key)",
            "triggeringDetectors": [],
        }
        debug["error"] = "No API key provided"
        return result, debug

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    # Build payload -- userEmail is optional, only add if provided
    payload = {
        "direction": direction,
        "content":   content,
    }
    if email and email.strip():
        payload["userEmail"] = email.strip()

    try:
        resp = requests.post(ZSCALER_ENDPOINT, json=payload, headers=headers, timeout=30)
        debug["http_status"] = resp.status_code
        try:
            debug["raw_response"] = resp.json()
        except Exception:
            debug["raw_response"] = resp.text[:1000]

        # Handle 404 explicitly -- policy not found for this API key
        if resp.status_code == 404:
            debug["error"] = (
                "404 - No AI Guard policy found. "
                "Check that your API key is linked to an AI Guard Application in "
                "ZIA Admin > AI Security > AI Guard > Applications."
            )
            return {
                "action":  "ALLOW",
                "message": "No AI Guard policy found for this API key (fail-open)",
                "triggeringDetectors": [],
            }, debug

        resp.raise_for_status()
        return resp.json(), debug

    except requests.exceptions.Timeout:
        debug["error"] = "Request timed out after 30s"
        return {"action": "ALLOW", "error": "AI Guard timeout - proceeding (fail-open)"}, debug

    except requests.exceptions.HTTPError as e:
        debug["error"] = f"HTTP error: {e}"
        return {"action": "ALLOW", "error": f"AI Guard HTTP error: {e}"}, debug

    except requests.exceptions.ConnectionError as e:
        debug["error"] = f"Connection error: {e}"
        return {"action": "ALLOW", "error": f"AI Guard connection error: {e}"}, debug

    except Exception as e:
        debug["error"] = f"Unexpected error: {e}"
        return {"action": "ALLOW", "error": f"AI Guard error: {e}"}, debug


# -----------------------------------------------------------------------------
# HELPER: Render debug panel for one AI Guard call
# -----------------------------------------------------------------------------
def render_debug_panel(debug: dict):
    direction = debug.get("direction", "unknown")
    status    = debug.get("http_status")
    raw       = debug.get("raw_response")
    err       = debug.get("error")

    label = "Prompt (outbound)" if direction == "outbound" else "Response (inbound)"

    if status == 200:
        status_icon = "✅"
    elif status is None:
        status_icon = "⚪"
    else:
        status_icon = "❌"

    with st.expander(f"🔬 AI Guard Debug -- {label}  {status_icon}", expanded=True):
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**Direction**")
            st.code(direction, language=None)
        with col2:
            st.markdown("**HTTP Status**")
            st.code(str(status) if status else "N/A", language=None)

        if raw:
            st.markdown("**Raw API Response**")
            if isinstance(raw, dict):
                st.json(raw)
            else:
                st.code(str(raw), language=None)

        if err:
            st.warning(f"ℹ️ {err}")

        # Verdict summary
        if isinstance(raw, dict):
            action = raw.get("action", "UNKNOWN").upper()
            if action == "ALLOW":
                st.success(f"Verdict: {action} -- Traffic passed AI Guard")
            elif action == "BLOCK":
                st.error(f"Verdict: {action} -- Traffic blocked by AI Guard")
            elif action == "CAUTION":
                st.warning(f"Verdict: {action} -- Traffic flagged by AI Guard")
            elif raw.get("statusCode") == 404:
                st.warning("Verdict: POLICY NOT FOUND -- See error above")
            else:
                st.info(f"Verdict: {action}")


# --------------------------------------------------------------
