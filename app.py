import streamlit as st
import time
import edge_tts
import asyncio
import base64
import os
import sqlite3
import nest_asyncio

# Wajib agar asyncio berjalan lancar di Streamlit
nest_asyncio.apply()

# ==========================================
# --- KONFIGURASI PAGE & API ---
# ==========================================
st.set_page_config(page_title="Djamantara AI", page_icon="🐱", layout="centered", initial_sidebar_state="collapsed")

if "GROQ_API_KEY" in st.secrets:
    GROQ_API_KEY = st.secrets["GROQ_API_KEY"]
else:
    GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
    if not GROQ_API_KEY:
        st.error("⚠️ API Key belum disetting di Secrets atau Environment!")
        st.stop()

try:
    client = Groq(api_key=GROQ_API_KEY)
except Exception as e:
    st.error(f"⚠️ Gagal koneksi ke Groq: {e}")
    st.stop()

# ==========================================
#  CSS - DESAIN DARK MINIMALIS
# ==========================================
st.markdown("""
    <style>
    #MainMenu {visibility: hidden;} header {visibility: hidden;} footer {visibility: hidden !important;}
    .stAppDeployButton, [data-testid="stFooter"], .stDeployButton {display: none !important;}
    .main .block-container { padding-top: 1.5rem; padding-bottom: 5rem; }
    
    .cat-container img { max-width: 80px; height: auto; margin-bottom: 10px; }
    h1 { text-align: center; margin: 0; font-size: 1.8rem; color: #fff; }
    .moto { text-align: center; color: #888; font-style: italic; font-size: 0.85rem; margin-bottom: 20px; line-height: 1.6; }
    
    .control-panel { position: fixed; bottom: 0; left: 0; right: 0; background: #0e1117; padding: 10px 15px; z-index: 999; border-top: 1px solid #333; }
    .stButton>button { width: 100%; border-radius: 6px; font-weight: 600; }
    
    .img-preview-box { 
        position: fixed; bottom: 70px; left: 50%; transform: translateX(-50%); 
        background: #1e232e; padding: 5px 10px; border-radius: 8px; border: 1px solid #444;         z-index: 998; font-size: 0.8rem; color: #aaa; 
    }
    </style>
    """, unsafe_allow_html=True)

