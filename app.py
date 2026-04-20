import streamlit as st
import time
import edge_tts
import asyncio
import base64
import os
import sqlite3
from groq import Groq

# --- KONFIGURASI API (AMAN) ---
# API Key sekarang dipanggil dari Streamlit Secrets
try:
    GROQ_API_KEY = st.secrets["GROQ_API_KEY"]
except Exception:
    st.error("⚠️ API Key 'GROQ_API_KEY' tidak ditemukan di Secrets, Bos!")
    st.stop()

# --- SETTING LAYAR MOBILE RESPONSIF ---
st.set_page_config(
    page_title="Djamantara AI", 
    page_icon="🐱", 
    layout="centered",
    initial_sidebar_state="collapsed"
)

# --- CSS INJECTION (Biar Ganteng di Hape) ---
st.markdown("""
    <style>
    .main .block-container {
        padding: 2rem 1rem 5rem 1rem;
    }
    .cat-container img {
        max-width: 100px;
        height: auto;
        border-radius: 50%;
    }
    .moto-text {
        font-size: 0.85rem !important;
        color: gray;
        font-style: italic;
        text-align: center;
    }
    footer {visibility: hidden;}
    #MainMenu {visibility: hidden;}
    .stChatInputContainer {
        padding-bottom: 20px;
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
    conn = sqlite3.connect('djamantara_memory.db', check_same_thread=False)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS chat_history 
                 (role TEXT, content TEXT, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')
    conn.commit()
    return conn

db_conn = init_db()

def save_chat(role, content):
    try:
        c = db_conn.cursor()
        c.execute("INSERT INTO chat_history (role, content) VALUES (?, ?)", (role, str(content)))
        db_conn.commit()
    except: pass

def load_chat():
    try:
        c = db_conn.cursor()
        c.execute("SELECT role, content FROM chat_history ORDER BY timestamp ASC")
        return [{"role": r, "content": c} for r, c in c.fetchall()]
    except: return []

# ==========================================
# --- 2. FUNGSI PENDUKUNG (MEDIA) ---
# ==========================================
def get_local_gif(file_path):
    if os.path.exists(file_path):
        with open(file_path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")
    return None

def encode_image(uploaded_file):
    return base64.b64encode(uploaded_file.getvalue()).decode('utf-8')

async def generate_voice(text):
    # Bersihkan markdown agar suara tidak mengeja simbol
    clean_text = text.replace("*", "").replace("#", "").replace("`", "").replace("-", " ")
    communicate = edge_tts.Communicate(clean_text, "id-ID-ArdiNeural", pitch="-5Hz", rate="+10%")
    await communicate.save("temp_voice.mp3")

def autoplay_audio(file_path):
    if os.path.exists(file_path):
        with open(file_path, "rb") as f:
            data = f.read()
            b64 = base64.b64encode(data).decode()
            st.markdown(f'<audio autoplay="true"><source src="data:audio/mp3;base64,{b64}" type="audio/mp3"></audio>', unsafe_allow_html=True)

# ==========================================
# --- 3. TAMPILAN UTAMA ---
# ==========================================
gif_data = get_local_gif("kucing.gif")

if gif_data:
    st.markdown(
        f"""
        <div style="text-align: center; margin-top: -30px;" class="cat-container">
            <img src="data:image/gif;base64,{gif_data}">
            <h2 style="margin: 0;">🤖 Djamantara AI</h2>
            <p class="moto-text">
                "Entar kon obâ'. É tengnga jhâlân pas mu-nemmu. Oréng od i' jhâ' alako jhubâ'. Lebbi bhagus nyaré élmo."
            </p>
        </div>
        """, 
        unsafe_allow_html=True
    )

with st.sidebar:
    st.header("👁️ Mata Kocheng")
    uploaded_file = st.file_uploader("Kirim foto...", type=["jpg", "jpeg", "png"])
    if uploaded_file:
        st.image(uploaded_file, caption="Foto Siap!", use_container_width=True)
    
    st.divider()
    if st.button("Hapus Ingatan"):
        db_conn.cursor().execute("DELETE FROM chat_history")
        db_conn.commit()
        st.session_state.messages = []
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
                if uploaded_file:
                    base64_image = encode_image(uploaded_file)
                    response = client.chat.completions.create(
                        messages=[
                            {
                                "role": "user",
                                "content": [
                                    {"type": "text", "text": f"Nama kamu Djamantara. Jawab santai, kocak, bahasa Indonesia campur Madura sedikit. Panggil 'Bos'. Analisa ini: {prompt}"},
                                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}},
                                ],
                            }
                        ],
                        model="llama-3.2-11b-vision-preview",
                    )
                else:
                    context = st.session_state.messages[-6:]
                    response = client.chat.completions.create(
                        messages=[
                            {"role": "system", "content": "Nama kamu Djamantara, asisten kucing hitam keren & kocak. Panggil user 'Bos'. Gunakan bahasa santai Indonesia-Madura."},
                            *context
                        ],
                        model="llama-3.3-70b-versatile",
                    )
                
                full_response = response.choices[0].message.content
                
                # Efek ngetik
                placeholder = st.empty()
                displayed_text = ""
                for char in full_response:
                    displayed_text += char
                    placeholder.markdown(displayed_text + "▌")
                    time.sleep(0.005)
                placeholder.markdown(full_response)

                # Audio TTS
                asyncio.run(generate_voice(full_response))
                autoplay_audio("temp_voice.mp3")
                
                st.session_state.messages.append({"role": "assistant", "content": full_response})
                save_chat("assistant", full_response)
                
            except Exception as e:
                st.error(f"Duh Bos, sistem macet: {str(e)}")
