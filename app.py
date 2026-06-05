# =============================================================================
# Private Chat App — Google Gemini 2.5 Flash + Zscaler AI Guard (DAS/API Mode)
# Option 2: resolve-and-execute-policy (no Policy ID required)
# =============================================================================
# Requirements:
#   pip install streamlit google-generativeai requests python-dotenv
# =============================================================================

import os
import base64
import mimetypes
import requests
import streamlit as st
from dotenv import load_dotenv
import google.generativeai as genai

# ── Load .env if present ─────────────────────────────────────────────────────
load_dotenv()

# ── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Private AI Chat",
    page_icon="🔒",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ────────────────────────────────────────────────────────────────
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
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# CONSTANTS
# ─────────────────────────────────────────────────────────────────────────────
ZSCALER_ENDPOINT = "https://api.zseclipse.net/v1/detection/resolve-and-execute-policy"
GEMINI_MODEL     = "gemini-2.5-flash"
DEFAULT_USER     = "lkrishnamoorthy@zscaler.com"

# ─────────────────────────────────────────────────────────────────────────────
# SESSION STATE INIT
# ─────────────────────────────────────────────────────────────────────────────
if "messages" not in st.session_state:
    st.session_state.messages = []   # list of {role, content, guard_status, triggered}
if "uploaded_file_data" not in st.session_state:
    st.session_state.uploaded_file_data = []

# ─────────────────────────────────────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("🔒 Private AI Chat")
    st.caption("Powered by Gemini + Zscaler AI Guard")
    st.divider()

    # ── Model info (read-only display) ────────────────────────────────────────
    st.markdown('<p class="sidebar-label">🤖 LLM Model</p>', unsafe_allow_html=True)
    st.info(f"**{GEMINI_MODEL}**", icon="🧠")

    st.divider()

    # ── API Keys ──────────────────────────────────────────────────────────────
    st.markdown("### 🔑 API Keys")
    gemini_key = st.text_input(
        "Google Gemini API Key",
        value=os.getenv("GEMINI_API_KEY", ""),
        type="password",
        placeholder="AIza...",
        help="Get your key from https://aistudio.google.com/",
    )
    zscaler_key = st.text_input(
        "Zscaler AI Guard API Key",
        value=os.getenv("ZSCALER_API_KEY", ""),
        type="password",
        placeholder="Bearer token from ZIA console",
        help="ZIA Admin → AI Security → AI Guard → Application Key",
    )
    user_email = st.text_input(
        "User Email (for AI Guard policy resolution)",
        value=DEFAULT_USER,
        placeholder="you@example.com",
        help="AI Guard uses this to resolve which policy applies to you.",
    )

    st.divider()

    # ── CAUTION behaviour ─────────────────────────────────────────────────────
    st.markdown("### ⚙️ Guard Settings")
    caution_action = st.radio(
        "CAUTION action",
        options=["Allow with warning", "Block"],
        index=0,
        help="What to do when AI Guard returns CAUTION on a prompt or response.",
    )

    st.divider()

    # ── File Upload (all formats) ─────────────────────────────────────────────
    st.markdown("### 📎 Attach Files / Images")
    uploaded_files = st.file_uploader(
        "Upload any file(s) — images, PDFs, text, etc.",
        accept_multiple_files=True,
        type=None,        # ← accepts ALL file formats
        help="Attach files to include in your next message to Gemini.",
        label_visibility="collapsed",
    )

    if uploaded_files:
        st.success(f"{len(uploaded_files)} file(s) ready to send")
        for f in uploaded_files:
            st.caption(f"📄 {f.name}  `{round(f.size/1024, 1)} KB`")

    st.divider()

    # ── Clear chat ────────────────────────────────────────────────────────────
    if st.button("🗑️ Clear Chat", use_container_width=True, type="secondary"):
        st.session_state.messages = []
        st.session_state.uploaded_file_data = []
        st.rerun()

    # ── Guard endpoint (info) ─────────────────────────────────────────────────
    st.markdown('<p class="sidebar-label">🛡️ AI Guard Endpoint</p>', unsafe_allow_html=True)
    st.code("resolve-and-execute-policy", language=None)
    st.caption("Option 2 · No Policy ID required")


