import streamlit as st
import json
import requests
import uuid # Still useful for potential logging/tracing

# 1. Page Configuration
st.set_page_config(page_title="Zscaler DAS/API Bot", page_icon="🛡️", layout="wide")
st.title("🛡️ Lokesh's AI Assistant (Zscaler DAS/API Mode)")

# Securely fetch Zscaler API Key from Streamlit secrets
try:
    api_key = st.secrets["ZSCALER_API_KEY"]
except KeyError:
    st.error("ZSCALER_API_KEY not found in Streamlit secrets. Please add it to run the app.")
    st.stop()


# 2. Sidebar for settings
with st.sidebar:
    st.header("⚙️ Settings")
    model_name = st.text_input("Google Model ID", "gemini-2.5-flash")
    st.caption("↑ This is the programmatic ID for the model.")
    
    temperature = st.slider("Creativity (Temperature)", 0.0, 1.0, 0.5)
    
    st.divider()
    if st.button("🗑️ Clear Chat History", use_container_width=True):
        st.session_state.messages = []
        st.rerun()
    
    st.info("Mode: DAS/API (Direct Native Request)")


# 3. Initialize & Display Chat History
if "messages" not in st.session_state:
    st.session_state.messages = []

for message in st.session_state.messages:
    role = "assistant" if message.get("role") == "model" else "user"
    with st.chat_message(role):
        st.markdown(message["parts"][0]["text"])


# 4. Chat Input & Response Logic
if prompt := st.chat_input("Type your message here..."):
    st.session_state.messages.append({"role": "user", "parts": [{"text": prompt}]})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Sending request through Zscaler AI Guard..."):
            response_text = ""
            try:
                # --- Step 1: Define the Correct Endpoint and Headers ---
                zscaler_endpoint_url = "https://api.us1.zseclipse.net/v1/detection/resolve-and-execute-policy"
                
                headers = {
                    'Content-Type': 'application/json',
                    'X-ApiKey': f'Bearer {api_key}'
                }

                # --- Step 2: Construct the Native Google Gemini Request Body ---
                # This is the ONLY body we will use now.
                native_google_body = {
                    "contents": st.session_state.messages,
                    "generationConfig": {
                        "temperature": temperature,
                        "maxOutputTokens": 4096
                    },
                    # We might need to tell Zscaler which model we intend to use
                    # since we are no longer using the "provider" field.
                    "model": model_name
                }
                
                # --- Step 3: Make the API Call Directly with the Native Body ---
                # We are NO LONGER using the complex "invocations" envelope.
                response = requests.post(zscaler_endpoint_url, headers=headers, json=native_google_body)
                response_text = response.text
                response.raise_for_status() # This will trigger on 4xx or 5xx errors
                
                # --- Step 4: Parse the Response as a Direct Native Response ---
                # If the request succeeds, the body should be the direct response from Google.
                google_response_json = response.json()
                
                assistant_response = google_response_json['candidates'][0]['content']['parts'][0]['text']
                
                st.markdown(assistant_response)
                st.session_state.messages.append({"role": "model", "parts": [{"text": assistant_response}]})

            except json.JSONDecodeError:
                st.error("A JSON decoding error occurred. The response may not be valid JSON.")
                st.info(f"Status Code: {response.status_code}")
                st.code(response_text if response_text else "The response body was empty.")
            except requests.exceptions.HTTPError as e:
                st.error(f"An HTTP Error occurred: {e}")
                st.write("This often means the request body is still not what the server expects.")
                st.code(response_text if response_text else "The response body was empty.")
            except (KeyError, IndexError) as e:
                st.error("Failed to parse the AI's response. The structure was unexpected.")
                st.write("Error occurred when accessing key:", str(e))
                st.write("Received JSON that caused the error:")
                st.json(response.json())
            except Exception as e:
                st.error(f"An unexpected error occurred: {e}")
                st.write("Raw response text during error:")
                st.code(response_text)
