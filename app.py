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
# ⚠️ Saran: Gunakan st.secrets di deployment. Hardcode hanya untuk dev lokal.
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
    .header-box { text-align: center; padding: 1rem; }
    .header-box img { max-width: 100px; border-radius: 50%; border: 2px solid #00d9ff; }
    div[data-testid="stExpander"] { border: none !important; background: transparent !important; }
    .preview-container {
        position: fixed; bottom: 100px; left: 50%; transform: translateX(-50%);
        z-index: 1000; background: #1e1e1e; padding: 10px; border-radius: 15px;
        border: 1px solid #00d9ff; display: flex; align-items: center; gap: 10px;
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
    clean_text = text.replace("*", "").replace("#", "").replace("_", "")
    communicate = edge_tts.Communicate(clean_text, "id-ID-ArdiNeural", pitch="-5Hz")
    await communicate.save("temp_voice.mp3")

def play_audio():
    if os.path.exists("temp_voice.mp3"):
        with open("temp_voice.mp3", "rb") as f:
            audio_bytes = f.read()
        st.audio(audio_bytes, format="audio/mp3", autoplay=True)
        try: os.remove("temp_voice.mp3") # Bersihkan file sementara
        except: pass

# ==========================================
# --- UI RENDER ---
# ==========================================
gif_b64 = ""
if os.path.exists("kucing.gif"):
    with open("kucing.gif", "rb") as f:
        gif_b64 = base64.b64encode(f.read()).decode()

st.markdown('<div class="header-box">', unsafe_allow_html=True)
if gif_b64:
    st.markdown(f'<img src="data:image/gif;base64,{gif_b64}">', unsafe_allow_html=True)
st.markdown('<h1>Djamantara AI</h1><p class="moto-text">"Nyari ilmu dulu baru nyari kamu, Bos."</p></div>', unsafe_allow_html=True)

if "messages" not in st.session_state:
    st.session_state.messages = []
if "image_data" not in st.session_state:
    st.session_state.image_data = None

# --- TOMBOL UPLOAD DINAMIS (POPOVER) ---
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
            st.success("✅ Foto terlampir!")
        if st.button("🗑️ Reset Semua", key="btn_reset"):
            st.session_state.image_data = None
            st.session_state.messages = []
            st.rerun()

# Preview kecil jika ada gambar
if st.session_state.image_data:
    st.markdown('<div class="preview-container">', unsafe_allow_html=True)
    st.image(st.session_state.image_data, width=80)
    if st.button("❌", key="remove_img"):
        st.session_state.image_data = None
        st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

# Tampilan Chat History
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# Chat Input
if prompt := st.chat_input("Tanya apa hari ini, Bos?"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("🧠 Sedang berpikir..."):
            try:
                # Siapkan payload untuk Groq
                user_content = [{"type": "text", "text": prompt}]
                if st.session_state.image_data:
                    b64_img = base64.b64encode(st.session_state.image_data).decode()
                    user_content.append({
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{b64_img}"}
                    })

                # Pilih model vision (mendukung teks + gambar)
                model_name = "llama-3.2-11b-vision-preview" 
                
                response = client.chat.completions.create(
                    model=model_name,
                    messages=[{"role": "user", "content": user_content}],
                    temperature=0.7,
                    max_tokens=1024
                )
                ai_reply = response.choices[0].message.content

                # Tampilkan & simpan
                st.markdown(ai_reply)
                st.session_state.messages.append({"role": "assistant", "content": ai_reply})
                
                save_chat("user", prompt)
                save_chat("assistant", ai_reply)

                # Generate & Putar Suara
                asyncio.run(text_to_speech(ai_reply))
                play_audio()

                # Hapus gambar setelah diproses
                st.session_state.image_data = None

            except Exception as e:
                error_msg = f"❌ Terjadi kesalahan: {str(e)}"
                st.error(error_msg)
                save_chat("user", prompt)
                save_chat("assistant", error_msg)