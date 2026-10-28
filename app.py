import csv
import io
import json
import random
import time
from collections import Counter
from datetime import datetime, timezone
from math import comb

import pandas as pd
import requests
import streamlit as st

st.set_page_config(page_title='LoterIA Pro 4.0 Online', page_icon='🎯', layout='wide')

CONFIG = {
    'Mega-Sena': ('megasena', 1, 60, 6, 6),
    'Lotofácil': ('lotofacil', 1, 25, 15, 15),
    'Quina': ('quina', 1, 80, 5, 5),
    'Dupla-Sena': ('duplasena', 1, 50, 6, 6),
    'Lotomania': ('lotomania', 0, 99, 50, 20),
    '+Milionária': ('maismilionaria', 1, 50, 6, 6),
    'Super Sete': ('supersete', 0, 9, 7, 7),
    'Dia de Sorte': ('diadesorte', 1, 31, 7, 7),
}
MESES = ['Janeiro','Fevereiro','Março','Abril','Maio','Junho','Julho','Agosto','Setembro','Outubro','Novembro','Dezembro']
BASE = 'https://servicebus2.caixa.gov.br/portaldeloterias/api'

@st.cache_data(ttl=900, show_spinner=False)
def obter(modalidade, concurso=None):
    slug = CONFIG[modalidade][0]
    url = f'{BASE}/{slug}' + (f'/{int(concurso)}' if concurso else '')
    response = requests.get(url, timeout=15, headers={'Accept':'application/json','User-Agent':'Mozilla/5.0'})
    response.raise_for_status()
    data = response.json()
    if not isinstance(data, dict) or not isinstance(data.get('numero'), int):
        raise ValueError('Resposta sem número de concurso válido')
    return data

def numeros(data, campo='listaDezenas'):
    raw = data.get(campo) or []
    if not isinstance(raw, list):
        return []
    try:
        return [int(v) for v in raw]
    except (ValueError, TypeError):
        return []

def resultado_validado(mod, d):
    _, ini, fim, _, sorteados = CONFIG[mod]
    a = numeros(d)
    if len(a) != sorteados or any(n < ini or n > fim for n in a):
        return False
    if mod != 'Super Sete' and len(set(a)) != len(a):
        return False
    if mod == 'Dupla-Sena':
        b = numeros(d, 'listaDezenasSegundoSorteio')
        return len(b)==6 and len(set(b))==6 and all(1<=n<=50 for n in b)
    if mod == '+Milionária':
        t = numeros(d, 'trevosSorteados')
        return len(t)==2 and len(set(t))==2 and all(1<=n<=6 for n in t)
    if mod == 'Dia de Sorte':
        return d.get('nomeTimeCoracaoMesSorte') in MESES
    return True

