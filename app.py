import streamlit as st
import google.generativeai as genai
from PIL import Image
import json

# 1. Page Configuration
st.set_page_config(page_title="Advanced AI Bot", page_icon="🚀", layout="wide")
st.title("🤖 Lokesh's AI Assistant")

# Securely fetch API Key from Streamlit Secrets
api_key = st.secrets["GOOGLE_API_KEY"]
genai.configure(api_key=api_key)

# 2. Sidebar: Settings, File Upload, and History Export
with st.sidebar:
    st.header("⚙️ Settings")
    
    # Creativity slider
    temp = st.slider("Creativity (Temperature)", 0.0, 1.0, 0.7)
    
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

    # --- History Export Section ---
    st.header("💾 Export History")
    if "messages" in st.session_state and st.session_state.messages:
        # Convert history to simple text
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

    # Reset Button
    if st.button("🗑️ Clear Chat History", use_container_width=True):
        st.session_state.messages = []
        st.rerun()
    
    st.info("Powered by Gemini 2.5 Flash")

# 3. Setup AI Model
model = genai.GenerativeModel(
    model_name='gemini-2.5-flash',
    generation_config={"temperature": temp}
)

# 4. Initialize & Display Chat History
if "messages" not in st.session_state
