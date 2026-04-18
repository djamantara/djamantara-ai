import streamlit as st
import time
import edge_tts
import asyncio
import base64
import os
import sqlite3
from PIL import Image
import io
from groq import Groq

# ==========================================
# --- KONFIGURASI API AMAN (SECRETS) ---
# ==========================================
if "GROQ_API_KEY" in st.secrets:
    GROQ_API_KEY = st.secrets["GROQ_API_KEY"]
else:
    st.error("⚠️ API Key 'GROQ_API_KEY' tidak ditemukan! Cek Settings > Secrets.")
    st.stop()

# Setup Client
client = None
try:
    client = Groq(api_key=GROQ_API_KEY)
except Exception as e:
    st.error(f"⚠️ Waduh Bos, Groq-nya bermasalah: {e}")

# ==========================================
# --- SETTING LAYAR MOBILE RESPONSIF ---
# ==========================================
st.set_page_config(
    page_title="Djamantara AI", 
    page_icon="🐱", 
    layout="centered",
    initial_sidebar_state="expanded"
)

# ==========================================
# --- CSS INJECTION (HIDE BRANDING + RESPONSIVE) ---
# ==========================================
st.markdown("""
    <style>
    /* HIDE STREAMLIT BRANDING */
    #MainMenu {visibility: hidden;}
    header {visibility: hidden;}
    footer {visibility: hidden !important;}
    .stAppDeployButton {visibility: hidden !important;}
    [data-testid="stFooter"] {visibility: hidden !important; display: none !important;}
    .stDeployButton {display: none !important;}
    
    /* LAYOUT */
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
    
    /* MOBILE */
    @media only screen and (max-width: 600px) {
        h1 { font-size: 1.8rem !important; }
        .moto-text { font-size: 0.8rem !important; }
    }
    </style>
    """, unsafe_allow_html=True)

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

init_db()

# ==========================================
# --- 2. FUNGSI PENDUKUNG ---
# ==========================================
def get_local_gif(file_path):
    if os.path.exists(file_path):
        with open(file_path, "rb") as file_:
            contents = file_.read()
            data_url = base64.b64encode(contents).decode("utf-8")
        return data_url
    return None

def encode_image(uploaded_file):
    uploaded_file.seek(0)
    return base64.b64encode(uploaded_file.read()).decode('utf-8')

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

def autoplay_audio(file_path):
    if os.path.exists(file_path):
        with open(file_path, "rb") as f:
            data = f.read()
            b64 = base64.b64encode(data).decode()
            md = f'<audio autoplay="true"><source src="data:audio/mp3;base64,{b64}" type="audio/mp3"></audio>'
            st.markdown(md, unsafe_allow_html=True)

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

# ==========================================
# --- SIDEBAR (UPLOAD + HAPUS INGATAN) ---
# ==========================================
with st.sidebar:
    st.title("👁️ Mata Kocheng")
    st.markdown("### Upload Foto")
    uploaded_file = st.file_uploader("Kirim foto...", type=["jpg", "jpeg", "png"], help="Upload foto untuk dianalisa oleh Djamantara")
    
    if uploaded_file:
        st.session_state.current_image = uploaded_file
        st.image(uploaded_file, caption="Foto Siap!", use_container_width=True)
        st.success("✅ Foto berhasil diupload!")
    elif "current_image" in st.session_state:
        st.image(st.session_state.current_image, caption="Foto Siap!", use_container_width=True)
        uploaded_file = st.session_state.current_image
        st.success("✅ Foto tersimpan!")
    
    st.divider()
    
    # ✅ TOMBOL HAPUS INGATAN (DENGAN KONFIRMASI)
    st.markdown("### ⚙️ Pengaturan")
    if st.button("🗑️ Hapus Ingatan", use_container_width=True, help="Hapus semua riwayat chat"):
        st.session_state.confirm_delete = True

    if st.session_state.get("confirm_delete", False):
        st.warning("Yakin ingin menghapus semua riwayat? Data tidak bisa dikembalikan.")
        col1, col2 = st.columns(2)
        if col1.button("✅ Ya, Hapus", use_container_width=True):
            conn = sqlite3.connect('djamantara_memory.db')
            conn.cursor().execute("DELETE FROM chat_history")
            conn.commit()
            conn.close()
            
            st.session_state.messages = []
            if "current_image" in st.session_state:
                del st.session_state.current_image
            st.session_state.confirm_delete = False  # Reset flag
            st.success("✅ Ingatan berhasil dihapus!")
            st.rerun()
            
        if col2.button("❌ Batal", use_container_width=True):
            st.session_state.confirm_delete = False
            st.rerun()
    
    st.markdown("---")
    st.markdown("*Djamantara AI - Kocheng Pinter*")

# ==========================================
# --- CHAT HISTORY ---
# ==========================================
if "messages" not in st.session_state:
    st.session_state.messages = load_chat()

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# ==========================================
# --- 4. LOGIKA PERCAKAPAN ---
# ==========================================
if prompt := st.chat_input("Ngobrol moso Djamantara, Bos..."):
    if not client:
        st.error("⚠️ Koneksi ke Groq belum siap. Cek API Key di secrets.")
        st.stop()

    st.session_state.messages.append({"role": "user", "content": prompt})
    save_chat("user", prompt)
    
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Si Kocheng lagi ngintip..."):
            try:
                # ✅ AMBIL GAMBAR DARI SESSION STATE (LEBIH STABIL)
                image_to_use = st.session_state.get("current_image")
                
                if image_to_use:
                    base64_image = encode_image(image_to_use)
                    response = client.chat.completions.create(
                        messages=[
                            {
                                "role": "user",
                                "content": [
                                    {"type": "text", "text": f"Nama kamu Djamantara. Jawab santai, kocak, bahasa Indonesia campur Madura sedikit. Panggil 'Bos'. Analisa ini: {prompt}"},
                                    {
                                        "type": "image_url",
                                        "image_url": { "url": f"data:image/jpeg;base64,{base64_image}" },
                                    },
                                ],
                            }
                        ],
                        model="meta-llama/llama-4-scout-17b-16e-instruct",
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
                autoplay_audio("temp_voice.mp3")
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