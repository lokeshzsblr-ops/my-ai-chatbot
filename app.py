import streamlit as st
import google.generativeai as genai
from PIL import Image
import json

# 1. Page Configuration
st.set_page_config(page_title="AI Search Bot", page_icon="🌐", layout="wide")
st.title("🌐 Lokesh's AI Assistant")

# API Key
api_key = st.secrets["GOOGLE_API_KEY"]
genai.configure(api_key=api_key)

# 2. Sidebar: Settings & Tools
with st.sidebar:
    st.header("⚙️ Settings")
    temp = st.slider("Creativity", 0.0, 1.0, 0.7)
    
    # NEW: Web Search Toggle
    use_web_search = st.toggle("Enable Web Search", value=False, help="Allow the AI to search Google for the latest info.")
    
    st.divider()
    st.header("📂 Upload Center")
    uploaded_file = st.file_uploader("Upload Image/PDF", type=["jpg", "jpeg", "png", "pdf"])
    
    if uploaded_file and uploaded_file.type.startswith("image"):
        st.image(Image.open(uploaded_file), use_container_width=True)

    st.divider()
    if st.button("🗑️ Clear Chat History", use_container_width=True):
        st.session_state.messages = []
        st.rerun()

# 3. Setup AI Model with Tools
# We only add the 'google_search_retrieval' tool if the toggle is ON
tools = ["google_search_retrieval"] if use_web_search else []

model = genai.GenerativeModel(
    model_name='gemini-2.5-flash',
    generation_config={"temperature": temp},
    tools=tools  # This enables the web search!
)

# 4. Initialize & Display Chat History
if "messages" not in st.session_state:
    st.session_state.messages = []

for message in st.session_state.messages:
    avatar = "🤖" if message["role"] == "assistant" else "👤"
    with st.chat_message(message["role"], avatar=avatar):
        st.markdown(message["content"])

# 5. Chat Input & Response
if prompt := st.chat_input("Ask me anything (e.g., 'What is the price of Bitcoin today?')"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user", avatar="👤"):
        st.markdown(prompt)

    with st.chat_message("assistant", avatar="🤖"):
        content_to_send = [prompt]
        if uploaded_file:
            if uploaded_file.type.startswith("image"):
                content_to_send.append(Image.open(uploaded_file))
            elif uploaded_file.type == "application/pdf":
                content_to_send.append({"mime_type": "application/pdf", "data": uploaded_file.getvalue()})

        # Generate Response (Note: Streaming is disabled when using tools for better stability)
        response = model.generate_content(content_to_send)
        
        # Display the text answer
        st.markdown(response.text)
        
        # NEW: Show Sources (Grounding Metadata)
        if use_web_search and response.candidates[0].grounding_metadata.search_entry_point:
            st.caption("Sources found via Google Search:")
            # This creates a small Google Search chip/link automatically
            st.html(response.candidates[0].grounding_metadata.search_entry_point.html_content)
    
    st.session_state.messages.append({"role": "assistant", "content": response.text})