# ─────────────────────────────────────────────────────────────────────────────
# HELPER: Zscaler AI Guard Inspection
# ─────────────────────────────────────────────────────────────────────────────
def inspect_with_ai_guard(content: str, direction: str, api_key: str, email: str) -> dict:
    """
    Call Zscaler AI Guard Option 2 — resolve-and-execute-policy.

    Args:
        content   : The text to inspect (prompt or LLM response)
        direction : "outbound" for user prompt → LLM
                    "inbound"  for LLM response → user
        api_key   : Zscaler AI Guard Bearer token
        email     : End-user email for policy resolution

    Returns:
        dict with keys: action (ALLOW/BLOCK/CAUTION), message, triggeringDetectors
        On failure returns {"action": "ALLOW", "error": "<msg>"} — fail-open
    """
    if not api_key:
        # No key configured → fail-open (skip guard)
        return {"action": "ALLOW", "message": "AI Guard not configured (no API key)", "triggeringDetectors": []}

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "direction": direction,
        "content":   content,
        "userEmail": email,
    }
    try:
        resp = requests.post(ZSCALER_ENDPOINT, json=payload, headers=headers, timeout=30)
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.Timeout:
        return {"action": "ALLOW", "error": "AI Guard timeout — proceeding (fail-open)"}
    except requests.exceptions.HTTPError as e:
        return {"action": "ALLOW", "error": f"AI Guard HTTP error: {e}"}
    except Exception as e:
        return {"action": "ALLOW", "error": f"AI Guard error: {e}"}


# ─────────────────────────────────────────────────────────────────────────────
# HELPER: Build Gemini parts list (text + files)
# ─────────────────────────────────────────────────────────────────────────────
def build_gemini_parts(prompt_text: str, files: list) -> list:
    """
    Build the parts list for Gemini, including inline file data where supported.
    Supported inline MIME types: image/*, application/pdf, text/*, audio/*, video/*
    """
    parts = []

    for f in files:
        file_bytes = f.read()
        mime_type  = f.type or (mimetypes.guess_type(f.name)[0] or "application/octet-stream")
        b64_data   = base64.standard_b64encode(file_bytes).decode("utf-8")

        # Gemini inline_data supports images, pdf, audio, video, plain text
        inline_mime_prefixes = ("image/", "application/pdf", "text/", "audio/", "video/")
        if any(mime_type.startswith(p) for p in inline_mime_prefixes):
            parts.append({"inline_data": {"mime_type": mime_type, "data": b64_data}})
        else:
            # For unsupported types, attach as plain text description
            try:
                text_content = file_bytes.decode("utf-8", errors="replace")
                parts.append({"text": f"[Attached file: {f.name}]\n{text_content}"})
            except Exception:
                parts.append({"text": f"[Attached file: {f.name} — binary content, {len(file_bytes)} bytes]"})

    # Add the user's text prompt last
    parts.append({"text": prompt_text})
    return parts


# ─────────────────────────────────────────────────────────────────────────────
# HELPER: Render guard badge
# ─────────────────────────────────────────────────────────────────────────────
def render_guard_result(guard_result: dict, label: str):
    action   = guard_result.get("action", "ALLOW").upper()
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


# ─────────────────────────────────────────────────────────────────────────────
# MAIN CHAT UI
# ─────────────────────────────────────────────────────────────────────────────
st.title("🔒 Private AI Chat")
st.caption(
    "Your conversations are protected by **Zscaler AI Guard** — "
    "every prompt and response is inspected before delivery."
)

# ── Render chat history ───────────────────────────────────────────────────────
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        # Show any attached file names
        if msg.get("files"):
            st.caption("📎 " + " · ".join(msg["files"]))

        # Guard result banners (stored per message)
        if msg.get("guard_prompt"):
            render_guard_result(msg["guard_prompt"], "Prompt")
        if msg.get("guard_response"):
            render_guard_result(msg["guard_response"], "Response")

        st.markdown(msg["content"])

        if msg["role"] == "assistant" and msg.get("guard_response", {}).get("action") == "ALLOW":
            st.markdown('<span class="allow-badge">✅ Cleared by AI Guard</span>', unsafe_allow_html=True)


