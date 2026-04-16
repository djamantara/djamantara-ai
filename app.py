import streamlit as st
import time
import edge_tts
import asyncio
import base64
import os
import sqlite3
from groq import Groq
from PIL import Image
import io

# ==========================================
# --- KONFIGURASI API AMAN ---
# ==========================================
if "GROQ_API_KEY" in st.secrets:
    GROQ_API_KEY = st.secrets["GROQ_API_KEY"]
else:
    # Saran: Gunakan os.getenv agar lebih aman di lokal
    GROQ_API_KEY = os.getenv("GROQ_API_KEY", "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")
    if not GROQ_API_KEY:
        st.error("⚠️ API Key tidak ditemukan!")
        st.stop()

# --- SETTING LAYAR MOBILE RESPONSIF ---
st.set_page_config(
    page_title="Djamantara AI", 
    page_icon="🐱", 
    layout="centered",
    initial_sidebar_state="collapsed"
)

# ==========================================
# 🎨 CSS INJECTION - PREMIUM UI
# ==========================================
st.markdown("""
    <style>
    /* Sembunyikan elemen bawaan Streamlit agar terlihat seperti App */
    #MainMenu, footer, header, .stAppDeployButton, [data-testid="stToolbar"] {
        visibility: hidden !important; 
        display: none !important;
    }
    
    .main .block-container {
        padding-top: 1rem !important;
        padding-bottom: 1rem !important;
        max-width: 100% !important;
    }
    
    .cat-container img {
        max-width: 100px !important;
        border-radius: 50%;
        margin: 0 auto !important;
    }
    
    .moto-text {
        font-size: 0.85rem !important;
        color: #888;
        text-align: center;
        font-style: italic;
    }
    
    .image-preview-box {
        background: #121212;
        padding: 10px;
        border-radius: 15px;
        border: 1px solid #00d9ff;
        margin-bottom: 10px;
    }
    </style>
    """, unsafe_allow_html=True)

# Setup Groq Client
client = Groq(api_key=GROQ_API_KEY)

# ==========================================
# --- 1. SISTEM INGATAN (DATABASE) ---
# ==========================================
def init_db():
    conn = sqlite3.connect('djamantara_memory.db', check_same_thread=False)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS chat_history 
                 (role TEXT, content TEXT, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')
    conn.commit()
    conn.close()

def save_chat(role, content):
    try:
        conn = sqlite3.connect('djamantara_memory.db', check_same_thread=False)
        c = conn.cursor()
        c.execute("INSERT INTO chat_history (role, content) VALUES (?, ?)", (role, str(content)))
        conn.commit()
        conn.close()
    except: pass

def load_chat():
    try:
        conn = sqlite3.connect('djamantara_memory.db', check_same_thread=False)
        c = conn.cursor()
        c.execute("SELECT role, content FROM chat_history ORDER BY timestamp ASC")
        history = c.fetchall()
        conn.close()
        return [{"role": r, "content": c} for r, c in history]
    except: return []

def clear_chat_db():
    try:
        conn = sqlite3.connect('djamantara_memory.db', check_same_thread=False)
        conn.cursor().execute("DELETE FROM chat_history")
        conn.commit()
        conn.close()
        return True
    except: return False

init_db()

# ==========================================
# --- 2. FUNGSI PENDUKUNG (MEDIA) ---
# ==========================================
def get_local_gif(file_path):
    if os.path.exists(file_path):
        with open(file_path, "rb") as f:
            data = f.read()
            return base64.b64encode(data).decode()
    return None

def compress_image(uploaded_file):
    img = Image.open(uploaded_file)
    if img.mode != 'RGB':
        img = img.convert('RGB')
    
    # Resize jika terlalu besar
    max_size = 1024
    if max(img.size) > max_size:
        img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
    
    img_byte_arr = io.BytesIO()
    img.save(img_byte_arr, format='JPEG', quality=80)
    img_byte_arr.seek(0)
    return img_byte_arr

async def generate_voice(text):
    # Bersihkan teks dari simbol markdown agar suara lebih natural
    clean_text = text.replace("*", "").replace("#", "").replace("`", "")
    communicate = edge_tts.Communicate(clean_text, "id-ID-ArdiNeural", pitch="-5Hz", rate="+10%")
    await communicate.save("temp_voice.mp3")

# ==========================================
# --- 3. SESSION STATE ---
# ==========================================
if "messages" not in st.session_state:
    st.session_state.messages = load_chat()
if "compressed_image" not in st.session_state:
    st.session_state.compressed_image = None

# ==========================================
# --- 4. TAMPILAN ---
# ==========================================

# Header GIF
gif_base64 = get_local_gif("kucing.gif")
if gif_base64:
    st.markdown(
        f"""
        <div class="cat-container" style="text-align: center;">
            <img src="data:image/gif;base64,{gif_base64}">
            <h1 style='margin-bottom:0;'>🤖 Djamantara AI</h1>
            <p class="moto-text">"Entar kon obâ'. É tengnga jhâlân pas mu-nemmu. Lebbi bhagus nyaré élmo."</p>
        </div>
        """, unsafe_allow_html=True
    )
else:
    st.markdown("<h1 style='text-align: center;'>🤖 Djamantara AI</h1>", unsafe_allow_html=True)

# Toolbar Chat
col1, col2 = st.columns([3, 1])
with col1:
    uploaded_file = st.file_uploader("Upload Foto", type=["jpg", "png", "jpeg"], label_visibility="collapsed")
with col2:
    if st.button("🗑️ Reset", use_container_width=True):
        if clear_chat_db():
            st.session_state.messages = []
            st.session_state.compressed_image = None
            st.rerun()

# Logika Upload
if uploaded_file:
    st.session_state.compressed_image = compress_image(uploaded_file)
    st.image(st.session_state.compressed_image, caption="📸 Foto siap dianalisa", width=200)

# Tampilkan Chat
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# Input Chat
if prompt := st.chat_input("Ngobrol apa kita, Bos?"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    save_chat("user", prompt)
    
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Djamantara lagi mikir..."):
            try:
                if st.session_state.compressed_image:
                    # Logic Vision
                    b64_img = base64.b64encode(st.session_state.compressed_image.read()).decode()
                    response = client.chat.completions.create(
                        messages=[{
                            "role": "user",
                            "content": [
                                {"type": "text", "text": f"Kamu Djamantara. Jawab santai/kocak campur bahasa Madura. Analisa foto ini berdasarkan chat: {prompt}"},
                                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64_img}"}}
                            ]
                        }],
                        model="llama-3.2-11b-vision-preview", # Model vision yang stabil
                    )
                else:
                    # Logic Chat Biasa
                    response = client.chat.completions.create(
                        messages=[
                            {"role": "system", "content": "Nama kamu Djamantara, asisten kucing keren. Panggil 'Bos'. Gunakan bahasa Indonesia-Madura santai."},
                            *st.session_state.messages[-5:]
                        ],
                        model="llama-3.3-70b-versatile",
                    )
                
                full_res = response.choices[0].message.content
                st.markdown(full_res)
                
                # Audio TTS
                asyncio.run(generate_voice(full_res))
                if os.path.exists("temp_voice.mp3"):
                    st.audio("temp_voice.mp3")
                
                st.session_state.messages.append({"role": "assistant", "content": full_res})
                save_chat("assistant", full_res)

            except Exception as e:
                st.error(f"Waduh Bos, sistem error: {e}")
