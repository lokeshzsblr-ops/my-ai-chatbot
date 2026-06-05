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
    page_title="Lokesh's Private AI Chat",
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
    st.title("🔒 Lokesh's Private AI Chat")
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
        "User Email (for AI Guard policy resolution)",
        value=st.secrets.get("USER_EMAIL", DEFAULT_USER),
        placeholder="you@example.com",
        help="AI Guard uses this to resolve which policy applies to you.",
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
    direction: 'OUT' for user prompt -> LLM
               'IN'  for LLM response -> user
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
    payload = {
        "direction": direction,   # "OUT" or "IN"
        "content":   content,
        "userEmail": email,
    }

    try:
        resp = requests.post(ZSCALER_ENDPOINT, json=payload, headers=headers, timeout=30)
        debug["http_status"] = resp.status_code
        try:
            debug["raw_response"] = resp.json()
        except Exception:
            debug["raw_response"] = resp.text[:1000]

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

    label = "Prompt (OUT)" if direction == "OUT" else "Response (IN)"

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
            st.error(f"Error: {err}")

        # Verdict summary
        if isinstance(raw, dict):
            action = raw.get("action", "UNKNOWN").upper()
            if action == "ALLOW":
                st.success(f"Verdict: {action} -- Traffic passed AI Guard")
            elif action == "BLOCK":
                st.error(f"Verdict: {action} -- Traffic blocked by AI Guard")
            elif action == "CAUTION":
                st.warning(f"Verdict: {action} -- Traffic flagged by AI Guard")
            else:
                st.info(f"Verdict: {action}")


# -----------------------------------------------------------------------------
# HELPER: Build Gemini parts list (text + files)
# -----------------------------------------------------------------------------
def build_gemini_parts(prompt_text: str, files: list) -> list:
    parts = []
    for f in files:
        file_bytes = f.read()
        mime_type  = f.type or (mimetypes.guess_type(f.name)[0] or "application/octet-stream")
        b64_data   = base64.standard_b64encode(file_bytes).decode("utf-8")
        inline_mime_prefixes = ("image/", "application/pdf", "text/", "audio/", "video/")
        if any(mime_type.startswith(p) for p in inline_mime_prefixes):
            parts.append({"inline_data": {"mime_type": mime_type, "data": b64_data}})
        else:
            try:
                text_content = file_bytes.decode("utf-8", errors="replace")
                parts.append({"text": f"[Attached file: {f.name}]\n{text_content}"})
            except Exception:
                parts.append({"text": f"[Attached file: {f.name} - binary, {len(file_bytes)} bytes]"})
    parts.append({"text": prompt_text})
    return parts


# -----------------------------------------------------------------------------
# HELPER: Render guard banner
# -----------------------------------------------------------------------------
def render_guard_result(guard_result: dict, label: str):
    action    = guard_result.get("action", "ALLOW").upper()
    detectors = guard_result.get("triggeringDetectors", [])
    msg       = guard_result.get("message", "")
    err       = guard_result.get("error", "")

    if action == "BLOCK":
        det_str = ", ".join(detectors) if detectors else "Policy violation"
        st.markdown(
            f'<div class="block-banner">🚫 <b>Blocked by Zscaler AI Guard</b> [{label}]<br>'
            f'Reason: {det_str or msg}</div>',
            unsafe_allow_html=True,
        )
    elif action == "CAUTION":
        det_str = ", ".join(detectors) if detectors else msg or "Flagged content"
        st.markdown(
            f'<div class="caution-banner">⚠️ <b>AI Guard Caution</b> [{label}]<br>'
            f'Detected: {det_str}</div>',
            unsafe_allow_html=True,
        )
    elif err:
        st.caption(f"ℹ️ AI Guard: {err}")


# -----------------------------------------------------------------------------
# MAIN CHAT UI
# -----------------------------------------------------------------------------
st.title("🔒 Lokesh's Private AI Chat")
st.caption(
    "Your conversations are protected by **Zscaler AI Guard** "
    "-- every prompt and response is inspected before delivery."
)

# Render chat history
for idx, msg in enumerate(st.session_state.messages):
    with st.chat_message(msg["role"]):
        if msg.get("files"):
            st.caption("📎 " + " · ".join(msg["files"]))
        if msg.get("guard_prompt"):
            render_guard_result(msg["guard_prompt"], "Prompt")
        if msg.get("guard_response"):
            render_guard_result(msg["guard_response"], "Response")
        st.markdown(msg["content"])
        if msg["role"] == "assistant" and msg.get("guard_response", {}).get("action") == "ALLOW":
            st.markdown('<span class="allow-badge">✅ Cleared by AI Guard</span>', unsafe_allow_html=True)

        # Show stored debug panels if debug mode is on
        if debug_mode and msg.get("debug_entries"):
            for dbg in msg["debug_entries"]:
                render_debug_panel(dbg)


# -----------------------------------------------------------------------------
# CHAT INPUT
# -----------------------------------------------------------------------------
user_input = st.chat_input("Type your message here...")

