import streamlit as st
import google.generativeai as genai

st.markdown("""
    <style>
    /* Add a subtle shadow to the chat input box */
    .stChatInputContainer {
        border-radius: 20px;
        box-shadow: 0px 4px 10px rgba(0,0,0,0.1);
    }
    /* Change the background of user messages specifically */
    [data-testid="stChatMessage"]:nth-child(even) {
        background-color: rgba(0, 122, 255, 0.05);
        border-radius: 15px;
    }
    </style>
    """, unsafe_allow_html=True)

# 1. Page Config
st.set_page_config(page_title="Lokesh AI Chatbot", page_icon="🤖")
st.title("🤖 Lokesh's AI Chatbot")

with st.sidebar:
    st.header("⚙️ Settings")
    
    # Let users choose the 'creativity' of the bot
    temp = st.slider("Creativity (Temperature)", 0.0, 1.0, 0.7)
    
    # Add a Reset Button
    if st.button("🗑️ Clear Chat History"):
        st.session_state.messages = []
        st.rerun()
    
    st.divider()
    st.info("This bot is powered by Gemini 2.5 Flash.")

# 2. Get API Key from Streamlit Secrets
# (We will set this up in Step 3)
api_key = st.secrets["GOOGLE_API_KEY"]
genai.configure(api_key=api_key)
model = genai.GenerativeModel('gemini-2.5-flash')

# 3. Initialize Chat History
if "messages" not in st.session_state:
    st.session_state.messages = []

# 4. Display chat messages from history on app rerun
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# 5. Chat Input
if prompt := st.chat_input("What is on your mind?"):
    # Add user message to history
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Generate AI response
    with st.chat_message("assistant"):
        response = model.generate_content(prompt)
        st.markdown(response.text)
    
    # Add assistant response to history
    st.session_state.messages.append({"role": "assistant", "content": response.text})
