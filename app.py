import streamlit as st
import google.generativeai as genai
from PIL import Image

# 1. Setup
st.set_page_config(page_title="Multimodal AI Bot", page_icon="🎨")
st.title("🤖 AI Chat with Vision")

# API Key from Secrets
api_key = st.secrets["GOOGLE_API_KEY"]
genai.configure(api_key=api_key)
model = genai.GenerativeModel('gemini-2.5-flash')

# 2. Sidebar with File Uploader
with st.sidebar:
    st.header("📂 Upload Center")
    uploaded_file = st.file_uploader(
        "Upload an image or PDF", 
        type=["jpg", "jpeg", "png", "pdf"]
    )
    
    if uploaded_file:
        st.success("File uploaded!")
        # Preview the image if it is one
        if uploaded_file.type.startswith("image"):
            img = Image.open(uploaded_file)
            st.image(img, caption="Preview", use_container_width=True)

    if st.button("🗑️ Clear Chat"):
        st.session_state.messages = []
        st.rerun()

# 3. Chat Logic
if "messages" not in st.session_state:
    st.session_state.messages = []

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# 4. Handling Input + Files
if prompt := st.chat_input("Ask about the file or just say hi!"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        # Create a list of parts to send to AI
        content_to_send = [prompt]
        
        # If a file is uploaded, add it to the message
        if uploaded_file:
            if uploaded_file.type.startswith("image"):
                img = Image.open(uploaded_file)
                content_to_send.append(img)
            elif uploaded_file.type == "application/pdf":
                # For PDF, we send the bytes directly
                pdf_data = {"mime_type": "application/pdf", "data": uploaded_file.getvalue()}
                content_to_send.append(pdf_data)

        # Generate Response
        response = model.generate_content(content_to_send)
        st.markdown(response.text)
    
    st.session_state.messages.append({"role": "assistant", "content": response.text})