def gerar(mod, metodo, freq=None):
    _, ini, fim, tamanho, _ = CONFIG[mod]
    if mod == 'Super Sete':
        return {'numeros': [random.randrange(10) for _ in range(7)]}
    universo = list(range(ini, fim+1))
    def sortear():
        if metodo == 'Frequência histórica (experimental)' and freq:
            # Amostragem ponderada sem reposição; descritiva, não preditiva.
            pool = universo[:]
            picked = []
            for _ in range(tamanho):
                weights = [1 + freq.get(n,0) for n in pool]
                choice = random.choices(pool, weights=weights, k=1)[0]
                picked.append(choice)
                pool.remove(choice)
            return sorted(picked)
        return sorted(random.sample(universo, tamanho))
    a = sortear()
    if metodo == 'Equilibrado (heurístico)' and mod != 'Lotomania':
        for _ in range(250):
            p = sum(n%2==0 for n in a)
            baixo = sum(n <= (ini+fim)//2 for n in a)
            if abs(2*p-tamanho)<=2 and abs(2*baixo-tamanho)<=2:
                break
            a = sortear()
    result = {'numeros': a}
    if mod == '+Milionária':
        result['trevos'] = sorted(random.sample(range(1,7),2))
    if mod == 'Dia de Sorte':
        result['mes'] = random.choice(MESES)
    return result

def fmt(j, mod):
    ns = j['numeros']
    s = ' | '.join(map(str,ns)) if mod=='Super Sete' else ' '.join(f'{n:02d}' for n in ns)
    if 'trevos' in j: s += ' | Trevos: '+', '.join(map(str,j['trevos']))
    if 'mes' in j: s += ' | Mês: '+j['mes']
    return s

def conferir(j, d, mod):
    a = j['numeros']
    b = numeros(d)
    if mod == 'Super Sete':
        return f"{sum(x==y for x,y in zip(a,b))} colunas" if len(b)==7 else 'Resultado inválido'
    ac = len(set(a)&set(b))
    if mod == 'Dupla-Sena':
        segundo = numeros(d,'listaDezenasSegundoSorteio')
        return f'{ac} no 1º sorteio; {len(set(a)&set(segundo))} no 2º sorteio'
    if mod == '+Milionária':
        return f"{ac} números e {len(set(j['trevos'])&set(numeros(d,'trevosSorteados')))} trevos"
    if mod == 'Dia de Sorte':
        return f"{ac} números; mês {'certo' if j['mes']==d.get('nomeTimeCoracaoMesSorte') else 'errado'}"
    return f'{ac} acertos'

st.title('🎯 LoterIA Pro 4.0 Online')
st.caption('Análise estatística e geração de combinações. Nenhuma estratégia prevê sorteios aleatórios.')
mod = st.selectbox('Modalidade', list(CONFIG))
if 'jogos' not in st.session_state: st.session_state.jogos = {}
if 'historicos' not in st.session_state: st.session_state.historicos = {}

col1,col2 = st.columns([2,1])
with col1:
    st.write('**Consulta de resultados oficiais (serviço Caixa)**')
    consultar = st.button('🔄 Consultar último resultado', type='primary')
with col2:
    st.caption('Cache de consulta: até 15 minutos. Recarregue para nova verificação após esse período.')
if consultar:
    try:
        d = obter(mod)
        if not resultado_validado(mod,d):
            raise ValueError('Resposta recebida, mas os campos da modalidade estão incompletos ou inválidos')
        st.session_state.historicos.setdefault(mod,{})[d['numero']] = d
        st.session_state[f'ultimo_{mod}'] = d
        st.session_state[f'hora_{mod}'] = datetime.now().strftime('%d/%m/%Y %H:%M:%S')
    except Exception as exc:
        st.error(f'Não foi possível confirmar resultado online: {exc}')
ultimo = st.session_state.get(f'ultimo_{mod}')
if ultimo:
    st.success(f"Último concurso confirmado nesta sessão: {ultimo['numero']} — {ultimo.get('dataApuracao','data não informada')} | Consulta: {st.session_state.get(f'hora_{mod}','')}")
    st.write('Resultado:', ' '.join(f'{n:02d}' for n in numeros(ultimo)))
    if mod=='Dupla-Sena': st.write('Segundo sorteio:', numeros(ultimo,'listaDezenasSegundoSorteio'))
    if mod=='+Milionária': st.write('Trevos:', numeros(ultimo,'trevosSorteados'))
    if mod=='Dia de Sorte': st.write('Mês:', ultimo.get('nomeTimeCoracaoMesSorte'))
else:
    st.info('Nenhum resultado confirmado nesta sessão. Clique em Consultar. Não exibimos sincronização fictícia.')

gerador, historico, conferencia = st.tabs(['🎲 Gerador de jogos','📊 Histórico e estatísticas','🔍 Conferência e backtest'])
with historico:
    limite = st.number_input('Quantidade de concursos recentes para carregar',1,300,30,step=10)
    if st.button('Baixar histórico recente desta modalidade'):
        try:
            latest = obter(mod)
            if not resultado_validado(mod,latest): raise ValueError('Último resultado inválido')
            base = latest['numero']
            ok, falhas = 0,0
            progresso = st.progress(0)
            for i,num in enumerate(range(base, max(0,base-int(limite)),-1)):
                try:
                    d = latest if num==base else obter(mod,num)
                    if not resultado_validado(mod,d): raise ValueError('Campos inválidos')
                    st.session_state.historicos.setdefault(mod,{})[num] = d
                    ok+=1
                except Exception:
                    falhas+=1
                progresso.progress((i+1)/min(int(limite),base))
            st.success(f'{ok} concursos validados; {falhas} não carregados.')
        except Exception as exc:
            st.error(f'Falha na consulta: {exc}')
    dados = list(st.session_state.historicos.get(mod,{}).values())
    st.write(f'Concursos válidos armazenados nesta sessão: {len(dados)}')
    if dados:
        dados.sort(key=lambda d:d['numero'])
        linhas=[]
        for d in dados:
            row={'Concurso':d['numero'],'Data':d.get('dataApuracao',''),'Dezenas':' '.join(map(str,numeros(d)))}
            if mod=='Dupla-Sena': row['Segundo sorteio']=' '.join(map(str,numeros(d,'listaDezenasSegundoSorteio')))
            if mod=='+Milionária': row['Trevos']=' '.join(map(str,numeros(d,'trevosSorteados')))
            if mod=='Dia de Sorte': row['Mês']=d.get('nomeTimeCoracaoMesSorte')
            linhas.append(row)
        df=pd.DataFrame(linhas)
        st.dataframe(df, use_container_width=True,hide_index=True)
        st.download_button('Baixar histórico CSV',df.to_csv(index=False).encode('utf-8-sig'),f'historico_{CONFIG[mod][0]}.csv','text/csv')
        if mod=='Super Sete':
            coluna=st.selectbox('Coluna do Super Sete',range(1,8))
            freq=Counter(numeros(d)[coluna-1] for d in dados)
        else:
            freq=Counter(n for d in dados for n in numeros(d))
        st.subheader('Frequência observada (não é previsão)')
        st.bar_chart(pd.Series(dict(sorted(freq.items())),name='Ocorrências'))
        if mod=='Dupla-Sena':
            st.subheader('Segundo sorteio (separado)')
            f2=Counter(n for d in dados for n in numeros(d,'listaDezenasSegundoSorteio'))
            st.bar_chart(pd.Series(dict(sorted(f2.items())),name='Ocorrências'))
        if mod=='+Milionária':
            st.subheader('Frequência dos trevos')
            ft=Counter(n for d in dados for n in numeros(d,'trevosSorteados'))
            st.bar_chart(pd.Series(dict(sorted(ft.items())),name='Ocorrências'))
        if mod=='Dia de Sorte':
            st.subheader('Frequência dos meses')
            fm=Counter(d.get('nomeTimeCoracaoMesSorte') for d in dados)
            st.bar_chart(pd.Series({m:fm[m] for m in MESES},name='Ocorrências'))

with gerador:
    qtd=st.number_input('Quantidade de jogos',1,100,10)
    metodos=['Aleatório uniforme','Equilibrado (heurístico)','Frequência histórica (experimental)']
    if mod=='Super Sete': metodos=['Aleatório uniforme']
    metodo=st.selectbox('Estratégia',metodos)
    espelho=st.checkbox('Criar aposta-espelho para cada jogo (Lotomania)',disabled=mod!='Lotomania')
    if st.button('Gerar combinações'):
        hist=list(st.session_state.historicos.get(mod,{}).values())
        freq=Counter(n for d in hist for n in numeros(d)) if hist else None
        if metodo.startswith('Frequência') and not freq:
            st.warning('Sem histórico validado. Usando sorteio uniforme.')
        jogos=[]
        vistos=set()
        for _ in range(int(qtd)):
            for tentativa in range(100):
                j=gerar(mod,metodo,freq)
                chave=json.dumps(j,sort_keys=True,ensure_ascii=False)
                if chave not in vistos: break
            if chave in vistos: break
            vistos.add(chave)
            jogos.append(j)
            if mod=='Lotomania' and espelho:
                jogos.append({'numeros':sorted(set(range(100))-set(j['numeros']))})
        st.session_state.jogos[mod]=jogos
    jogos=st.session_state.jogos.get(mod,[])
    if jogos:
        linhas=[f'{i:02d}: {fmt(j,mod)}' for i,j in enumerate(jogos,1)]
        st.code('\n'.join(linhas),language='text')
        st.download_button('Baixar jogos TXT','\n'.join(linhas).encode('utf-8'),f'jogos_{CONFIG[mod][0]}.txt')

with conferencia:
    jogos=st.session_state.jogos.get(mod,[])
    dados=list(st.session_state.historicos.get(mod,{}).values())
    if not jogos: st.info('Gere jogos na primeira aba.')
    if not dados: st.info('Consulte ou baixe resultados antes de conferir.')
    if jogos and dados:
        numeros_concursos=sorted((d['numero'] for d in dados),reverse=True)
        escolhido=st.selectbox('Concurso para conferência',numeros_concursos)
        d=st.session_state.historicos[mod][escolhido]
        st.dataframe(pd.DataFrame([{'Jogo':i,'Combinação':fmt(j,mod),'Resultado':conferir(j,d,mod)} for i,j in enumerate(jogos,1)]),hide_index=True,use_container_width=True)
        st.subheader('Backtest descritivo')
        st.caption('Compara jogos fixos com concursos passados. Não é treinamento de IA nem previsão. Não calcula retorno financeiro.')
        if st.button('Conferir jogos contra todos os concursos carregados'):
            rows=[{'Concurso':d['numero'],'Jogo':i,'Acertos':conferir(j,d,mod)} for d in dados for i,j in enumerate(jogos,1)]
            st.dataframe(pd.DataFrame(rows),use_container_width=True,hide_index=True)

st.divider()
st.caption('Fonte de resultados: endpoint público da Caixa, sujeito a indisponibilidade. Dados em memória de sessão; exporte CSV para guardar o histórico. Uso responsável: não há previsão garantida.')