# ── Chat input ────────────────────────────────────────────────────────────────
user_input = st.chat_input("Type your message here…")

if user_input:

    # ── Validate API keys ─────────────────────────────────────────────────────
    if not gemini_key:
        st.error("⚠️ Please enter your **Google Gemini API Key** in the sidebar.")
        st.stop()

    # ── Collect attached files ────────────────────────────────────────────────
    attached_names = [f.name for f in uploaded_files] if uploaded_files else []

    # ── Display user message ──────────────────────────────────────────────────
    with st.chat_message("user"):
        if attached_names:
            st.caption("📎 " + " · ".join(attached_names))
        st.markdown(user_input)

    # ── STEP 1: Inspect PROMPT with AI Guard (direction: outbound) ────────────
    with st.spinner("🛡️ Zscaler AI Guard inspecting your prompt…"):
        guard_prompt_result = inspect_with_ai_guard(
            content=user_input,
            direction="outbound",
            api_key=zscaler_key,
            email=user_email,
        )

    prompt_action = guard_prompt_result.get("action", "ALLOW").upper()

    # ── STEP 2: Decide whether to proceed to LLM ─────────────────────────────
    should_call_llm = False
    if prompt_action == "ALLOW":
        should_call_llm = True
    elif prompt_action == "CAUTION":
        should_call_llm = (caution_action == "Allow with warning")
    elif prompt_action == "BLOCK":
        should_call_llm = False

    llm_response_text = None
    guard_response_result = {"action": "ALLOW", "triggeringDetectors": [], "message": "Not called"}

    if should_call_llm:
        # ── STEP 3: Call Google Gemini 2.5 Flash ─────────────────────────────
        try:
            genai.configure(api_key=gemini_key)
            model = genai.GenerativeModel(GEMINI_MODEL)

            # Build conversation history for Gemini
            gemini_history = []
            for m in st.session_state.messages:
                role = "user" if m["role"] == "user" else "model"
                gemini_history.append({"role": role, "parts": [{"text": m["content"]}]})

            # Build current turn parts (text + any attached files)
            current_parts = build_gemini_parts(user_input, uploaded_files or [])

            # Start chat with history and send current message
            chat = model.start_chat(history=gemini_history)

            with st.spinner("🤖 Gemini is thinking…"):
                response = chat.send_message(current_parts)
                llm_response_text = response.text

        except Exception as e:
            st.error(f"❌ Gemini API error: {e}")
            llm_response_text = None

        # ── STEP 4: Inspect RESPONSE with AI Guard (direction: inbound) ───────
        if llm_response_text:
            with st.spinner("🛡️ Zscaler AI Guard inspecting the response…"):
                guard_response_result = inspect_with_ai_guard(
                    content=llm_response_text,
                    direction="inbound",
                    api_key=zscaler_key,
                    email=user_email,
                )

    # ── STEP 5: Determine final response to show ──────────────────────────────
    response_action = guard_response_result.get("action", "ALLOW").upper()

    if not should_call_llm:
        # Prompt was blocked or cautioned+blocked
        detectors = guard_prompt_result.get("triggeringDetectors", [])
        det_str   = ", ".join(detectors) if detectors else guard_prompt_result.get("message", "Policy violation")
        display_content = f"🚫 Your message was **blocked** before reaching the AI.\n\n**Reason:** {det_str}"
        if prompt_action == "CAUTION" and caution_action == "Block":
            display_content = f"⚠️ Your message was **stopped** due to a caution flag.\n\n**Detected:** {det_str}"
        final_role = "assistant"

    elif llm_response_text is None:
        display_content = "❌ Could not get a response from Gemini. Please check your API key."
        final_role = "assistant"

    elif response_action == "BLOCK":
        detectors = guard_response_result.get("triggeringDetectors", [])
        det_str   = ", ".join(detectors) if detectors else guard_response_result.get("message", "Policy violation")
        display_content = f"🚫 The AI's response was **blocked** by Zscaler AI Guard.\n\n**Reason:** {det_str}"
        final_role = "assistant"

    elif response_action == "CAUTION" and caution_action == "Block":
        detectors = guard_response_result.get("triggeringDetectors", [])
        det_str   = ", ".join(detectors) if detectors else guard_response_result.get("message", "Flagged content")
        display_content = f"⚠️ The AI's response was **held** due to a caution flag.\n\n**Detected:** {det_str}"
        final_role = "assistant"

    else:
        # ALLOW or CAUTION+allow-with-warning
        display_content = llm_response_text
        final_role = "assistant"

    # ── STEP 6: Render assistant message ──────────────────────────────────────
    with st.chat_message("assistant"):
        if should_call_llm and prompt_action == "CAUTION":
            render_guard_result(guard_prompt_result, "Prompt")

        if response_action in ("BLOCK", "CAUTION") and should_call_llm:
            render_guard_result(guard_response_result, "Response")

        if not should_call_llm and prompt_action in ("BLOCK", "CAUTION"):
            render_guard_result(guard_prompt_result, "Prompt")

        st.markdown(display_content)

        if final_role == "assistant" and response_action == "ALLOW" and llm_response_text:
            st.markdown('<span class="allow-badge">✅ Cleared by AI Guard</span>', unsafe_allow_html=True)

    # ── STEP 7: Persist to session state ──────────────────────────────────────
    st.session_state.messages.append({
        "role":           "user",
        "content":        user_input,
        "files":          attached_names,
        "guard_prompt":   guard_prompt_result,
        "guard_response": None,
    })
    st.session_state.messages.append({
        "role":           "assistant",
        "content":        display_content,
        "files":          [],
        "guard_prompt":   None,
        "guard_response": guard_response_result if should_call_llm else None,
    })
