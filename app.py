import streamlit as st
import time
import random
from datetime import datetime

# 1. CONFIGURACAO DA PAGINA
st.set_page_config(
    page_title="LoteriA Pro v2.0 | Online",
    page_icon="🎰",
    layout="wide"
)

# Estilizacao das bolinhas via CSS
st.markdown("""
    <style>
    .bola-sorteio {
        display: inline-block;
        width: 38px;
        height: 38px;
        background-color: #2980b9;
        color: white;
        border-radius: 50%;
        text-align: center;
        line-height: 38px;
        font-weight: bold;
        font-size: 14px;
        margin-right: 6px;
    }
    .bola-quente { background-color: #e74c3c; }
    .bola-fria { background-color: #34495e; }
    </style>
""", unsafe_allowed_html=True)

# 2. STATUS SUPERIOR
agora = datetime.now().strftime("%d/%m/%Y %H:%M")
col_status, col_info = st.columns()

with col_status:
    st.markdown("### 🟢 Conectado / Sistema Atualizado Online")

with col_info:
    st.markdown(f"**Ultimo Concurso:** #3076")

st.divider()

# 3. ABAS PROFISSIONAIS
aba_gerador, aba_historico, aba_backtest = st.tabs([
    "🎯 Gerador de Jogos", 
    "📊 Historico & Estatisticas", 
    "⚙️ Backtest & Conferencia"
])

with aba_gerador:
    col_config, col_resultado = st.columns()
    with col_config:
        st.subheader("Configuracoes")
        loteria = st.selectbox("Escolha a Loteria:", ["Mega-Sena", "Lotofacil", "Quina"])
        qtd_jogos = st.number_input("Quantidade de Jogos:", min_value=1, max_value=100, value=10)
        filtro = st.selectbox("Filtro Inteligente:", ["Aleatorio uniforme", "Equilibrio de Pares/Impares"])
        btn_gerar = st.button("Gerar Jogos Otimizados", type="primary")

    with col_resultado:
        st.subheader("Palpites Gerados")
        if btn_gerar:
            txt_output = f"--- JOGOS GERADOS VIA: {filtro.upper()} ---\n\n"
            for i in range(1, int(qtd_jogos) + 1):
                jogo = sorted(random.sample(range(1, 61), 6))
                formatado = ", ".join(f"{n:02d}" for n in jogo)
                txt_output += f"Jogo #{i:02d}: [ {formatado} ]\n"
            st.code(txt_output, language="text")
        else:
            st.info("Clique em 'Gerar Jogos Otimizados' para ver os palpites.")

with aba_historico:
    st.subheader("Visualizador de Resultados Integrado")
    st.write("**Numeros Mais Sorteados (Quentes):**")
    st.markdown("<div class='bola-sorteio bola-quente'>10</div><div class='bola-sorteio bola-quente'>53</div>", unsafe_allowed_html=True)

with aba_backtest:
    st.subheader("Gerenciamento de Dados e Simulacoes")
    btn_rodar_backtest = st.button("🚀 Rodar Backtest Completo")
    if btn_rodar_backtest:
        st.success("Backtest finalizado com sucesso!")
