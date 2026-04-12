import streamlit as st
import google.generativeai as genai
from PIL import Image

# 1. Page Configuration
st.set_page_config(page_title="Advanced AI Bot", page_icon="🚀", layout="wide")
st.title("🤖 Lokesh's AI Assistant")

# Securely fetch API Key from Streamlit Secrets
api_key = st.secrets["GOOGLE_API_KEY"]
genai.configure(api_key=api_key)

# 2. Sidebar: Settings & File Upload
with st.sidebar:
    st.header("⚙️ Settings")
    
    # Creativity slider (Temperature)
    temp = st.slider("Creativity (Temperature)", 0.0, 1.0, 0.7, help="Higher = more creative/random, Lower = more factual/focused.")
    
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

    # Reset Button
    if st.button("🗑️ Clear Chat History", use_container_width=True):
        st.session_state.messages = []
        st.rerun()
    
    st.info("Powered by Gemini 2.5 Flash")

# 3. Setup the AI Model with the chosen Creativity level
# We apply the 'temp' from the slider here
model = genai.GenerativeModel(
    model_name='gemini-2.5-flash',
    generation_config={"temperature": temp}
)

# 4. Initialize & Display Chat History
if "messages" not in st.session_state:
    st.session_state.messages = []

# Display previous messages with icons
for message in st.session_state.messages:
    avatar = "🤖" if message["role"] == "assistant" else "👤"
    with st.chat_message(message["role"], avatar=avatar):
        st.markdown(message["content"])

# 5. Chat Input & Response Logic
if prompt := st.chat_input("Type your message here..."):
    # Show user message
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user", avatar="👤"):
        st.markdown(prompt)

    # Generate AI response
    with st.chat_message("assistant", avatar="🤖"):
        # Build the multimodal request list
        content_to_send = [prompt]
        
        if uploaded_file:
            if uploaded_file.type.startswith("image"):
                img = Image.open(uploaded_file)
                content_to_send.append(img)
            elif uploaded_file.type == "application/pdf":
                pdf_data = {"mime_type": "application/pdf", "data": uploaded_file.getvalue()}
                content_to_send.append(pdf_data)

        # The 'temp' from your slider is used here automatically
        response = model.generate_content(content_to_send)
        st.markdown(response.text)
    
    # Save bot response to history
    st.session_state.messages.append({"role": "assistant", "content": response.text})
