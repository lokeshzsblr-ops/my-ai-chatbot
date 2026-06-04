import streamlit as st
from PIL import Image
import json
import requests

# 1. Page Configuration
st.set_page_config(page_title="Zscaler AI Guard Bot", page_icon="🛡️", layout="wide")
st.title("🛡️ Lokesh's AI Assistant (via Zscaler AI Guard)")

# Securely fetch Zscaler API Key
try:
    api_key = st.secrets["ZSCALER_API_KEY"]
except KeyError:
    st.error("ZSCALER_API_KEY not found in Streamlit secrets. Please add it to run the app.")
    st.stop()


# 2. Sidebar
with st.sidebar:
    st.header("⚙️ Settings")
    # --- UPDATED LINE ---
    # Using the model ID you specified as the default.
    model_name = st.text_input("Model ID", "gemini-2.5-flash")
    
    st.caption("↑ IMPORTANT: This must be the exact ID from your Zscaler AI Guard policy.")
    temperature = st.slider("Creativity (Temperature)", 0.0, 1.0, 0.5)
    
    st.divider()
    if st.button("🗑️ Clear Chat History", use_container_width=True):
        st.session_state.messages = []
        st.rerun()
    
    st.info("Proxying via Zscaler AI Guard")


# 3. Initialize & Display Chat History
if "messages" not in st.session_state:
    st.session_state.messages = []

for message in st.session_state.messages:
    role = message.get("role")
    display_role = "assistant" if role == "model" else role
        
    with st.chat_message(display_role or "user"):
        if "parts" in message:
            st.markdown(message["parts"][0]["text"])
        else:
            st.markdown(message.get("content", ""))


# 4. Chat Input & Response Logic
if prompt := st.chat_input("Type your message here..."):
    st.session_state.messages.append({"role": "user", "parts": [{"text": prompt}]})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            response_text = ""
            try:
                zag_url = f"https://proxy.zseclipse.net/v1beta/models/{model_name}:generateContent"
                
                headers = {
                    'Content-Type': 'application/json',
                    'X-ApiKey': f'Bearer {api_key}'
                }

                # Convert chat history to the correct API format on-the-fly
                converted_history = []
                for msg in st.session_state.messages:
                    if "parts" in msg:
                        converted_history.append(msg)
                    else:
                        api_role = "model" if msg.get("role") == "assistant" else "user"
                        converted_history.append({"role": api_role, "parts": [{"text": msg.get("content", "")}]})

                # Construct the native Google Gemini request body
                body = {
                    "contents": converted_history,
                    "generationConfig": {
                        "temperature": temperature,
                        "maxOutputTokens": 2048
                    }
                }
                
                response = requests.post(zag_url, headers=headers, json=body)
                response_text = response.text
                response.raise_for_status()

                response_json = response.json()
                
                # Parse the native Gemini response
                assistant_response = response_json['candidates'][0]['content']['parts'][0]['text']
                
                st.markdown(assistant_response)
                st.session_state.messages.append({"role": "model", "parts": [{"text": assistant_response}]})

            except json.JSONDecodeError:
                st.error("The server's response was not in the expected JSON format.")
                st.info(f"Status Code: {response.status_code}")
                st.code(response_text if response_text else "The response body was empty.")
            except requests.exceptions.HTTPError as e:
                st.error(f"An HTTP Error occurred: {e}")
                st.code(response_text if response_text else "The response body was empty.")
            except (KeyError, IndexError):
                st.error("Failed to parse the AI's response. The structure was unexpected.")
                st.write("Received JSON response that caused the error:")
                st.json(response.json())
            except Exception as e:
                st.error(f"An unexpected error occurred: {e}")
                st.write("Raw response text during error:")
                st.code(response_text)
