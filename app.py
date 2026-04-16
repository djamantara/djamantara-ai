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
# --- KONFIGURASI API ---
# ==========================================
if "GROQ_API_KEY" in st.secrets:
    GROQ_API_KEY = st.secrets["GROQ_API_KEY"]
else:
    # Menggunakan key dari env atau default yang Bos kasih
    GROQ_API_KEY = os.getenv("GROQ_API_KEY", "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")
    if not GROQ_API_KEY:
        st.error("⚠️ API Key tidak ditemukan! Masukkan di Secrets Streamlit.")
        st.stop()

# --- SETTING HALAMAN ---
st.set_page_config(
    page_title="Djamantara AI", 
    page_icon="🐱", 
    layout="centered",
    initial_sidebar_state="collapsed"
)

# ==========================================
# 🎨 CSS CUSTOM - PREMIUM UI
# ==========================================
st.markdown("""
    <style>
    /* Sembunyikan Header & Footer Streamlit */
    #MainMenu, footer, header, .stAppDeployButton, [data-testid="stToolbar"] {
        visibility: hidden !important; 
        display: none !important;
    }
    
    .main .block-container {
        padding-top: 2rem !important;
        padding-bottom: 5rem !important;
        max-width: 100% !important;
    }
    
    /* Styling Header */
    .header-box {
        text-align: center;
        margin-bottom: 20px;
    }
    .header-box img {
        max-width: 120px;
        border-radius: 50%;
        margin-bottom: 10px;
    }
    
    .moto-text {
        font-size: 0.85rem !important;
        color: #aaaaaa;
        font-style: italic;
        line-height: 1.4;
    }

    /* Input Box Floating style */
    .stChatInputContainer {
        padding-bottom: 20px !important;
    }
    
    .image-preview-card {
        background: #1a1a1a;
        padding: 10px;
        border-radius: 15px;
        border: 2px solid #00d9ff;
        margin-bottom: 15px;
    }
    </style>
    """, unsafe_allow_html=True)

# Inisialisasi Klien Groq
client = Groq(api_key=GROQ_API_KEY)

# ==========================================
# --- 1. DATABASE (MEMORI CHAT) ---
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
# --- 2. MEDIA HELPER ---
# ==========================================
def get_base64_file(file_path):
    if os.path.exists(file_path):
        with open(file_path, "rb") as f:
            return base64.b64encode(f.read()).decode()
    return None

def process_image(uploaded_file):
    img = Image.open(uploaded_file)
    if img.mode != 'RGB':
        img = img.convert('RGB')
    
    # Resize agar hemat kuota token & cepat
    img.thumbnail((1024, 1024), Image.Resampling.LANCZOS)
    
    img_byte_arr = io.BytesIO()
    img.save(img_byte_arr, format='JPEG', quality=85)
    img_byte_arr.seek(0)
    return img_byte_arr

async def text_to_speech(text):
    # Bersihkan simbol biar suara AI-nya nggak bingung
    clean_text = text.replace("*", "").replace("#", "").replace("`", "").replace("-", " ")
    communicate = edge_tts.Communicate(clean_text, "id-ID-ArdiNeural", pitch="-5Hz", rate="+10%")
    await communicate.save("temp_voice.mp3")

# ==========================================
# --- 3. SESSION STATE ---
# ==========================================
if "messages" not in st.session_state:
    st.session_state.messages = load_chat()
if "temp_img" not in st.session_state:
    st.session_state.temp_img = None

# ==========================================
# --- 4. UI HEADER ---
# ==========================================
gif_b64 = get_base64_file("kucing.gif")
st.markdown('<div class="header-box">', unsafe_allow_html=True)
if gif_b64:
    st.markdown(f'<img src="data:image/gif;base64,{gif_b64}">', unsafe_allow_html=True)
st.markdown('<h1>🤖 Djamantara AI</h1>', unsafe_allow_html=True)
st.markdown('<p class="moto-text">"Entar kon obâ\'. É tengnga jhâlân pas mu-nemmu. Lebbi bhagus nyaré élmo."</p>', unsafe_allow_html=True)
st.markdown('</div>', unsafe_allow_html=True)

# Tombol Aksi
col_up, col_del = st.columns([4, 1])
with col_del:
    if st.button("🗑️ Reset", use_container_width=True):
        if clear_chat_db():
            st.session_state.messages = []
            st.session_state.temp_img = None
            st.rerun()

with col_up:
    uploaded_file = st.file_uploader("Upload foto", type=["jpg", "png", "jpeg"], label_visibility="collapsed")

# Preview Gambar
if uploaded_file:
    st.session_state.temp_img = process_image(uploaded_file)
    with st.container():
        st.markdown('<div class="image-preview-card">', unsafe_allow_html=True)
        st.image(st.session_state.temp_img, caption="📸 Foto siap dianlisa Bos!", width=250)
        if st.button("❌ Hapus Foto"):
            st.session_state.temp_img = None
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

# ==========================================
# --- 5. LOGIKA CHAT ---
# ==========================================
# Tampilkan histori
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# Input User
if prompt := st.chat_input("Tanya apa hari ini, Bos?"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    save_chat("user", prompt)
    
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Si Kocheng lagi mikir..."):
            try:
                # JIKA ADA GAMBAR
                if st.session_state.temp_img:
                    b64_data = base64.b64encode(st.session_state.temp_img.read()).decode()
                    response = client.chat.completions.create(
                        messages=[{
                            "role": "user",
                            "content": [
                                {"type": "text", "text": f"Nama kamu Djamantara. Jawab santai, kocak, gaya bahasa Indonesia-Madura. Panggil 'Bos'. Analisa ini: {prompt}"},
                                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64_data}"}}
                            ]
                        }],
                        model="llama-3.2-90b-vision-preview", # MODEL TERBARU
                    )
                # JIKA CHAT BIASA
                else:
                    context = st.session_state.messages[-6:] # Ambil 6 pesan terakhir buat konteks
                    response = client.chat.completions.create(
                        messages=[
                            {"role": "system", "content": "Kamu Djamantara, asisten kucing hitam keren & kocak. Panggil user 'Bos'. Gunakan bahasa santai Indonesia-Madura."},
                            *context
                        ],
                        model="llama-3.3-70b-versatile",
                    )
                
                full_response = response.choices[0].message.content
                st.markdown(full_response)
                
                # TTS (Suara)
                try:
                    asyncio.run(text_to_speech(full_response))
                    if os.path.exists("temp_voice.mp3"):
                        st.audio("temp_voice.mp3", format="audio/mpeg", autoplay=True)
                except: pass

                # Simpan ke memori
                st.session_state.messages.append({"role": "assistant", "content": full_response})
                save_chat("assistant", full_response)

            except Exception as e:
                st.error(f"Duh Bos, sistem macet: {str(e)}")

# Bersihkan file suara lama
if os.path.exists("temp_voice.mp3"):
    try: os.remove("temp_voice.mp3")
    except: pass
