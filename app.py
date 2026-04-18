import streamlit as st
from groq import Groq

# --- KONFIGURASI API ---
GROQ_API_KEY = "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"

st.set_page_config(page_title="Djamantara AI", page_icon="🐱", layout="centered")

# Inisialisasi Klien Groq
try:
    client = Groq(api_key=GROQ_API_KEY)
except Exception as e:
    st.error(f"⚠️ API Groq error: {e}")
    st.stop()

# Setup Session State untuk Chat History
if "messages" not in st.session_state:
    st.session_state.messages = []

# --- TAMPILAN UTAMA ---
st.title("🤖 Djamantara AI")
st.markdown("Halo Bos! Ngobrol santai aja. Djamantara siap bantu.")

# Tampilkan Chat History
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# --- LOGIKA CHAT ---
if prompt := st.chat_input("Ketik pesan..."):
    # 1. Simpan & tampilkan pesan user
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # 2. Panggil AI & tampilkan respons
    with st.chat_message("assistant"):
        with st.spinner("Djamantara sedang mengetik..."):
            try:
                # Ambil 5 pesan terakhir sebagai konteks
                context = st.session_state.messages[-5:]
                system_prompt = {
                    "role": "system", 
                    "content": "Nama kamu Djamantara. Jawab santai, kocak, bahasa Indonesia campur Madura sedikit. Panggil user 'Bos'. Jangan terlalu panjang."
                }

                response = client.chat.completions.create(
                    messages=[system_prompt] + context,
                    model="llama-3.3-70b-versatile",
                    temperature=0.7
                )

                full_response = response.choices[0].message.content
                st.markdown(full_response)

                # Simpan respons AI ke history
                st.session_state.messages.append({"role": "assistant", "content": full_response})

            except Exception as e:
                st.error(f"Duh Bos, sistem macet: {e}")