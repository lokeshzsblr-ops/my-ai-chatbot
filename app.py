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
    temperature = st.slider("Creativity (Temperature)", 0.0, 1.0, 0.5)
    
    st.divider()
    st.header("📂 Upload Center")
    # File uploader (functionality for sending file is still pending Zscaler docs)
    uploaded_file = st.file_uploader("Upload an image or PDF", type=["jpg", "jpeg", "png", "pdf"])
    if uploaded_file:
        st.success("File ready!")
        if uploaded_file.type.startswith("image"):
            st.image(Image.open(uploaded_file), caption="Preview", use_container_width=True)

    st.divider()
    st.header("💾 Export History")
    # Export and Clear buttons
    if "messages" in st.session_state and st.session_state.messages:
        # Simplified export logic
        chat_text = "\n\n".join([f"{msg.get('author', msg.get('role', 'unknown')).upper()}: {msg['content']}" for msg in st.session_state.messages])
        st.download_button("Download Chat (.txt)", chat_text, "chatbot_history.txt", "text/plain", use_container_width=True)
    else:
        st.info("No history yet.")
    
    st.divider()
    if st.button("🗑️ Clear Chat History", use_container_width=True):
        st.session_state.messages = []
        st.rerun()
    
    st.info("Proxying via Zscaler AI Guard")


# 3. Initialize Chat History (if it doesn't exist)
if "messages" not in st.session_state:
    st.session_state.messages = []


# 4. Display Chat History (with Backward Compatibility)
# --- THIS IS THE CORRECTED SECTION ---
for message in st.session_state.messages:
    # Determine the role for display purposes, handling both old ('role') and
    # new ('author') message formats to prevent errors with old history.
    if "author" in message:
        # New format: author is 'user' or 'model'
        display_role = "assistant" if message["author"] == "model" else "user"
    else:
        # Old format: role is 'user' or 'assistant'
        display_role = message.get("role", "user")

    avatar = "🤖" if display_role == "assistant" else "👤"
    with st.chat_message(display_role, avatar=avatar):
        st.markdown(message["content"])


# 5. Chat Input & Response Logic
if prompt := st.chat_input("Type your message here..."):
    # Append user message in the new 'author' format
    st.session_state.messages.append({"author": "user", "content": prompt})
    with st.chat_message("user", avatar="👤"):
        st.markdown(prompt)

    with st.chat_message("assistant", avatar="🤖"):
        with st.spinner("Thinking..."):
            response_text = ""
            try:
                model_id = "gemini-2.5-flash"
                zag_url = "https://proxy.us1.zseclipse.net/v1/chat/completions"
                
                headers = {
                    'Content-Type': 'application/json',
                    'X-ApiKey': f'Bearer {api_key}'
                }

                # Construct the body in the native Google Gemini format
                body = {
                  "model": model_id, # Zscaler docs imply model is still needed here
                  "instances": [
                    { "messages": st.session_state.messages }
                  ],
                  "parameters": {
                    "temperature": temperature,
                    "maxOutputTokens": 2048
                  }
                }
                
                response = requests.post(zag_url, headers=headers, json=body)
                response_text = response.text
                response.raise_for_status()

                response_json = response.json()
                
                # Parse the Google/Vertex AI response structure
                assistant_response = response_json['predictions'][0]['candidates'][0]['content']
                
                st.markdown(assistant_response)
                # Append assistant response in the new 'author' format
                st.session_state.messages.append({"author": "model", "content": assistant_response})

            # ... (rest of the error handling is the same) ...
            except json.JSONDecodeError:
                st.error("The server's response was not in the expected JSON format.")
                st.info(f"Status Code: {response.status_code}")
                st.code(response_text if response_text else "The response body was empty.")
            except requests.exceptions.HTTPError as e:
                st.error(f"An HTTP Error occurred: {e}")
                st.code(response_text if response_text else "The response body was empty.")
            except (KeyError, IndexError):
                st.error("Failed to parse the AI's response. The structure was unexpected.")
                st.write("Received JSON response:")
                st.json(response.json())
            except Exception as e:
                st.error(f"An unexpected error occurred: {e}")