```Here is the complete `app.py` — copy and paste the entire block:

```python
# =============================================================================
# Private Chat App — Google Gemini 2.5 Flash + Zscaler AI Guard (DAS/API Mode)
# Option 2: resolve-and-execute-policy (no Policy ID required)
# =============================================================================
# Requirements:
#   pip install streamlit google-generativeai requests python-dotenv
# =============================================================================

import os
import base64
import mimetypes
import requests
import streamlit as st
from dotenv import load_dotenv
import google.generativeai as genai

# ── Load .env if present ─────────────────────────────────────────────────────
load_dotenv()

# ── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Private AI Chat",
    page_icon="🔒",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ────────────────────────────────────────────────────────────────
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
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# CONSTANTS
# ─────────────────────────────────────────────────────────────────────────────
ZSCALER_ENDPOINT = "https://api.zseclipse.net/v1/detection/resolve-and-execute-policy"
GEMINI_MODEL     = "gemini-2.5-flash"
DEFAULT_USER     = "lkrishnamoorthy@zscaler.com"

# ─────────────────────────────────────────────────────────────────────────────
# SESSION STATE INIT
# ─────────────────────────────────────────────────────────────────────────────
if "messages" not in st.session_state:
    st.session_state.messages = []   # list of {role, content, guard_status, triggered}
if "uploaded_file_data" not in st.session_state:
    st.session_state.uploaded_file_data = []

