import streamlit as st
import requests
import google.generativeai as genai

# 1. Page Configuration
st.set_page_config(page_title="Zscaler DAS/API Bot", page_icon="🛡️", layout="wide")
st.title("🛡️ Lokesh's AI Assistant (Zscaler DAS/API Mode)")

# Securely fetch API Keys from Streamlit secrets
try:
    zscaler_api_key = st.secrets["ZSCALER_API_KEY"]
    google_api_key  = st.secrets["GOOGLE_API_KEY"]
except KeyError as e:
    st.error(f"Missing secret: {e}. Please add it to your Streamlit secrets.")
    st.stop()

# Configure Google Gemini
genai.configure(api_key=google_api_key)


# 2. Sidebar
with st.sidebar:
    st.header("⚙️ Settings")
    model_name  = st.text_input("Google Model ID", "gemini-2.5-flash")
    temperature = st.slider("Creativity (Temperature)", 0.0, 1.0, 0.5)

    st.divider()
    if st.button("🗑️ Clear Chat History", use_container_width=True):
        st.session_state.messages = []
        st.rerun()

    st.info("Mode: DAS/API (Scan + Execute)")


# 3. Helper: Scan text with Zscaler AI Guard
def zscaler_scan(text: str, direction: str) -> dict:
    """
    Sends text to Zscaler AI Guard for policy scanning.
    direction: "outbound" (user prompt) or "inbound" (LLM response)
    Returns the full JSON response.
    """
    url     = "https://api.zseclipse.net/v1/detection/resolve-and-execute-policy"

    # --- CORRECTED: X-ApiKey header, no Bearer prefix ---
    headers = {
        "Content-Type": "application/json",
        "X-ApiKey":     zscaler_api_key
    }

    # --- CORRECTED: Simple direction + content body ---
    body = {
        "direction": direction,
        "content":   text
    }

    res = requests.post(url, headers=headers, json=body)
    res.raise_for_status()
    return res.json()


# 4. Initialize & Display Chat History
if "messages" not in st.session_state:
    st.session_state.messages = []

for message in st.session_state.messages:
    role = "assistant" if message.get("role") == "model" else "user"
    with st.chat_message(role):
        st.markdown(message["parts"][0]["text"])


# 5. Chat Input & Response Logic
if prompt := st.chat_input("Type your message here..."):

    st.session_state.messages.append({"role": "user", "parts": [{"text": prompt}]})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        zscaler_result = {}
        try:
            # ── STEP 1: Scan the outbound prompt ──────────────────────────────
            with st.spinner("🛡️ Zscaler: Scanning your prompt..."):
                zscaler_result = zscaler_scan(text=prompt, direction="outbound")

            action = zscaler_result.get("action", "allow").lower()
            if action == "block":
                st.error("🚫 Zscaler AI Guard blocked your prompt based on company policy.")
                st.json(zscaler_result)
                st.stop()

            # ── STEP 2: Call Gemini directly ──────────────────────────────────
            with st.spinner("🤖 Contacting Gemini..."):
                gemini_model    = genai.GenerativeModel(
                    model_name=model_name,
                    generation_config=genai.types.GenerationConfig(
                        temperature=temperature,
                        max_output_tokens=4096
                    )
                )
                gemini_response = gemini_model.generate_content(st.session_state.messages)
                llm_reply       = gemini_response.text

            # ── STEP 3: Scan the inbound LLM response ─────────────────────────
            with st.spinner("🛡️ Zscaler: Scanning AI response..."):
                zscaler_result = zscaler_scan(text=llm_reply, direction="inbound")

            action = zscaler_result.get("action", "allow").lower()
            if action == "block":
                st.error("🚫 Zscaler AI Guard blocked the AI response based on company policy.")
                st.json(zscaler_result)
                st.stop()

            
