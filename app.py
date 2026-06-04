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
    # This creativity slider will now control the 'temperature' parameter
    temperature = st.slider("Creativity (Temperature)", 0.0, 1.0, 0.5)
    
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
    # Use 'author' internally for consistency with the new API format
    avatar = "🤖" if message["author"] == "model" else "👤"
    with st.chat_message(message["author"], avatar=avatar):
        st.markdown(message["content"])

# 5. Chat Input & Response Logic
if prompt := st.chat_input("Type your message here..."):
    # Use 'author' and 'model' to align with Google's format
    st.session_state.messages.append({"author": "user", "content": prompt})
    with st.chat_message("user", avatar="👤"):
        st.markdown(prompt)

    with st.chat_message("model", avatar="🤖"):
        with st.spinner("Thinking..."):
            response_text = ""
            try:
                # --- Zscaler AI Guard API Call ---
                
                # The model name is now part of the URL, not the body
                model_id = "gemini-2.5-flash"
                # IMPORTANT: This URL format is a guess based on Google's standards.
                # Your Zscaler admin may need to provide the exact URL template.
                # This assumes a project and location are not needed in the URL for Zscaler.
                zag_url = f"https://proxy.us1.zseclipse.net/v1/chat/completions" # Keeping this for now as per docs
                
                headers = {
                    'Content-Type': 'application/json',
                    'X-ApiKey': f'Bearer {api_key}'
                }

                # --- CORRECTED REQUEST BODY ---
                # This now uses the native Google Gemini (Vertex AI) format.
                body = {
                  "instances": [
                    {
                      # We send the entire chat history for context
                      "messages": st.session_state.messages 
                    }
                  ],
                  "parameters": {
                    "temperature": temperature,
                    "maxOutputTokens": 2048,
                    "topK": 40
                  }
                }
                
                # Zscaler's API might still need the model in the body, even if it's not standard
                # for Google. Let's add it back just in case, as per their documentation example.
                body['model'] = model_id
                
                response = requests.post(zag_url, headers=headers, json=body)
                response_text = response.text
                response.raise_for_status()

                response_json = response.json()
                
                # Adjust parsing for the Google/Vertex AI response structure
                assistant_response = response_json['predictions'][0]['candidates'][0]['content']
                
                st.markdown(assistant_response)
                # Save the response using the 'author' format
                st.session_state.messages.append({"author": "model", "content": assistant_response})

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
                st.json(response_json) # Display what was actually received
            except Exception as e:
                st.error(f"An unexpected error occurred: {e}")

