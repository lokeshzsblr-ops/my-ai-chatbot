import streamlit as st
import json
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

# Configure the Google Gemini client
genai.configure(api_key=google_api_key)


# 2. Sidebar for settings
with st.sidebar:
    st.header("⚙️ Settings")
    model_name   = st.text_input("Google Model ID", "gemini-2.5-flash")
    temperature  = st.slider("Creativity (Temperature)", 0.0, 1.0, 0.5)

    st.divider()
    if st.button("🗑️ Clear Chat History", use_container_width=True):
        st.session_state.messages = []
        st.rerun()

    st.info("Mode: DAS/API (Resolve & Execute)")


# 3. Helper: Call Zscaler policy evaluation endpoint
def evaluate_with_zscaler(text: str, direction: str) -> dict:
    """
    Sends text to Zscaler AI Guard for policy evaluation.
    direction: "outbound" (user prompt) or "inbound" (LLM response)
    Returns the full JSON response from Zscaler.
    """
    url     = "https://api.zseclipse.net/v1/detection/resolve-and-execute-policy"
    headers = {
        "Content-Type":  "application/json",
        "Authorization": f"Bearer {zscaler_api_key}"
    }
    body = {
        "direction": direction,
        "content":   text
    }
    response = requests.post(url, headers=headers, json=body)
    response.raise_for_status()
    return response.json()


# 4. Initialize & Display Chat History
if "messages" not in st.session_state:
    st.session_state.messages = []

for message in st.session_state.messages:
    role = "assistant" if message.get("role") == "model" else "user"
    with st.chat_message(role):
        st.markdown(message["parts"][0]["text"])


# 5. Chat Input & Response Logic
if prompt := st.chat_input("Type your message here..."):

    # Display user message immediately
    st.session_state.messages.append({"role": "user", "parts": [{"text": prompt}]})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        response_text = ""
        try:
            # ── STEP 1: Evaluate the outbound prompt with Zscaler ──────────────
            with st.spinner("🛡️ Zscaler: Evaluating your prompt..."):
                zs_outbound = evaluate_with_zscaler(prompt, "outbound")

            # Check if Zscaler blocked the prompt
            action = zs_outbound.get("action", "").lower()
            if action == "block":
                st.error("🚫 Zscaler AI Guard blocked this prompt based on your company's policy.")
                st.json(zs_outbound)
                st.stop()

            # ── STEP 2: Call Google Gemini directly ────────────────────────────
            with st.spinner("🤖 Contacting Gemini..."):
                gemini_model = genai.GenerativeModel(
                    model_name=model_name,
                    generation_config=genai.types.GenerationConfig(
                        temperature=temperature,
                        max_output_tokens=4096
                    )
                )
                gemini_response = gemini_model.generate_content(
                    st.session_state.messages
                )
                llm_reply = gemini_response.text

            # ── STEP 3: Evaluate the inbound LLM response with Zscaler ─────────
            with st.spinner("🛡️ Zscaler: Evaluating AI response..."):
                zs_inbound = evaluate_with_zscaler(llm_reply, "inbound")

            # Check if Zscaler blocked the response
            action = zs_inbound.get("action", "").lower()
            if action == "block":
                st.error("🚫 Zscaler AI Guard blocked the AI's response based on your company's policy.")
                st.json(zs_inbound)
                st.stop()

            # ── STEP 4: Display and store the response ─────────────────────────
            st.markdown(llm_reply)
            st.session_state.messages.append({"role": "model", "parts": [{"text": llm_reply}]})

        except requests.exceptions.HTTPError as e:
            st.error(f"Zscaler API Error: {e}")
            st.code(e.response.text if e.response else "No response body.")
        except Exception as e:
            st.error(f"An unexpected error occurred: {e}")
            st.code(response_text)
