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
    # --- CORRECTED LINE ---
    # Set the default model to the one you are using.
    model_name = st.text_input("Model Name", "gemini-2.5-flash")
    
    st.divider()

    st.header("📂 Upload Center")
    uploaded_file = st.file_uploader(
        "Upload an image or PDF", 
        type=["jpg", "jpeg", "png", "pdf"]
    )
    
    if uploaded_file:
        st.success("File ready!")
        if uploaded_file.type.startswith("image"):
            img = Image.open(uploaded_file)
            st.image(img, caption="Preview", use_container_width=True)

    st.divider()

    st.header("💾 Export History")
    if "messages" in st.session_state and st.session_state.messages:
        chat_text = ""
        for msg in st.session_state.messages:
            chat_text += f"{msg['role'].upper()}: {msg['content']}\n\n"
        
        st.download_button(
            label="Download Chat (.txt)",
            data=chat_text,
            file_name="chatbot_history.txt",
            mime="text/plain",
            use_container_width=True
        )
    else:
        st.info("No history yet.")
    
    st.divider()

    if st.button("🗑️ Clear Chat History", use_container_width=True):
        st.session_state.messages = []
        st.rerun()
    
    st.info("Proxying via Zscaler AI Guard")


# 4. Initialize & Display Chat History
if "messages" not in st.session_state:
    st.session_state.messages = []

for message in st.session_state.messages:
    avatar = "🤖" if message["role"] == "assistant" else "👤"
    with st.chat_message(message["role"], avatar=avatar):
        st.markdown(message["content"])

# 5. Chat Input & Response Logic
if prompt := st.chat_input("Type your message here..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user", avatar="👤"):
        st.markdown(prompt)

    with st.chat_message("assistant", avatar="🤖"):
        with st.spinner("Thinking..."):
            response_text = ""
            try:
                zag_url = "https://proxy.us1.zseclipse.net/v1/chat/completions"
                headers = {
                    'Content-Type': 'application/json',
                    'X-ApiKey': f'Bearer {api_key}'
                }

                messages_payload = [{"role": "user", "content": prompt}]
                
                body = {
                    "model": model_name,
                    "messages": messages_payload
                }

                response = requests.post(zag_url, headers=headers, json=body)
                response_text = response.text

                response.raise_for_status()

                response_json = response.json()
                
                assistant_response = response_json['choices'][0]['message']['content']
                
                st.markdown(assistant_response)
                st.session_state.messages.append({"role": "assistant", "content": assistant_response})

            except json.JSONDecodeError:
                st.error("The server's response was not in the expected JSON format.")
                st.info(f"Status Code: {response.status_code}")
                st.write("Here is the raw response from the server:")
                st.code(response_text if response_text else "The response body was empty.")
            # Other error handling...
            except requests.exceptions.HTTPError as e:
                st.error(f"An HTTP Error occurred: {e}")
                st.write("Here is the raw response from the server:")
                st.code(response_text if response_text else "The response body was empty.")
            except requests.exceptions.RequestException as e:
                st.error(f"A network connection error occurred: {e}")
            except (KeyError, IndexError):
                st.error("The JSON response from the server was in an unexpected format.")
                st.write("Here is the JSON response that caused the error:")
                st.json(response_text)
            except Exception as e:
                st.error(f"An unexpected error occurred: {e}")
