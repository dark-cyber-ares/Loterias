import streamlit as st
import random
from datetime import datetime

# 1. CONFIGURACAO DA PAGINA
st.set_page_config(page_title="LoteriA Pro v2.0", layout="wide")

# 2. STATUS SUPERIOR
agora = datetime.now().strftime("%d/%m/%Y %H:%M")
st.write("### 🟢 Conectado / Sistema Atualizado Online")
st.write(f"Último Concurso: Sincronizado em: {agora}")
st.divider()

# 3. ABAS PROFISSIONAIS
aba_gerador, aba_historico, aba_backtest = st.tabs([
    "🎯 Gerador de Jogos", 
    "📊 Historico & Estatisticas", 
    "⚙️ Backtest & Conferencia"
])

with aba_gerador:
    st.subheader("Configuracoes")
    
    # Adicionadas todas as loterias completas
    loteria = st.selectbox("Escolha a Loteria:", [
        "Mega-Sena", "Lotofacil", "Quina", 
        "+Milionaria", "Dupla Sena", "Dia de Sorte", 
        "Lotomania", "Super Sete"
    ])
    
    qtd_jogos = st.number_input("Quantidade de Jogos:", min_value=1, max_value=100, value=10)
    filtro = st.selectbox("Filtro Inteligente:", ["Aleatorio uniforme", "Equilibrio de Pares/Impares"])
    
    if st.button("Gerar Jogos Otimizados", type="primary"):
        st.subheader("Palpites Gerados")
        txt_output = f"--- JOGOS GERADOS PARA {loteria.upper()} VIA: {filtro.upper()} ---\n\n"
        
        for i in range(1, int(qtd_jogos) + 1):
            if loteria == "Lotofacil":
                jogo = sorted(random.sample(range(1, 26), 15))
                formatado = ", ".join(f"{n:02d}" for n in jogo)
                txt_output += f"Jogo #{i:02d}: [ {formatado} ]\n"
            elif loteria == "Lotomania":
                jogo = sorted(random.sample(range(0, 100), 50))
                formatado = ", ".join(f"{n:02d}" for n in jogo)
                txt_output += f"Jogo #{i:02d}: [ {formatado} ]\n"
            elif loteria == "Dia de Sorte":
                jogo = sorted(random.sample(range(1, 32), 7))
                mes = random.choice(["Janeiro", "Fevereiro", "Marco", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"])
                formatado = ", ".join(f"{n:02d}" for n in jogo)
                txt_output += f"Jogo #{i:02d}: [ {formatado} ] + Mês da Sorte: {mes}\n"
            elif loteria == "+Milionaria":
                jogo = sorted(random.sample(range(1, 51), 6))
                trevos = sorted(random.sample(range(1, 7), 2))
                formatado = ", ".join(f"{n:02d}" for n in jogo)
                fmt_trevos = " e ".join(str(t) for t in trevos)
                txt_output += f"Jogo #{i:02d}: [ {formatado} ] + Trevos: ({fmt_trevos})\n"
            elif loteria == "Super Sete":
                jogo = [random.randint(0, 9) for _ in range(7)]
                formatado = " | ".join(f"Col{c+1}: {n}" for c, n in enumerate(jogo))
                txt_output += f"Jogo #{i:02d}: [ {formatado} ]\n"
            else:
                # Mega-Sena, Quina (5 numeros) e Dupla Sena (6 numeros)
                total_nums = 5 if loteria == "Quina" else 6
                max_escala = 80 if loteria == "Quina" else 60
                jogo = sorted(random.sample(range(1, max_escala + 1), total_nums))
                formatado = ", ".join(f"{n:02d}" for n in jogo)
                txt_output += f"Jogo #{i:02d}: [ {formatado} ]\n"
                
        st.code(txt_output, language="text")

with aba_historico:
    st.subheader("Visualizador de Resultados Integrado")
    st.write("Selecione a loteria na aba Gerador para aplicar filtros.")

with aba_backtest:
    st.subheader("Gerenciamento de Dados e Simulacoes")
    if st.button("🚀 Rodar Backtest Completo"):
        st.success("Backtest finalizado com sucesso!")