if user_input:

    if not gemini_key:
        st.error("Please enter your Google Gemini API Key in the sidebar.")
        st.stop()

    attached_names = [f.name for f in uploaded_files] if uploaded_files else []
    turn_debug_logs = []

    with st.chat_message("user"):
        if attached_names:
            st.caption("📎 " + " · ".join(attached_names))
        st.markdown(user_input)

    # STEP 1: Inspect PROMPT with AI Guard -- direction: OUT
    with st.spinner("🛡️ Zscaler AI Guard inspecting your prompt..."):
        guard_prompt_result, debug_prompt = inspect_with_ai_guard(
            content=user_input,
            direction="OUT",
            api_key=zscaler_key,
            email=user_email,
        )
    turn_debug_logs.append(debug_prompt)

    prompt_action = guard_prompt_result.get("action", "ALLOW").upper()

    # STEP 2: Decide whether to call the LLM
    if prompt_action == "ALLOW":
        should_call_llm = True
    elif prompt_action == "CAUTION":
        should_call_llm = (caution_action == "Allow with warning")
    else:
        should_call_llm = False

    llm_response_text = None
    guard_response_result = {
        "action": "ALLOW",
        "triggeringDetectors": [],
        "message": "Not called",
    }
    debug_response = {
        "direction":    "IN",
        "http_status":  None,
        "raw_response": None,
        "error":        "Skipped - LLM not called",
    }

    if should_call_llm:
        # STEP 3: Call Gemini
        try:
            genai.configure(api_key=gemini_key)
            model = genai.GenerativeModel(GEMINI_MODEL)

            gemini_history = []
            for m in st.session_state.messages:
                role = "user" if m["role"] == "user" else "model"
                gemini_history.append({"role": role, "parts": [{"text": m["content"]}]})

            current_parts = build_gemini_parts(user_input, uploaded_files or [])
            chat = model.start_chat(history=gemini_history)

            with st.spinner("🤖 Gemini is thinking..."):
                response = chat.send_message(current_parts)
                llm_response_text = response.text

        except Exception as e:
            st.error(f"Gemini API error: {e}")
            llm_response_text = None

        # STEP 4: Inspect RESPONSE with AI Guard -- direction: IN
        if llm_response_text:
            with st.spinner("🛡️ Zscaler AI Guard inspecting the response..."):
                guard_response_result, debug_response = inspect_with_ai_guard(
                    content=llm_response_text,
                    direction="IN",
                    api_key=zscaler_key,
                    email=user_email,
                )
            turn_debug_logs.append(debug_response)

    # STEP 5: Determine what to display
    response_action = guard_response_result.get("action", "ALLOW").upper()

    if not should_call_llm:
        detectors = guard_prompt_result.get("triggeringDetectors", [])
        det_str   = ", ".join(detectors) if detectors else guard_prompt_result.get("message", "Policy violation")
        if prompt_action == "CAUTION" and caution_action == "Block":
            display_content = f"Your message was stopped due to a caution flag.\n\n**Detected:** {det_str}"
        else:
            display_content = f"Your message was blocked before reaching the AI.\n\n**Reason:** {det_str}"

    elif llm_response_text is None:
        display_content = "Could not get a response from Gemini. Please check your API key."

    elif response_action == "BLOCK":
        detectors = guard_response_result.get("triggeringDetectors", [])
        det_str   = ", ".join(detectors) if detectors else guard_response_result.get("message", "Policy violation")
        display_content = f"The AI response was blocked by Zscaler AI Guard.\n\n**Reason:** {det_str}"

    elif response_action == "CAUTION" and caution_action == "Block":
        detectors = guard_response_result.get("triggeringDetectors", [])
        det_str   = ", ".join(detectors) if detectors else guard_response_result.get("message", "Flagged content")
        display_content = f"The AI response was held due to a caution flag.\n\n**Detected:** {det_str}"

    else:
        display_content = llm_response_text

    # STEP 6: Render assistant reply
    with st.chat_message("assistant"):
        if should_call_llm and prompt_action == "CAUTION":
            render_guard_result(guard_prompt_result, "Prompt")
        if should_call_llm and response_action in ("BLOCK", "CAUTION"):
            render_guard_result(guard_response_result, "Response")
        if not should_call_llm and prompt_action in ("BLOCK", "CAUTION"):
            render_guard_result(guard_prompt_result, "Prompt")

        st.markdown(display_content)

        if response_action == "ALLOW" and llm_response_text:
            st.markdown('<span class="allow-badge">✅ Cleared by AI Guard</span>', unsafe_allow_html=True)

        # Show live debug panels if debug mode is on
        if debug_mode:
            for dbg in turn_debug_logs:
                render_debug_panel(dbg)

    # STEP 7: Save to session state
    st.session_state.messages.append({
        "role":           "user",
        "content":        user_input,
        "files":          attached_names,
        "guard_prompt":   guard_prompt_result,
        "guard_response": None,
        "debug_entries":  [],
    })
    st.session_state.messages.append({
        "role":           "assistant",
        "content":        display_content,
        "files":          [],
        "guard_prompt":   None,
        "guard_response": guard_response_result if should_call_llm else None,
        "debug_entries":  turn_debug_logs,
    })
