import streamlit as st
import json
import requests

# 1. Page Configuration
st.set_page_config(page_title="Zscaler DAS/API Bot", page_icon="🛡️", layout="wide")
st.title("🛡️ Lokesh's AI Assistant (Zscaler DAS/API Mode)")

# Securely fetch API Keys from Streamlit secrets
try:
    zscaler_api_key = st.secrets["ZSCALER_API_KEY"]   # AI Guard Token
    zscaler_app_id  = st.secrets["ZSCALER_APP_ID"]    # Application ID
except KeyError as e:
    st.error(f"Missing secret: {e}. Please add it to your Streamlit secrets.")
    st.stop()


# 2. Sidebar for settings
with st.sidebar:
    st.header("⚙️ Settings")
    model_name  = st.text_input("Google Model ID", "gemini-2.5-flash")
    temperature = st.slider("Creativity (Temperature)", 0.0, 1.0, 0.5)

    st.divider()
    if st.button("🗑️ Clear Chat History", use_container_width=True):
        st.session_state.messages = []
        st.rerun()

    st.info("Mode: DAS/API (Resolve & Execute)")


# 3. Initialize & Display Chat History
if "messages" not in st.session_state:
    st.session_state.messages = []

for message in st.session_state.messages:
    role = "assistant" if message.get("role") == "model" else "user"
    with st.chat_message(role):
        st.markdown(message["parts"][0]["text"])


# 4. Chat Input & Response Logic
if prompt := st.chat_input("Type your message here..."):

    # Display user message immediately
    st.session_state.messages.append({"role": "user", "parts": [{"text": prompt}]})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        try:
            with st.spinner("🛡️ Sending request through Zscaler AI Guard..."):

                # --- Step 1: Define the correct endpoint and headers ---
                zscaler_endpoint_url = "https://api.zseclipse.net/v1/detection/resolve-and-execute-policy"

                # TWO credentials are required:
                # Authorization header → your AI Guard Bearer Token
                # X-ApiKey header      → your Application ID
                headers = {
                    "Content-Type":  "application/json",
                    "Authorization": f"Bearer {zscaler_api_key}",
                    "X-ApiKey":      zscaler_app_id
                }

                # --- Step 2: Build the request body exactly as the documentation specifies ---
                # provider and model are required top-level fields.
                # contents uses the native Gemini format with the full chat history.
                request_body = {
                    "provider": "google",
                    "model":    model_name,
                    "contents": st.session_state.messages
                }

                # --- Step 3: Send the request to Zscaler ---
                response = requests.post(
                    zscaler_endpoint_url,
                    headers=headers,
                    json=request_body
                )
                response_text = response.text
                response.raise_for_status()
                zscaler_response = response.json()

                # --- Step 4: Check if Zscaler blocked the request ---
                action = zscaler_response.get("action", "").lower()
                if action == "block":
                    st.error("🚫 Zscaler AI Guard blocked this request based on your company's policy.")
                    st.json(zscaler_response)
                    st.stop()

                # --- Step 5: Extract the Gemini response from Zscaler's reply ---
                # Zscaler calls Google on our behalf and returns the response directly.
                assistant_response = zscaler_response['candidates'][0]['content']['parts'][0]['text']

                st.markdown(assistant_response)
                st.session_state.messages.append({"role": "model", "parts": [{"text": assistant_response}]})

        except requests.exceptions.HTTPError as e:
            st.error(f"Zscaler API Error: {e}")
            st.code(e.response.text if e.response else "No response body.")
        except (KeyError, IndexError) as e:
            st.error("Failed to parse the response. The structure was unexpected.")
            st.write(f"Error on key: `{e}`")
            st.write("Full response received:")
            st.json(zscaler_response)
        except Exception as e:
            st.error(f"An unexpected error occurred: {e}")
