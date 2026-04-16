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
# 🎨 CSS INJECTION - QWEN STYLE UI
# ==========================================
st.markdown("""
    <style>
    /* Hide ALL default elements */
    #MainMenu, footer, header, .stAppDeployButton, [data-testid="stToolbar"] {
        visibility: hidden !important; 
        display: none !important;
    }
    .viewerBadge, .github-link, [data-testid="stDecoration"], .stDeployButton {
        visibility: hidden !important; 
        display: none !important;
    }
    
    /* Main container */
    .main .block-container {
        padding-top: 0.5rem !important;
        padding-bottom: 0rem !important;
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
        font-size: 0.8rem !important;
        line-height: 1.4 !important;
        text-align: center !important;
        margin-top: 5px !important;
        margin-bottom: 10px !important;
        color: #888 !important;
    }
    
    /* Image Preview Box - Qwen Style */
    .image-preview-box {
        background: #1a1f2e;
        padding: 10px;
        border-radius: 12px;
        margin: 10px 0;
        border: 1px solid #333;
    }
    .image-preview-box img {
        border-radius: 8px;
        max-width: 100%;
        height: auto;
    }
    
    /* Chat Input Container - Qwen Style */
    .stChatInputContainer {
        position: fixed !important;
        bottom: 0 !important;
        left: 0 !important;
        right: 0 !important;
        width: 100% !important;
        padding: 10px 15px 15px 15px !important;
        background: linear-gradient(to top, #0e1117 0%, transparent 100%) !important;
        z-index: 999 !important;
        margin: 0 !important;
    }
    
    /* Upload Button - Qwen Style (Integrated with chat) */
    .upload-button-container {
        display: flex;
        align-items: center;
        gap: 10px;
        margin-bottom: 10px;
    }
    
    /* St file uploader styling */
    .stFileUploader {
        display: inline-block;
    }
    .stFileUploader > div {
        min-width: auto !important;
    }
    
    /* Hide file uploader default button */
    .stFileUploader label, .stFileUploader [data-testid="stWidgetLabel"] {
        display: none !important;
    }
    
    /* Custom upload button styling */
    .custom-upload-btn {
        background: #2d3561 !important;
        color: white !important;
        border: 1px solid #444 !important;
        padding: 8px 16px !important;
        border-radius: 8px !important;
        cursor: pointer !important;
        font-size: 0.9rem !important;
        display: inline-flex !important;
        align-items: center !important;
        gap: 6px !important;
        transition: all 0.3s !important;
    }
    .custom-upload-btn:hover {
        background: #3d4571 !important;
        border-color: #666 !important;
    }
    
    /* Chat messages spacing */
    .stChatMessage {
        padding: 0.5rem !important;
        margin-bottom: 5px !important;
    }
    
    /* Mobile adjustments */
    @media only screen and (max-width: 600px) {
        h1 { font-size: 1.5rem !important; }
        .moto-text { font-size: 0.7rem !important; }
        .stChatMessage { padding: 0.5rem !important; }
        .stChatInputContainer {
            padding: 8px 10px 12px 10px !important;
        }
    }
    
    /* Hide scrollbar */
    ::-webkit-scrollbar { width: 0px; }
    
    /* Main content padding bottom for chat input */
    .main > div {
        padding-bottom: 150px !important;
    }
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
gif_result = get_local_gif("kucing.gif")

if gif_result is not None:
    st.markdown(
        f"""
        <div style="text-align: center; margin-top: -10px;" class="cat-container">
            <img src="image/gif;base64,{gif_result}" style="z-index: 1;">
            <h1 style="margin: 5px 0; padding: 0; font-size: 1.5rem;">🤖 Djamantara AI</h1>
            <p class="moto-text">
                "Entar kon obâ'. É tengnga jhâlân pas mu-nemmu."
            </p>
        </div>
        """, 
        unsafe_allow_html=True
    )
else:
    st.markdown("<h1 style='text-align: center; margin-top: 10px;'>🤖 Djamantara AI</h1>", unsafe_allow_html=True)

# --- TAMPILKAN FOTO JIKA ADA ---
if st.session_state.current_image is not None:
    st.markdown('<div class="image-preview-box">', unsafe_allow_html=True)
    col1, col2, col3 = st.columns([5, 1, 1])
    with col1:
        st.image(st.session_state.current_image, caption="", use_container_width=True)
    with col2:
        if st.button("❌", use_container_width=True, help="Hapus foto"):
            st.session_state.current_image = None
            st.session_state.compressed_image = None
            st.rerun()
    with col3:
        if st.button("🗑️ Chat", use_container_width=True, help="Hapus semua chat"):
            if clear_chat_db():
                st.session_state.messages = []
                st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

# --- CHAT HISTORY ---
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# ==========================================
# --- 5. CHAT INPUT & UPLOAD (QWEN STYLE) ---
# ==========================================
# Container untuk upload dan chat input (fixed di bawah)
with st.container():
    # Upload button row
    col_upload1, col_upload2 = st.columns([4, 1])
    with col_upload1:
        st.markdown('<div style="padding: 5px 0; font-size: 0.85rem; color: #888;">📎 Upload foto untuk dianalisa</div>', unsafe_allow_html=True)
    with col_upload2:
        uploaded_file = st.file_uploader("", type=["jpg", "jpeg", "png"], key="main_uploader", label_visibility="collapsed")
        
        if uploaded_file:
            with st.spinner("🔄"):
                try:
                    compressed_img = compress_image(uploaded_file, max_size=1024, quality=85)
                    st.session_state.current_image = uploaded_file
                    st.session_state.compressed_image = compressed_img
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ {e}")

# ==========================================
# --- 6. LOGIKA PERCAKAPAN ---
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