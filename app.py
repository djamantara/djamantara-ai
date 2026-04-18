import streamlit as st
import time
import edge_tts
import asyncio
import base64
import os
import sqlite3
import threading
from groq import Groq

# --- KONFIGURASI API ---
# 💡 Gunakan st.secrets atau .env di production
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "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")

# --- SETTING LAYAR MOBILE RESPONSIF ---
st.set_page_config(
    page_title="Djamantara AI", 
    page_icon="🐱", 
    layout="centered",
    initial_sidebar_state="collapsed"
)

# --- CSS INJECTION ---
st.markdown("""
    <style>
    .main .block-container {
        padding-top: 2rem;
        padding-bottom: 5rem;
        padding-left: 1rem;
        padding-right: 1rem;
    }
    .cat-container img {
        max-width: 100px;
        height: auto;
    }
    .moto-text {
        font-size: 0.9rem !important;
        line-height: 1.4;
    }
    .stChatInputContainer {
        padding-bottom: 20px;
    }
    footer {visibility: hidden;}
    #MainMenu {visibility: hidden;}
    @media only screen and (max-width: 600px) {
        h1 { font-size: 1.8rem !important; }
        .moto-text { font-size: 0.8rem !important; }
    }
    </style>
    """, unsafe_allow_html=True)
# Setup Klien API
try:
    client = Groq(api_key=GROQ_API_KEY)
except Exception as e:
    st.error(f"⚠️ Waduh Bos, Groq-nya bermasalah: {e}")
    st.stop()

# ==========================================
# --- 1. SISTEM INGATAN (DATABASE) ---
# ==========================================
def init_db():
    conn = sqlite3.connect('djamantara_memory.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS chat_history 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, role TEXT, content TEXT, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')
    conn.commit()
    conn.close()

def save_chat(role, content):
    conn = sqlite3.connect('djamantara_memory.db')
    try:
        c = conn.cursor()
        c.execute("INSERT INTO chat_history (role, content) VALUES (?, ?)", (role, str(content)))
        conn.commit()
    finally:
        conn.close()

def load_chat(limit=50):
    conn = sqlite3.connect('djamantara_memory.db')
    try:
        c = conn.cursor()
        c.execute("SELECT role, content FROM chat_history ORDER BY timestamp ASC LIMIT ?", (limit,))
        history = c.fetchall()
        return [{"role": r, "content": c} for r, c in history]
    finally:
        conn.close()

init_db()

# ==========================================
# --- 2. FUNGSI PENDUKUNG (MEDIA) ---
# ==========================================
def get_local_gif(file_path):
    if os.path.exists(file_path):
        with open(file_path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")
    return None

def encode_image(file_obj):    file_obj.seek(0)
    mime_type = file_obj.type or "image/jpeg"
    return base64.b64encode(file_obj.read()).decode('utf-8'), mime_type

def run_async_safe(coro_func, *args):
    def _run():
        new_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(new_loop)
        try:
            new_loop.run_until_complete(coro_func(*args))
        finally:
            new_loop.close()
    threading.Thread(target=_run, daemon=True).start()

async def generate_voice(text):
    clean_text = text.replace("*", "").replace("#", "").replace("`", "").replace("-", " ")
    communicate = edge_tts.Communicate(clean_text, "id-ID-ArdiNeural", pitch="-5Hz", rate="+10%")
    await communicate.save("temp_voice.mp3")

def autoplay_audio(file_path):
    if os.path.exists(file_path):
        with open(file_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
            st.markdown(f'<audio autoplay playsinline controls style="display:none;"><source src="data:audio/mp3;base64,{b64}" type="audio/mp3"></audio>', unsafe_allow_html=True)

# ==========================================
# --- 3. TAMPILAN UTAMA ---
# ==========================================
gif_data = get_local_gif("kucing.gif")

if gif_data:
    st.markdown(
        f"""
        <div style="text-align: center; margin-top: -30px;" class="cat-container">
            <img src="data:image/gif;base64,{gif_data}" style="z-index: 1;">
            <h1 style="margin: 0; padding: 0;">🤖 Djamantara AI</h1>
            <p class="moto-text" style="color: gray; font-style: italic;">
                "Entar kon obâ'. É tengnga jhâlân pas mu-nemmu. Oréng od i' jhâ' alako jhubâ'. Lebbi bhagus nyaré élmo."
            </p>
        </div>
        """, 
        unsafe_allow_html=True
    )

with st.sidebar:
    st.title("👁️ Mata Kocheng")
    uploaded_file = st.file_uploader("Kirim foto...", type=["jpg", "jpeg", "png"])
    
    if uploaded_file:
        st.session_state.current_image = uploaded_file        st.image(uploaded_file, caption="Foto Siap!", use_container_width=True)
    elif "current_image" in st.session_state:
        st.image(st.session_state.current_image, caption="Foto Siap!", use_container_width=True)
    
    st.divider()
    if st.button("🗑️ Hapus Ingatan"):
        conn = sqlite3.connect('djamantara_memory.db')
        conn.cursor().execute("DELETE FROM chat_history")
        conn.commit()
        conn.close()
        st.session_state.messages = []
        st.session_state.pop("current_image", None)
        st.rerun()

if "messages" not in st.session_state:
    st.session_state.messages = load_chat()

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# ==========================================
# --- 4. LOGIKA PERCAKAPAN ---
# ==========================================
if prompt := st.chat_input("Ngobrol moso Djamantara, Bos..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    save_chat("user", prompt)
    
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Si Kocheng lagi ngintip..."):
            try:
                image_obj = st.session_state.get("current_image")
                
                if image_obj:
                    base64_image, mime_type = encode_image(image_obj)
                    response = client.chat.completions.create(
                        messages=[
                            {
                                "role": "user",
                                "content": [
                                    {"type": "text", "text": f"Nama kamu Djamantara. Jawab santai, kocak, bahasa Indonesia campur Madura sedikit. Panggil 'Bos'. Analisa ini: {prompt}"},
                                    {"type": "image_url", "image_url": {"url": f"{mime_type};base64,{base64_image}"}},
                                ],
                            }
                        ],
                        model="llama-3.2-90b-vision-preview",
                        temperature=0.7                    )
                    full_response = response.choices[0].message.content
                else:
                    context = st.session_state.messages[-5:]
                    system_msg = {"role": "system", "content": "Nama kamu Djamantara, asisten kucing hitam keren & kocak. Panggil user 'Bos'. Gunakan bahasa santai Indonesia-Madura. Jangan terlalu panjang."}
                    
                    response = client.chat.completions.create(
                        messages=[system_msg] + context,
                        model="llama-3.3-70b-versatile",
                        temperature=0.7
                    )
                    full_response = response.choices[0].message.content
                
                # Efek mengetik
                placeholder = st.empty()
                displayed_text = ""
                for char in full_response:
                    displayed_text += char
                    placeholder.markdown(displayed_text + "▌")
                    time.sleep(0.005)
                placeholder.markdown(full_response)

                # Generate & putar suara di background
                if full_response.strip():
                    run_async_safe(generate_voice, full_response)
                    time.sleep(0.8)
                    autoplay_audio("temp_voice.mp3")
                    
                st.session_state.messages.append({"role": "assistant", "content": full_response})
                save_chat("assistant", full_response)
                
            except Exception as e:
                st.error(f"Duh Bos, sistem macet: {str(e)}")