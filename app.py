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
    /* Hide default elements */
    #MainMenu, footer, header, .stAppDeployButton, [data-testid="stToolbar"] {
        visibility: hidden !important; 
        display: none !important;
    }
    .viewerBadge, .github-link, [data-testid="stDecoration"] {
        visibility: hidden !important; 
        display: none !important;
    }
    
    /* Container adjustments */
    .main .block-container {
        padding-top: 1rem !important;
        padding-bottom: 1rem !important;
        padding-left: 0.5rem !important;
        padding-right: 0.5rem !important;
        max-width: 100% !important;
    }
    
    /* GIF Styling */
    .cat-container img {
        max-width: 100px !important;
        height: auto !important;
        display: block !important;
        margin: 0 auto !important;
    }
    .moto-text {
        font-size: 0.85rem !important;
        line-height: 1.4 !important;
        text-align: center !important;
        margin-top: 5px !important;
        margin-bottom: 15px !important;
    }
    
    /* Image Preview Box */
    .image-preview-box {
        background: linear-gradient(135deg, #1e3a5f 0%, #0d1b2a 100%);
        padding: 15px;
        border-radius: 15px;
        margin: 10px 0;
        border: 2px solid #00d9ff;
        box-shadow: 0 4px 15px rgba(0, 217, 255, 0.3);
    }
    .image-preview-box img {
        border-radius: 10px;
        max-width: 100%;
        height: auto;
    }
    
    /* Info Box */
    .info-box {
        background: #0d1b2a;
        padding: 10px;
        border-radius: 8px;
        margin: 10px 0;
        font-size: 0.8rem;
        color: #00d9ff;
        text-align: center;
    }
    
    /* Chat Input Container */
    .stChatInputContainer {
        padding-bottom: 1rem !important;
        padding-top: 0.5rem !important;
    }
    
    /* Mobile Text */
    @media only screen and (max-width: 600px) {
        h1 { font-size: 1.5rem !important; }
        .moto-text { font-size: 0.75rem !important; }
        .stChatMessage { padding: 0.5rem !important; }
    }
    
    /* Scrollbar */
    ::-webkit-scrollbar { width: 6px; }
    ::-webkit-scrollbar-track { background: #0e1117; }
    ::-webkit-scrollbar-thumb { background: #555; border-radius: 3px; }
    </style>
    """, unsafe_allow_html=True)

# Setup Klien API
try:
    client = Groq(api_key=GROQ_API_KEY)
except Exception as e:
    st.error(f"⚠️ Waduh Bos, Groq-nya bermasalah: {e}")

# ==========================================
# --- 1. SISTEM INGATAN (DATABASE) ---
# ==========================================
def init_db():
    conn = sqlite3.connect('djamantara_memory.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS chat_history 
                 (role TEXT, content TEXT, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')
    conn.commit()
    conn.close()

def save_chat(role, content):
    try:
        conn = sqlite3.connect('djamantara_memory.db')
        c = conn.cursor()
        c.execute("INSERT INTO chat_history (role, content) VALUES (?, ?)", (role, str(content)))
        conn.commit()
        conn.close()
    except: pass

def load_chat():
    try:
        conn = sqlite3.connect('djamantara_memory.db')
        c = conn.cursor()
        c.execute("SELECT role, content FROM chat_history ORDER BY timestamp ASC")
        history = c.fetchall()
        conn.close()
        return [{"role": r, "content": c} for r, c in history]
    except: return []

def clear_chat_db():
    try:
        conn = sqlite3.connect('djamantara_memory.db')
        conn.cursor().execute("DELETE FROM chat_history")
        conn.commit()
        conn.close()
        return True
    except:
        return False

init_db()

# ==========================================
# --- 2. FUNGSI PENDUKUNG (MEDIA) ---
# ==========================================
def get_local_gif(file_path):
    if os.path.exists(file_path):
        with open(file_path, "rb") as file_:
            contents = file_.read()
            return base64.b64encode(contents).decode("utf-8")
    return None

def compress_image(uploaded_file, max_size=1024, quality=85):
    """
    Auto-compress gambar agar ukurannya kecil
    """
    img = Image.open(uploaded_file)
    if img.mode in ('RGBA', 'P', 'LA'):
        img = img.convert('RGB')
    
    width, height = img.size
    if width > max_size or height > max_size:
        ratio = min(max_size / width, max_size / height)
        new_size = (int(width * ratio), int(height * ratio))
        img = img.resize(new_size, Image.Resampling.LANCZOS)
    
    img_byte_arr = io.BytesIO()
    img.save(img_byte_arr, format='JPEG', quality=quality, optimize=True)
    img_byte_arr.seek(0)
    
    return img_byte_arr

def encode_image(image_source):
    """Encode image ke base64"""
    if hasattr(image_source, 'seek'):
        image_source.seek(0)
    return base64.b64encode(image_source.read()).decode('utf-8')

def run_async_safe(coro_func, *args):
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import threading
            result = None
            def _run():
                nonlocal result
                new_loop = asyncio.new_event_loop()
                asyncio.set_event_loop(new_loop)
                result = new_loop.run_until_complete(coro_func(*args))
                new_loop.close()
            thread = threading.Thread(target=_run)
            thread.start()
            thread.join()
            return result
        else:
            return loop.run_until_complete(coro_func(*args))
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(coro_func(*args))
        loop.close()
        return result

async def generate_voice(text):
    clean_text = text.replace("*", "").replace("#", "").replace("`", "").replace("-", " ")
    communicate = edge_tts.Communicate(clean_text, "id-ID-ArdiNeural", pitch="-5Hz", rate="+10%")
    await communicate.save("temp_voice.mp3")

# ==========================================
# --- 3. INISIALISASI SESSION STATE ---
# ==========================================
if "messages" not in st.session_state:
    st.session_state.messages = load_chat()
if "current_image" not in st.session_state:
    st.session_state.current_image = None
if "compressed_image" not in st.session_state:
    st.session_state.compressed_image = None

# ==========================================
# --- 4. TAMPILAN UTAMA ---
# ==========================================

# --- TAMPILKAN GIF HEADER ---
gif_data = get_local_gif("kucing.gif")

# !!! PENTING: Pastikan baris di bawah ini lengkap menjadi 'if gif_data:' !!!
if gif_
    st.markdown(
        f"""
        <div style="text-align: center; margin-top: -20px;" class="cat-container">
            <img src="image/gif;base64,{gif_data}" style="z-index: 1;">
            <h1 style="margin: 0; padding: 0;">🤖 Djamantara AI</h1>
            <p class="moto-text" style="color: gray; font-style: italic;">
                "Entar kon obâ'. É tengnga jhâlân pas mu-nemmu. Oréng od i' jhâ' alako jhubâ'. Lebbi bhagus nyaré élmo."
            </p>
        </div>
        """, 
        unsafe_allow_html=True
    )
else:
    st.markdown("<h1 style='text-align: center;'>🤖 Djamantara AI</h1>", unsafe_allow_html=True)

# --- TOMBOL HAPUS CHAT & UPLOAD FOTO ---
col1, col2 = st.columns([3, 1])
with col1:
    st.markdown("### 📸 Upload Foto (Auto Compress)")
with col2:
    if st.button("🗑️ Hapus Chat", use_container_width=True, help="Hapus semua riwayat chat"):
        if clear_chat_db():
            st.session_state.messages = []
            st.rerun()

# --- UPLOAD FOTO DENGAN AUTO-COMPRESS ---
uploaded_file = st.file_uploader("", type=["jpg", "jpeg", "png"], key="main_uploader", label_visibility="collapsed")

if uploaded_file:
    with st.spinner("🔄 Kompres foto..."):
        try:
            compressed_img = compress_image(uploaded_file, max_size=1024, quality=85)
            st.session_state.current_image = uploaded_file
            st.session_state.compressed_image = compressed_img
            st.success("✅ Foto berhasil diupload & dikompres!")
        except Exception as e:
            st.error(f"❌ Gagal kompres: {e}")

# --- INFO UKURAN FILE ---
if st.session_state.compressed_image is not None:
    st.session_state.compressed_image.seek(0)
    size_kb = len(st.session_state.compressed_image.read()) / 1024
    st.markdown(f'<div class="info-box">📦 Ukuran setelah kompres: {size_kb:.1f} KB</div>', unsafe_allow_html=True)

# --- TAMPILKAN FOTO JIKA ADA (PREVIEW PERMANEN) ---
if st.session_state.current_image is not None:
    st.markdown('<div class="image-preview-box">', unsafe_allow_html=True)
    col1, col2 = st.columns([4, 1])
    with col1:
        st.image(st.session_state.current_image, caption="📸 Foto yang akan dianalisa", use_container_width=True)
    with col2:
        if st.button("❌ Hapus Foto", use_container_width=True):
            st.session_state.current_image = None
            st.session_state.compressed_image = None
            st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

# --- CHAT HISTORY ---
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# ==========================================
# --- 5. LOGIKA PERCAKAPAN ---
# ==========================================
if prompt := st.chat_input("Ngobrol moso Djamantara, Bos..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    save_chat("user", prompt)
    
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Si Kocheng lagi ngintip..."):
            try:
                image_to_use = st.session_state.compressed_image
                
                if image_to_use:
                    base64_image = encode_image(image_to_use)
                    
                    # Menggunakan model vision terbaru yang supported
                    response = client.chat.completions.create(
                        messages=[
                            {
                                "role": "user",
                                "content": [
                                    {"type": "text", "text": f"Nama kamu Djamantara. Jawab santai, kocak, bahasa Indonesia campur Madura sedikit. Panggil 'Bos'. Analisa ini: {prompt}"},
                                    {"type": "image_url", "image_url": {"url": f"image/jpeg;base64,{base64_image}"}}
                                ]
                            }
                        ],
                        model="llama-3.2-90b-vision-preview",
                    )
                    full_response = response.choices[0].message.content
                else:
                    context = st.session_state.messages[-5:]
                    chat_completion = client.chat.completions.create(
                        messages=[
                            {"role": "system", "content": "Nama kamu Djamantara, asisten kucing hitam keren & kocak. Panggil user 'Bos'. Gunakan bahasa santai Indonesia-Madura."},
                            *context
                        ],
                        model="llama-3.3-70b-versatile",
                    )
                    full_response = chat_completion.choices[0].message.content
                
                placeholder = st.empty()
                displayed_text = ""
                for char in full_response:
                    displayed_text += char
                    placeholder.markdown(displayed_text + "▌")
                    time.sleep(0.005)
                placeholder.markdown(full_response)

                run_async_safe(generate_voice, full_response)
                if os.path.exists("temp_voice.mp3"):
                    st.audio("temp_voice.mp3", format="audio/mpeg")

                st.session_state.messages.append({"role": "assistant", "content": full_response})
                save_chat("assistant", full_response)
                
            except Exception as e:
                st.error(f"Duh Bos, sistem macet: {str(e)}")

# Cleanup
if os.path.exists("temp_voice.mp3"):
    try: 
        time.sleep(3)
        os.remove("temp_voice.mp3")
    except: pass