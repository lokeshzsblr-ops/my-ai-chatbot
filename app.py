import streamlit as st
import json
import requests
import uuid

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
    st.session_state.messages.append({"role": "user", "parts": [{"text": prompt}]})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Contacting Zscaler AI Guard..."):
            response_text = ""
            zscaler_response_json = {}
            try:
                # --- Step 1: Define Endpoints and Headers ---
                #
                # --- THIS IS THE CORRECTED URL ---
                # The server auto-prepends /v1/authenticate-llm-app to all requests.
                # The error response "path" field revealed the true base path.
                # So the full correct URL must include it explicitly.
                #
                zscaler_endpoint_url = "https://api.zseclipse.net/v1/authenticate-llm-app/v1/detection/resolve-and-execute-policy"
                google_api_path = f"/v1beta/models/{model_name}:generateContent"
                
                headers = {
                    'Content-Type': 'application/json',
                    'X-ApiKey': f'Bearer {api_key}'
                }

                # --- Step 2: Construct the Native Google Gemini Request Body ---
                native_google_body = {
                    "contents": st.session_state.messages,
                    "generationConfig": {
                        "temperature": temperature,
                        "maxOutputTokens": 4096
                    }
                }

                # --- Step 3: Construct the Zscaler AI Guard "Envelope" Body ---
                zscaler_envelope_body = {
                    "invocations": [
                        {
                            "id": str(uuid.uuid4()),
                            "protocol": "http",
                            "provider": "google",
                            "request": {
                                "uri": {
                                    "path": google_api_path
                                },
                                "headers": {
                                    "Content-Type": "application/json"
                                },
                                "body": native_google_body
                            }
                        }
                    ]
                }
                
                # --- Step 4: Make the API Call ---
                response = requests.post(zscaler_endpoint_url, headers=headers, json=zscaler_envelope_body)
                response_text = response.text
                response.raise_for_status()
                zscaler_response_json = response.json()

                # --- Step 5: Parse the Zscaler Response ---
                invocation_result = zscaler_response_json['invocations'][0]
                
                if invocation_result.get("status") != "forwarded":
                    error_details = invocation_result.get("error", "No error details provided.")
                    st.error(f"Zscaler AI Guard did not forward the request. Status: {invocation_result.get('status')}")
                    st.json(error_details)
                    st.stop()

                google_response_body = invocation_result["response"]["body"]
                
                # --- Step 6: Parse the Native Google Response ---
                assistant_response = google_response_body['candidates'][0]['content']['parts'][0]['text']
                
                st.markdown(assistant_response)
                st.session_state.messages.append({"role": "model", "parts": [{"text": assistant_response}]})

            except json.JSONDecodeError:
                st.error("A JSON decoding error occurred.")
                st.info(f"Status Code: {response.status_code}")
                st.code(response_text if response_text else "The response body was empty.")
            except requests.exceptions.HTTPError as e:
                st.error(f"An HTTP Error occurred: {e}")
                st.code(response_text if response_text else "The response body was empty.")
            except (KeyError, IndexError) as e:
                st.error("Failed to parse the AI's response. The data structure was unexpected.")
                st.write("Error occurred when accessing key:", str(e))
                st.write("Received Zscaler JSON that caused the error:")
                st.json(zscaler_response_json)
            except Exception as e:
                st.error(f"An unexpected error occurred: {e}")
                st.write("Raw response text during error:")
                st.code(response_text)
