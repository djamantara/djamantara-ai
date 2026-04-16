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
GROQ_API_KEY = st.secrets.get("GROQ_API_KEY", os.getenv("GROQ_API_KEY", "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"))
if not GROQ_API_KEY:
    st.error("⚠️ API Key tidak ditemukan!")
    st.stop()

st.set_page_config(page_title="Djamantara AI", page_icon="🐱", layout="centered")

# ==========================================
# 🎨 CSS CUSTOM - GEMINI STYLE
# ==========================================
st.markdown("""
    <style>
    #MainMenu, footer, header, .stAppDeployButton, [data-testid="stToolbar"] {
        visibility: hidden !important; display: none !important;
    }
    
    /* Header Animation */
    .header-box { text-align: center; padding: 1rem; }
    .header-box img { max-width: 100px; border-radius: 50%; border: 2px solid #00d9ff; }
    
    /* Floating Action Button Style untuk Upload */
    div[data-testid="stExpander"] {
        border: none !important;
        background: transparent !important;
    }
    
    /* Preview Gambar Minimalis */
    .preview-container {
        position: fixed;
        bottom: 100px;
        left: 50%;
        transform: translateX(-50%);
        z-index: 1000;
        background: #1e1e1e;
        padding: 10px;
        border-radius: 15px;
        border: 1px solid #00d9ff;
        display: flex;
        align-items: center;
        gap: 10px;
        box-shadow: 0px 4px 15px rgba(0,0,0,0.5);
    }
    
    .moto-text { font-size: 0.8rem; color: #888; font-style: italic; }
    </style>
    """, unsafe_allow_html=True)

client = Groq(api_key=GROQ_API_KEY)

# ==========================================
# --- DATABASE & LOGIC ---
# ==========================================
def init_db():
    conn = sqlite3.connect('djamantara_memory.db', check_same_thread=False)
    conn.execute('CREATE TABLE IF NOT EXISTS chat_history (role TEXT, content TEXT, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)')
    conn.close()

def save_chat(role, content):
    conn = sqlite3.connect('djamantara_memory.db', check_same_thread=False)
    conn.execute("INSERT INTO chat_history (role, content) VALUES (?, ?)", (role, str(content)))
    conn.commit()
    conn.close()

init_db()

async def text_to_speech(text):
    clean_text = text.replace("*", "").replace("#", "")
    communicate = edge_tts.Communicate(clean_text, "id-ID-ArdiNeural", pitch="-5Hz")
    await communicate.save("temp_voice.mp3")

# ==========================================
# --- UI RENDER ---
# ==========================================

# Header
gif_b64 = "" 
if os.path.exists("kucing.gif"):
    with open("kucing.gif", "rb") as f:
        gif_b64 = base64.b64encode(f.read()).decode()

st.markdown('<div class="header-box">', unsafe_allow_html=True)
if gif_b64:
    st.markdown(f'<img src="data:image/gif;base64,{gif_b64}">', unsafe_allow_html=True)
st.markdown('<h1>Djamantara AI</h1><p class="moto-text">"Nyari ilmu dulu baru nyari kamu, Bos."</p></div>', unsafe_allow_html=True)

# Memori Session
if "messages" not in st.session_state:
    st.session_state.messages = []
if "image_data" not in st.session_state:
    st.session_state.image_data = None

# --- TOMBOL UPLOAD DINAMIS (POPOVER) ---
# Kita taruh tombol upload tepat di atas input chat
cols = st.columns([1, 1, 1])
with cols[1]:
    with st.popover("📎 Lampirkan Foto"):
        up = st.file_uploader("Pilih gambar", type=["jpg", "jpeg", "png"], label_visibility="collapsed")
        if up:
            img = Image.open(up)
            if img.mode != 'RGB': img = img.convert('RGB')
            img.thumbnail((800, 800))
            buf = io.BytesIO()
            img.save(buf, format='JPEG')
            st.session_state.image_data = buf.getvalue()
            st.success("Foto terlampir!")
        if st.button("🗑️ Reset Semua"):
            st.session_state.image_data = None
            st.session_state.messages = []
            st.rerun()

# Preview kecil jika ada gambar (seperti di Gemini)
if st.session_state.image_data:
    st.markdown('<div class="preview-container">', unsafe_allow_html=True)
    st.image(st.session_state.image_data, width=80)
    if st.button("❌"):
        st.session_state.image_data = None
        st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

# Tampilan Chat
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# Chat Input
if prompt := st.chat_input("Tanya apa hari ini, Bos?"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        try:
            if st.session_state.image_data:
                b64_img = base64.b64encode(st.session_state.image_data).decode()
                response = client.chat.completions.create(
                    messages=[{
                        "role": "user",
                        "content": [
                            {"type": "text", "text": f"Kamu Djamantara. Jawab kocak Indonesia-Madura. Bos nanya: {prompt}"},
                            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64_img}"}}
                        ]
                    }],
                    model="llama-3.2-90b-vision-preview",
                )
            else:
                response = client.chat.completions.create(
                    messages=[{"role": "system", "content": "Kamu Djamantara, panggil user 'Bos'."}] + st.session_state.messages[-5:],
                    model="llama-3.3-70b-versatile",
                )
            
            res_text = response.choices[0].message.content
            st.markdown(res_text)
            
            # Reset image setelah kirim (seperti Gemini)
            st.session_state.image_data = None
            
            asyncio.run(text_to_speech(res_text))
            if os.path.exists("temp_voice.mp3"):
                st.audio("temp_voice.mp3", autoplay=True)
                
            st.session_state.messages.append({"role": "assistant", "content": res_text})
            save_chat("assistant", res_text)
            
        except Exception as e:
            st.error(f"Error: {e}")