# ─────────────────────────────────────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("🔒 Private AI Chat")
    st.caption("Powered by Gemini + Zscaler AI Guard")
    st.divider()

    # ── Model info (read-only display) ────────────────────────────────────────
    st.markdown('<p class="sidebar-label">🤖 LLM Model</p>', unsafe_allow_html=True)
    st.info(f"**{GEMINI_MODEL}**", icon="🧠")

    st.divider()

    # ── API Keys ──────────────────────────────────────────────────────────────
    st.markdown("### 🔑 API Keys")
    gemini_key = st.text_input(
        "Google Gemini API Key",
        value=os.getenv("GEMINI_API_KEY", ""),
        type="password",
        placeholder="AIza...",
        help="Get your key from https://aistudio.google.com/",
    )
    zscaler_key = st.text_input(
        "Zscaler AI Guard API Key",
        value=os.getenv("ZSCALER_API_KEY", ""),
        type="password",
        placeholder="Bearer token from ZIA console",
        help="ZIA Admin → AI Security → AI Guard → Application Key",
    )
    user_email = st.text_input(
        "User Email (for AI Guard policy resolution)",
        value=DEFAULT_USER,
        placeholder="you@example.com",
        help="AI Guard uses this to resolve which policy applies to you.",
    )

    st.divider()

    # ── CAUTION behaviour ─────────────────────────────────────────────────────
    st.markdown("### ⚙️ Guard Settings")
    caution_action = st.radio(
        "CAUTION action",
        options=["Allow with warning", "Block"],
        index=0,
        help="What to do when AI Guard returns CAUTION on a prompt or response.",
    )

    st.divider()

    # ── File Upload (all formats) ─────────────────────────────────────────────
    st.markdown("### 📎 Attach Files / Images")
    uploaded_files = st.file_uploader(
        "Upload any file(s) — images, PDFs, text, etc.",
        accept_multiple_files=True,
        type=None,        # ← accepts ALL file formats
        help="Attach files to include in your next message to Gemini.",
        label_visibility="collapsed",
    )

    if uploaded_files:
        st.success(f"{len(uploaded_files)} file(s) ready to send")
        for f in uploaded_files:
            st.caption(f"📄 {f.name}  `{round(f.size/1024, 1)} KB`")

    st.divider()

    # ── Clear chat ────────────────────────────────────────────────────────────
    if st.button("🗑️ Clear Chat", use_container_width=True, type="secondary"):
        st.session_state.messages = []
        st.session_state.uploaded_file_data = []
        st.rerun()

    # ── Guard endpoint (info) ─────────────────────────────────────────────────
    st.markdown('<p class="sidebar-label">🛡️ AI Guard Endpoint</p>', unsafe_allow_html=True)
    st.code("resolve-and-execute-policy", language=None)
    st.caption("Option 2 · No Policy ID required")


# ─────────────────────────────────────────────────────────────────────────────
# HELPER: Zscaler AI Guard Inspection
# ─────────────────────────────────────────────────────────────────────────────
def inspect_with_ai_guard(content: str, direction: str, api_key: str, email: str) -> dict:
    """
    Call Zscaler AI Guard Option 2 — resolve-and-execute-policy.

    Args:
        content   : The text to inspect (prompt or LLM response)
        direction : "outbound" for user prompt → LLM
                    "inbound"  for LLM response → user
        api_key   : Zscaler AI Guard Bearer token
        email     : End-user email for policy resolution

    Returns:
        dict with keys: action (ALLOW/BLOCK/CAUTION), message, triggeringDetectors
        On failure returns {"action": "ALLOW", "error": "<msg>"} — fail-open
    """
    if not api_key:
        # No key configured → fail-open (skip guard)
        return {"action": "ALLOW", "message": "AI Guard not configured (no API key)", "triggeringDetectors": []}

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "direction": direction,
        "content":   content,
        "userEmail": email,
    }
    try:
        resp = requests.post(ZSCALER_ENDPOINT, json=payload, headers=headers, timeout=30)
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.Timeout:
        return {"action": "ALLOW", "error": "AI Guard timeout — proceeding (fail-open)"}
    except requests.exceptions.HTTPError as e:
        return {"action": "ALLOW", "error": f"AI Guard HTTP error: {e}"}
    except Exception as e:
        return {"action": "ALLOW", "error": f"AI Guard error: {e}"}


