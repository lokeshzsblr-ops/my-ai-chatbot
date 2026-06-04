import streamlit as st
from PIL import Image
import json
import requests # Use the requests library to make HTTP calls

# 1. Page Configuration
st.set_page_config(page_title="Zscaler AI Guard Bot", page_icon="🛡️", layout="wide")
st.title("🛡️ Lokesh's AI Assistant (via Zscaler AI Guard)")

# --- IMPORTANT ---
# Securely fetch Zscaler API Key from Streamlit Secrets.
# Make sure to set "ZSCALER_API_KEY" in your Streamlit secrets.
try:
    api_key = st.secrets["ZSCALER_API_KEY"]
except KeyError:
    st.error("ZSCALER_API_KEY not found in Streamlit secrets. Please add it to run the app.")
    st.stop()


# 2. Sidebar: Settings, File Upload, and History Export
with st.sidebar:
    st.header("⚙️ Settings")
    
    # Model name input, as it's part of the request body
    model_name = st.text_input("Model Name", "gpt-3.5-turbo")
    
    st.divider()

    st.header("📂 Upload Center")
    uploaded_file = st.file_uploader(
        "Upload an image or PDF", 
        type=["jpg", "jpeg", "png", "pdf"]
    )
    
    if uploaded_file:
        st.success("File ready!")
        # NOTE: The logic to SEND the file to the API is commented out below,
        # as the Zscaler documentation provided does not specify how to handle files.
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
            try:
                # --- Zscaler AI Guard API Call ---
                
                # 1. Define the API endpoint and headers
                zag_url = "https://api.us1.zseclipse.net/v1/chat/completions"
                headers = {
                    'Content-Type': 'application/json',
                    'X-ApiKey': f'Bearer {api_key}'
                }

                # 2. Construct the request body
                # The 'messages' format follows the provided documentation
                messages_payload = [{"role": "user", "content": prompt}]

                # --- IMPORTANT: FILE HANDLING ---
                # The documentation does not explain how to send files. 
                # If you find out how, you will need to modify the 'messages_payload'
                # to include the file data in the format Zscaler expects.
                # The code below is commented out as it will not work without
                # the correct API specification.
                #
                # if uploaded_file:
                #     if uploaded_file.type.startswith("image"):
                #         # Example: You might need to base64 encode the image
                #         # and add it to the payload. This is just a guess.
                #         st.warning("Image upload is not yet supported with this API configuration.")
                #     elif uploaded_file.type == "application/pdf":
                #         st.warning("PDF upload is not yet supported with this API configuration.")
                
                body = {
                    "model": model_name,
                    "messages": messages_payload
                }

                # 3. Make the POST request
                response = requests.post(zag_url, headers=headers, json=body)
                response.raise_for_status() # Raises an error for bad responses (4xx or 5xx)

                # 4. Parse the response
                response_json = response.json()
                
                # Assuming a standard OpenAI-like response structure.
                # You may need to change these keys based on the actual Zscaler response.
                assistant_response = response_json['choices'][0]['message']['content']
                
                st.markdown(assistant_response)
                st.session_state.messages.append({"role": "assistant", "content": assistant_response})

            except requests.exceptions.RequestException as e:
                st.error(f"HTTP Request failed: {e}")
            except (KeyError, IndexError) as e:
                st.error("Failed to parse the response from the AI. The response format might have changed.")
                st.json(response.json()) # Display the raw response for debugging
            except Exception as e:
                st.error(f"An unexpected error occurred: {e}")

