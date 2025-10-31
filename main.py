import streamlit as st

st.set_page_config(page_title="Teste Header", page_icon="🧩")

# CSS para remover o cabeçalho
st.markdown("""
<style>
header[data-testid="stHeader"] {
    display: none;
}
</style>
""", unsafe_allow_html=True)

st.title("🧩 Teste — Cabeçalho oculto")
st.write("O cabeçalho original do Streamlit foi removido com CSS.")