# ─────────────────────────────────────────────────────────────────────────────
# HELPER: Build Gemini parts list (text + files)
# ─────────────────────────────────────────────────────────────────────────────
def build_gemini_parts(prompt_text: str, files: list) -> list:
    """
    Build the parts list for Gemini, including inline file data where supported.
    Supported inline MIME types: image/*, application/pdf, text/*, audio/*, video/*
    """
    parts = []

    for f in files:
        file_bytes = f.read()
        mime_type  = f.type or (mimetypes.guess_type(f.name)[0] or "application/octet-stream")
        b64_data   = base64.standard_b64encode(file_bytes).decode("utf-8")

        # Gemini inline_data supports images, pdf, audio, video, plain text
        inline_mime_prefixes = ("image/", "application/pdf", "text/", "audio/", "video/")
        if any(mime_type.startswith(p) for p in inline_mime_prefixes):
            parts.append({"inline_data": {"mime_type": mime_type, "data": b64_data}})
        else:
            # For unsupported types, attach as plain text description
            try:
                text_content = file_bytes.decode("utf-8", errors="replace")
                parts.append({"text": f"[Attached file: {f.name}]\n{text_content}"})
            except Exception:
                parts.append({"text": f"[Attached file: {f.name} — binary content, {len(file_bytes)} bytes]"})

    # Add the user's text prompt last
    parts.append({"text": prompt_text})
    return parts


# ─────────────────────────────────────────────────────────────────────────────
# HELPER: Render guard badge
# ─────────────────────────────────────────────────────────────────────────────
def render_guard_result(guard_result: dict, label: str):
    action   = guard_result.get("action", "ALLOW").upper()
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


# ─────────────────────────────────────────────────────────────────────────────
# MAIN CHAT UI
# ─────────────────────────────────────────────────────────────────────────────
st.title("🔒 Private AI Chat")
st.caption(
    "Your conversations are protected by **Zscaler AI Guard** — "
    "every prompt and response is inspected before delivery."
)

# ── Render chat history ───────────────────────────────────────────────────────
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        # Show any attached file names
        if msg.get("files"):
            st.caption("📎 " + " · ".join(msg["files"]))

        # Guard result banners (stored per message)
        if msg.get("guard_prompt"):
            render_guard_result(msg["guard_prompt"], "Prompt")
        if msg.get("guard_response"):
            render_guard_result(msg["guard_response"], "Response")

        st.markdown(msg["content"])

        if msg["role"] == "assistant" and msg.get("guard_response", {}).get("action") == "ALLOW":
            st.markdown('<span class="allow-badge">✅ Cleared by AI Guard</span>', unsafe_allow_html=True)


# ── Chat input ────────────────────────────────────────────────────────────────
user_input = st.chat_input("Type your message here…")

