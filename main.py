import streamlit as st

st.set_page_config(page_title="Teste Footer", page_icon="🧩")

st.markdown("""
<style>
/* Oculta o nome do usuário criador do app no Streamlit Cloud */
div[data-testid="stDecoration"] > div:first-child {
    display: none !important;
}

/* Mantém "Hosted with Streamlit" visível */
div[data-testid="stDecoration"] > div:last-child {
    display: block !important;
}
</style>
""", unsafe_allow_html=True)

st.title("🧩 Teste — Ocultando apenas usuário")
st.write("O nome do usuário criador foi ocultado, mas 'Hosted with Streamlit' continua visível.")