# ==========================================
# --- DATABASE ---
# ==========================================
def init_db():
    conn = sqlite3.connect('djamantara_memory.db', check_same_thread=False)
    conn.execute('''CREATE TABLE IF NOT EXISTS chat_history 
                    (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                     role TEXT, 
                     content TEXT, 
                     timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')
    conn.commit()
    conn.close()

def save_chat(role, content):
    try:
        conn = sqlite3.connect('djamantara_memory.db', check_same_thread=False)
        conn.execute("INSERT INTO chat_history (role, content) VALUES (?, ?)", (role, str(content)))
        conn.commit()
        conn.close()
    except Exception:
        pass

def load_chat():
    try:
        conn = sqlite3.connect('djamantara_memory.db', check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute("SELECT role, content FROM chat_history ORDER BY timestamp ASC")
        results = [{"role": row[0], "content": row[1]} for row in cursor.fetchall()]
        conn.close()
        return results
    except Exception:
        return []

init_db()

# ==========================================
# --- HELPER FUNCTIONS ---
# ==========================================
def get_gif(path):
    if os.path.exists(path):
        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode()
    return None

def encode_img(file_obj):    file_obj.seek(0)
    return base64.b64encode(file_obj.read()).decode()

async def gen_voice(text):
    clean = text.replace("*", "").replace("#", "").replace("`", "").replace("-", " ").strip()
    if not clean:
        return
    communicate = edge_tts.Communicate(clean, "id-ID-ArdiNeural", pitch="-5Hz", rate="+10%")
    await communicate.save("temp_voice.mp3")

def play_audio(path):
    if os.path.exists(path):
        with open(path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
        st.markdown(f'''
            <audio autoplay="true" controls="false">
                <source src="data:audio/mp3;base64,{b64}" type="audio/mp3">
            </audio>
        ''', unsafe_allow_html=True)

# ==========================================
# --- UI HEADER ---
# ==========================================
gif_data = get_gif("kucing.gif")
st.markdown('<div class="cat-container" style="text-align:center;">', unsafe_allow_html=True)
if gif_data:
    st.markdown(f'<img src="data:image/gif;base64,{gif_data}">', unsafe_allow_html=True)
else:
    st.markdown('<div style="font-size: 3rem;">🐱</div>', unsafe_allow_html=True)
st.markdown('<h1>🤖 Djamantara AI</h1>', unsafe_allow_html=True)
st.markdown('''<p class="moto">"Entar kon obâ'. É tengnga jhâlân pas mu-nemmu. Oréng od i' jhâ' alako jhubâ'. Lebbi bhagus nyaré élmo."</p>''', unsafe_allow_html=True)
st.markdown('</div>', unsafe_allow_html=True)
st.markdown('<hr style="border: 1px solid #333; margin: 15px 0;">', unsafe_allow_html=True)

# ==========================================
# --- SESSION STATE & UPLOAD ---
# ==========================================
if "messages" not in st.session_state:
    st.session_state.messages = load_chat()
if "current_image" not in st.session_state:
    st.session_state.current_image = None

# Upload Gambar
uploaded_file = st.file_uploader("", type=["jpg", "jpeg", "png"], label_visibility="collapsed")
if uploaded_file:
    st.session_state.current_image = uploaded_file

# Preview Gambar Terlampir
if st.session_state.current_image:
    st.markdown('''        <div class="img-preview-box">
            📷 Foto terlampir | <span style="color:#ff6b6b; cursor:pointer; text-decoration:underline;" onclick="document.querySelector('[type=file]').value=''; window.location.reload();">Hapus</span>
        </div>
    ''', unsafe_allow_html=True)

# Tampilkan Riwayat Chat
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# ==========================================
# --- LOGIKA CHAT & AI ---
# ==========================================
if prompt := st.chat_input("Ngobrol moso Djamantara, Bos..."):
    if not client:
        st.error("⚠️ API Key error!"); st.stop()

    st.session_state.messages.append({"role": "user", "content": prompt})
    save_chat("user", prompt)

    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Si Kocheng lagi ngintip..."):
            try:
                img = st.session_state.get("current_image")
                full_response = ""

                if img:
                    # Analisis Gambar + Teks
                    b64 = encode_img(img)
                    resp = client.chat.completions.create(
                        model="llama-3.2-11b-vision-preview",
                        messages=[{
                            "role": "user",
                            "content": [
                                {"type": "text", "text": f"Nama kamu Djamantara. Jawab santai, kocak, bahasa Indonesia campur Madura. Panggil 'Bos'. Analisa gambar ini: {prompt}"},
                                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}}
                            ]
                        }],
                        temperature=0.7,
                        max_tokens=1024
                    )
                    full_response = resp.choices[0].message.content
                else:
                    # Chat Teks Saja
                    ctx = st.session_state.messages[-6:]
                    resp = client.chat.completions.create(
                        model="llama-3.3-70b-versatile",                        messages=[
                            {"role": "system", "content": "Nama kamu Djamantara, asisten kucing hitam keren & kocak. Panggil user 'Bos'. Bahasa santai Indonesia-Madura."}
                        ] + ctx,
                        temperature=0.7,
                        max_tokens=1024
                    )
                    full_response = resp.choices[0].message.content

                # Efek Ngetik
                ph = st.empty()
                txt = ""
                for char in full_response:
                    txt += char
                    ph.markdown(txt + "▌")
                    time.sleep(0.015)
                ph.markdown(full_response)

                # Generate & Putar Suara
                try:
                    asyncio.run(gen_voice(full_response))
                    play_audio("temp_voice.mp3")
                except Exception:
                    pass

                # Simpan ke DB & Session
                st.session_state.messages.append({"role": "assistant", "content": full_response})
                save_chat("assistant", full_response)

                # Reset gambar setelah terkirim
                if st.session_state.current_image:
                    st.session_state.current_image = None
                    st.rerun()

            except Exception as e:
                st.error(f"⚠️ Error: {str(e)}")

# Hapus file sementara
if os.path.exists("temp_voice.mp3"):
    try:
        os.remove("temp_voice.mp3")
    except Exception:
        pass