if user_input:

    # ── Validate API keys ─────────────────────────────────────────────────────
    if not gemini_key:
        st.error("⚠️ Please enter your **Google Gemini API Key** in the sidebar.")
        st.stop()

    # ── Collect attached files ────────────────────────────────────────────────
    attached_names = [f.name for f in uploaded_files] if uploaded_files else []

    # ── Display user message ──────────────────────────────────────────────────
    with st.chat_message("user"):
        if attached_names:
            st.caption("📎 " + " · ".join(attached_names))
        st.markdown(user_input)

    # ── STEP 1: Inspect PROMPT with AI Guard (direction: outbound) ────────────
    with st.spinner("🛡️ Zscaler AI Guard inspecting your prompt…"):
        guard_prompt_result = inspect_with_ai_guard(
            content=user_input,
            direction="outbound",
            api_key=zscaler_key,
            email=user_email,
        )

    prompt_action = guard_prompt_result.get("action", "ALLOW").upper()

    # ── STEP 2: Decide whether to proceed to LLM ─────────────────────────────
    should_call_llm = False
    if prompt_action == "ALLOW":
        should_call_llm = True
    elif prompt_action == "CAUTION":
        should_call_llm = (caution_action == "Allow with warning")
    elif prompt_action == "BLOCK":
        should_call_llm = False

    llm_response_text = None
    guard_response_result = {"action": "ALLOW", "triggeringDetectors": [], "message": "Not called"}

    if should_call_llm:
        # ── STEP 3: Call Google Gemini 2.5 Flash ─────────────────────────────
        try:
            genai.configure(api_key=gemini_key)
            model = genai.GenerativeModel(GEMINI_MODEL)

            # Build conversation history for Gemini
            gemini_history = []
            for m in st.session_state.messages:
                role = "user" if m["role"] == "user" else "model"
                gemini_history.append({"role": role, "parts": [{"text": m["content"]}]})

            # Build current turn parts (text + any attached files)
            current_parts = build_gemini_parts(user_input, uploaded_files or [])

            # Start chat with history and send current message
            chat = model.start_chat(history=gemini_history)

            with st.spinner("🤖 Gemini is thinking…"):
                response = chat.send_message(current_parts)
                llm_response_text = response.text

        except Exception as e:
            st.error(f"❌ Gemini API error: {e}")
            llm_response_text = None

        # ── STEP 4: Inspect RESPONSE with AI Guard (direction: inbound) ───────
        if llm_response_text:
            with st.spinner("🛡️ Zscaler AI Guard inspecting the response…"):
                guard_response_result = inspect_with_ai_guard(
                    content=llm_response_text,
                    direction="inbound",
                    api_key=zscaler_key,
                    email=user_email,
                )

    # ── STEP 5: Determine final response to show ──────────────────────────────
    response_action = guard_response_result.get("action", "ALLOW").upper()

    if not should_call_llm:
        # Prompt was blocked or cautioned+blocked
        detectors = guard_prompt_result.get("triggeringDetectors", [])
        det_str   = ", ".join(detectors) if detectors else guard_prompt_result.get("message", "Policy violation")
        display_content = f"🚫 Your message was **blocked** before reaching the AI.\n\n**Reason:** {det_str}"
        if prompt_action == "CAUTION" and caution_action == "Block":
            display_content = f"⚠️ Your message was **stopped** due to a caution flag.\n\n**Detected:** {det_str}"
        final_role = "assistant"

    elif llm_response_text is None:
        display_content = "❌ Could not get a response from Gemini. Please check your API key."
        final_role = "assistant"

    elif response_action == "BLOCK":
        detectors = guard_response_result.get("triggeringDetectors", [])
        det_str   = ", ".join(detectors) if detectors else guard_response_result.get("message", "Policy violation")
        display_content = f"🚫 The AI's response was **blocked** by Zscaler AI Guard.\n\n**Reason:** {det_str}"
        final_role = "assistant"

    elif response_action == "CAUTION" and caution_action == "Block":
        detectors = guard_response_result.get("triggeringDetectors", [])
        det_str   = ", ".join(detectors) if detectors else guard_response_result.get("message", "Flagged content")
        display_content = f"⚠️ The AI's response was **held** due to a caution flag.\n\n**Detected:** {det_str}"
        final_role = "assistant"

    else:
        # ALLOW or CAUTION+allow-with-warning
        display_content = llm_response_text
        final_role = "assistant"

    # ── STEP 6: Render assistant message ──────────────────────────────────────
    with st.chat_message("assistant"):
        if should_call_llm and prompt_action == "CAUTION":
            render_guard_result(guard_prompt_result, "Prompt")

        if response_action in ("BLOCK", "CAUTION") and should_call_llm:
            render_guard_result(guard_response_result, "Response")

        if not should_call_llm and prompt_action in ("BLOCK", "CAUTION"):
            render_guard_result(guard_prompt_result, "Prompt")

        st.markdown(display_content)

        if final_role == "assistant" and response_action == "ALLOW" and llm_response_text:
            st.markdown('<span class="allow-badge">✅ Cleared by AI Guard</span>', unsafe_allow_html=True)

    # ── STEP 7: Persist to session state ──────────────────────────────────────
    st.session_state.messages.append({
        "role":           "user",
        "content":        user_input,
        "files":          attached_names,
        "guard_prompt":   guard_prompt_result,
        "guard_response": None,
    })
    st.session_state.messages.append({
        "role":           "assistant",
        "content":        display_content,
        "files":          [],
        "guard_prompt":   None,
        "guard_response": guard_response_result if should_call_llm else None,
    })
```---

## How to run

```bash
pip install streamlit google-generativeai requests python-dotenv
streamlit run app.py
