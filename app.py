"""LoterIA Pro 4.2 — análise descritiva; não prevê resultados."""
import json
import random
import re
from collections import Counter
from datetime import datetime, date
from math import comb

import pandas as pd
import requests
import streamlit as st
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

st.set_page_config(page_title='LoterIA Pro 4.2', page_icon='🎯', layout='wide')
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
MESES = ['Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho', 'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro']
CAIXA = 'https://servicebus2.caixa.gov.br/portaldeloterias/api'
GUIDI = 'https://api.guidi.dev.br/loteria'
HEROKU = 'https://loteriascaixa-api.herokuapp.com/api'
VALORFINAL_SUPERSETE = 'https://valorfinal.com.br/data/supersete-historico.json'


@st.cache_resource
def sessao_http():
    s = requests.Session()
    retry = Retry(total=2, connect=2, read=1, backoff_factor=0.5,
                  status_forcelist=[429, 500, 502, 503, 504], allowed_methods=['GET'])
    s.mount('https://', HTTPAdapter(max_retries=retry))
    s.headers.update({'Accept': 'application/json', 'User-Agent': 'Mozilla/5.0 LoterIA-Pro/4.2'})
    return s


def inteiros(valores):
    if not isinstance(valores, list):
        return []
    try:
        if any(isinstance(v, bool) or not re.fullmatch(r'\d{1,3}', str(v).strip()) for v in valores):
            return []
        return [int(v) for v in valores]
    except (ValueError, TypeError):
        return []


def numeros(d, campo='listaDezenas'):
    return inteiros(d.get(campo, []))


def normalizar_alternativa(mod, bruto):
    """Aceita apenas formatos explicitamente reconhecidos; nunca adivinha colunas."""
    if not isinstance(bruto, dict):
        raise ValueError('Formato alternativo não reconhecido')
    numero = bruto.get('numero', bruto.get('concurso'))
    if isinstance(numero, bool) or not str(numero).isdigit():
        raise ValueError('Concurso ausente na fonte alternativa')
    data = bruto.get('dataApuracao', bruto.get('data'))
    if not isinstance(data, str):
        raise ValueError('Data ausente na fonte alternativa')
    lista = bruto.get('listaDezenas', bruto.get('dezenas'))
    # Super Sete precisa preservar a ordem C1 ... C7. Sem contrato de ordem, rejeita.
    if mod == 'Super Sete':
        colunas = bruto.get('colunas')
        if isinstance(colunas, list) and len(colunas) == 7:
            if all(isinstance(c, dict) and ('dezena' in c or 'numero' in c) for c in colunas):
                lista = [c.get('dezena', c.get('numero')) for c in colunas]
            else:
                lista = colunas
        elif 'listaDezenas' not in bruto and 'dezenasOrdemSorteio' in bruto:
            lista = bruto['dezenasOrdemSorteio']
        elif 'listaDezenas' not in bruto:
            raise ValueError('Ordem das 7 colunas não confirmada na fonte alternativa')
    d = {'numero': int(numero), 'dataApuracao': data, 'listaDezenas': lista}
    if mod == 'Dupla-Sena':
        d['listaDezenasSegundoSorteio'] = bruto.get('listaDezenasSegundoSorteio', bruto.get('dezenasSegundoSorteio'))
    if mod == '+Milionária':
        d['trevosSorteados'] = bruto.get('trevosSorteados', bruto.get('trevos'))
    if mod == 'Dia de Sorte':
        d['nomeTimeCoracaoMesSorte'] = bruto.get('nomeTimeCoracaoMesSorte', bruto.get('mesSorte'))
    return d


def resultado_validado(mod, d, concurso=None):
    if not isinstance(d, dict):
        return False
    n = d.get('numero')
    if type(n) is not int or n < 1 or (concurso is not None and n != concurso):
        return False
    data = d.get('dataApuracao')
    try:
        dia = datetime.strptime(data, '%d/%m/%Y').date()
        if dia > date.today():
            return False
    except (TypeError, ValueError):
        return False
    _, ini, fim, _, sorteados = CONFIG[mod]
    a = numeros(d)
    if len(a) != sorteados or any(x < ini or x > fim for x in a):
        return False
    if mod != 'Super Sete' and len(set(a)) != len(a):
        return False
    if mod == 'Dupla-Sena':
        b = numeros(d, 'listaDezenasSegundoSorteio')
        if len(b) != 6 or len(set(b)) != 6 or any(not 1 <= x <= 50 for x in b):
            return False
    if mod == '+Milionária':
        t = numeros(d, 'trevosSorteados')
        if len(t) != 2 or len(set(t)) != 2 or any(not 1 <= x <= 6 for x in t):
            return False
    if mod == 'Dia de Sorte' and d.get('nomeTimeCoracaoMesSorte') not in MESES:
        return False
    return True


def buscar_fonte(url):
    r = sessao_http().get(url, timeout=(5, 15))
    r.raise_for_status()
    return r.json()


def diagnostico_erro(exc):
    """Expõe informações úteis sem incluir URLs ou conteúdos completos de respostas."""
    if isinstance(exc, RuntimeError):
        return str(exc)[:240]
    if isinstance(exc, requests.HTTPError) and exc.response is not None:
        return f'HTTP {exc.response.status_code}'
    if isinstance(exc, requests.exceptions.RetryError):
        causa = str(exc)
        match = re.search(r'(?:status|ResponseError).*?(\d{3})', causa, re.IGNORECASE)
        return f'RetryError (HTTP {match.group(1)})' if match else 'RetryError (tentativas esgotadas)'
    if isinstance(exc, requests.exceptions.Timeout):
        return 'Tempo limite de conexão/resposta'
    if isinstance(exc, requests.exceptions.ConnectionError):
        return 'Falha de conexão'
    if isinstance(exc, requests.exceptions.JSONDecodeError):
        return 'Resposta não é JSON válido'
    if isinstance(exc, ValueError):
        return f'Validação: {str(exc)[:110]}'
    return type(exc).__name__


def buscar_super_sete(url):
    """Tenta uma sessão HTTP independente após falha da sessão padrão.

    Não ignora HTTP, não altera dados e não contorna restrições do servidor.
    """
    try:
        return buscar_fonte(url)
    except (requests.RequestException, ValueError) as primeira:
        # Nova sessão sem o cache de conexões/retries anterior; apenas uma tentativa.
        try:
            with requests.Session() as s:
                s.headers.update({'Accept': 'application/json',
                                  'User-Agent': 'LoterIA-Pro/4.2.4 (consulta publica)'})
                r = s.get(url, timeout=(5, 15), headers={'Cache-Control': 'no-cache'})
                r.raise_for_status()
                return r.json()
        except (requests.RequestException, ValueError) as segunda:
            raise RuntimeError(f'{diagnostico_erro(primeira)}; segunda tentativa: {diagnostico_erro(segunda)}') from segunda


@st.cache_data(ttl=900, show_spinner=False)
def historico_valorfinal_supersete():
    """Lê e valida o histórico da fonte independente; não presume que esteja atualizado."""
    bruto = buscar_fonte(VALORFINAL_SUPERSETE)
    if not isinstance(bruto, dict) or bruto.get('modalidade') != 'supersete':
        raise ValueError('modalidade Super Sete não confirmada no ValorFinal')
    registros = bruto.get('concursos')
    ultimo = bruto.get('ultimoConcurso')
    if (not isinstance(registros, list) or not registros or
            type(ultimo) is not int or ultimo < 1):
        raise ValueError('histórico ou último concurso inválido no ValorFinal')
    encontrados = {}
    for registro in registros:
        if not isinstance(registro, list) or len(registro) != 3:
            raise ValueError('registro de concurso com formato inesperado no ValorFinal')
        numero, data_iso, colunas = registro
        if type(numero) is not int or numero < 1 or numero in encontrados:
            raise ValueError('número de concurso inválido ou duplicado no ValorFinal')
        if not isinstance(data_iso, str):
            raise ValueError('data de concurso inválida no ValorFinal')
        try:
            data_obj = datetime.strptime(data_iso, '%Y-%m-%d').date()
        except ValueError as exc:
            raise ValueError('data de concurso fora do formato ISO no ValorFinal') from exc
        if not isinstance(colunas, list) or len(colunas) != 7 or any(
                type(digito) is not int or not 0 <= digito <= 9 for digito in colunas):
            raise ValueError('sete colunas inválidas no ValorFinal')
        dado = {'numero': numero, 'dataApuracao': data_obj.strftime('%d/%m/%Y'),
                'listaDezenas': list(colunas)}
        if not resultado_validado('Super Sete', dado):
            raise ValueError('resultado não validado no ValorFinal')
        encontrados[numero] = dado
    if max(encontrados) != ultimo or len(encontrados) != len(registros):
        raise ValueError('metadados de concursos inconsistentes no ValorFinal')
    return encontrados, ultimo


def obter_valorfinal_supersete(concurso=None):
    registros, ultimo = historico_valorfinal_supersete()
    escolhido = ultimo if concurso is None else concurso
    if escolhido not in registros:
        raise ValueError(f'concurso {escolhido} não disponível no histórico ValorFinal (até {ultimo})')
    dado = dict(registros[escolhido])
    if not resultado_validado('Super Sete', dado, concurso):
        raise ValueError('concurso inválido na fonte ValorFinal')
    return {'dados': dado, 'fonte': 'ValorFinal (histórico independente; não oficial)',
            'url': VALORFINAL_SUPERSETE}


@st.cache_data(ttl=900, show_spinner=False)
def obter(mod, concurso=None, permitir_alternativa=True):
    slug = CONFIG[mod][0]
    erros = []
    url = f'{CAIXA}/{slug}' + (f'/{concurso}' if concurso is not None else '')
    try:
        d = (buscar_super_sete(url) if mod == 'Super Sete' else buscar_fonte(url))
        if not resultado_validado(mod, d, concurso):
            raise ValueError('dados oficiais incompletos ou inválidos')
        return {'dados': d, 'fonte': 'CAIXA (serviço oficial)', 'url': url}
    except (requests.RequestException, ValueError, TypeError, RuntimeError) as e:
        erros.append(f'CAIXA: {diagnostico_erro(e)}' if mod == 'Super Sete' else f'CAIXA: {type(e).__name__}')
    # Para Super Sete, consultar o histórico ValorFinal antes da Guidi,
    # pois a resposta "ultimo" da Guidi pode estar atrasada.
    if permitir_alternativa and mod == 'Super Sete':
        try:
            return obter_valorfinal_supersete(concurso)
        except (requests.RequestException, ValueError, TypeError, RuntimeError) as e:
            erros.append(f'ValorFinal: {diagnostico_erro(e)}')
    if permitir_alternativa:
        url_alt = f'{GUIDI}/{slug}/' + (str(concurso) if concurso is not None else 'ultimo')
        try:
            d = normalizar_alternativa(mod, buscar_super_sete(url_alt) if mod == 'Super Sete' else buscar_fonte(url_alt))
            if not resultado_validado(mod, d, concurso):
                raise ValueError('dados alternativos incompletos ou inválidos')
            return {'dados': d, 'fonte': 'API Guidi (terceiro; não oficial)', 'url': url_alt}
        except (requests.RequestException, ValueError, TypeError, RuntimeError) as e:
            erros.append(f'Guidi: {diagnostico_erro(e)}' if mod == 'Super Sete' else f'Guidi: {type(e).__name__}')
    # Terceira fonte verificada manualmente para Super Sete (serviço não oficial).
    # A resposta fornece dezenasOrdemSorteio, que preserva C1...C7.
    if permitir_alternativa and mod == 'Super Sete':
        url_terceira = f'{HEROKU}/{slug}' + (f'/{concurso}' if concurso is not None else '')
        try:
            bruto = buscar_super_sete(url_terceira)
            if not isinstance(bruto, dict) or bruto.get('loteria') != slug:
                raise ValueError('modalidade não confirmada na terceira fonte')
            if not isinstance(bruto.get('dezenasOrdemSorteio'), list):
                raise ValueError('ordem das colunas ausente na terceira fonte')
            d = normalizar_alternativa(mod, bruto)
            if not resultado_validado(mod, d, concurso):
                raise ValueError('dados da terceira fonte incompletos ou inválidos')
            return {'dados': d, 'fonte': 'API LoteriasCaixa Heroku (terceiro; não oficial)', 'url': url_terceira}
        except (requests.RequestException, ValueError, TypeError, RuntimeError) as e:
            erros.append(f'Terceira API: {diagnostico_erro(e)}')
    raise RuntimeError('; '.join(erros) + '. Nenhum resultado foi confirmado.')


def gerar(mod, metodo, freq=None, por_coluna=None):
    _, ini, fim, tamanho, _ = CONFIG[mod]
    if mod == 'Super Sete':
        ns = []
        for i in range(7):
            f = (por_coluna or {}).get(i, {})
            ns.append(random.choices(range(10), weights=[1 + f.get(v, 0) for v in range(10)])[0]
                      if metodo.startswith('Frequência') and f else random.randrange(10))
        return {'numeros': ns}
    universo = list(range(ini, fim + 1))
    def sortear():
        if metodo.startswith('Frequência') and freq:
            pool, picked = universo[:], []
            for _ in range(tamanho):
                escolhido = random.choices(pool, weights=[1 + freq.get(n, 0) for n in pool])[0]
                picked.append(escolhido)
                pool.remove(escolhido)
            return sorted(picked)
        return sorted(random.sample(universo, tamanho))
    a = sortear()
    if metodo.startswith('Equilibrado') and mod != 'Lotomania':
        for _ in range(250):
            pares = sum(n % 2 == 0 for n in a)
            baixos = sum(n <= (ini + fim) // 2 for n in a)
            if abs(2 * pares - tamanho) <= 2 and abs(2 * baixos - tamanho) <= 2:
                break
            a = sortear()
    jogo = {'numeros': a}
    if mod == '+Milionária':
        jogo['trevos'] = sorted(random.sample(range(1, 7), 2))
    if mod == 'Dia de Sorte':
        jogo['mes'] = random.choice(MESES)
    return jogo


def formatar(j, mod):
    s = ' | '.join(map(str, j['numeros'])) if mod == 'Super Sete' else ' '.join(f'{n:02d}' for n in j['numeros'])
    if 'trevos' in j:
        s += ' | Trevos: ' + ', '.join(map(str, j['trevos']))
    if 'mes' in j:
        s += ' | Mês: ' + j['mes']
    return s


def acertos(j, d, mod):
    a, b = j['numeros'], numeros(d)
    if mod == 'Super Sete':
        return {'Colunas': sum(x == y for x, y in zip(a, b))}
    n = len(set(a) & set(b))
    if mod == 'Dupla-Sena':
        return {'1º sorteio': n, '2º sorteio': len(set(a) & set(numeros(d, 'listaDezenasSegundoSorteio')))}
    if mod == '+Milionária':
        return {'Dezenas': n, 'Trevos': len(set(j['trevos']) & set(numeros(d, 'trevosSorteados')))}
    if mod == 'Dia de Sorte':
        return {'Dezenas': n, 'Mês correto': j['mes'] == d.get('nomeTimeCoracaoMesSorte')}
    return {'Acertos': n}


def csv_bytes(df):
    return df.to_csv(index=False).encode('utf-8-sig')


def linha_historico(d, mod):
    linha = {'Concurso': d['numero'], 'Data': d['dataApuracao'],
             'Dezenas': ' | '.join(map(str, numeros(d))) if mod == 'Super Sete' else ' '.join(f'{x:02d}' for x in numeros(d)),
             'Fonte': d.get('_fonte', 'Importação sem fonte identificada')}
    if mod == 'Dupla-Sena':
        linha['Segundo sorteio'] = ' '.join(map(str, numeros(d, 'listaDezenasSegundoSorteio')))
    if mod == '+Milionária':
        linha['Trevos'] = ' '.join(map(str, numeros(d, 'trevosSorteados')))
    if mod == 'Dia de Sorte':
        linha['Mês'] = d['nomeTimeCoracaoMesSorte']
    return linha


st.title('🎯 LoterIA Pro 4.2.6 — prioridade ValorFinal Super Sete (teste local)')
st.caption('Estatísticas descritivas e geração de combinações. Nenhuma estratégia prevê sorteios ou aumenta comprovadamente as chances.')
mod = st.selectbox('Modalidade', list(CONFIG))
if 'historicos' not in st.session_state:
    st.session_state.historicos = {}
if 'jogos' not in st.session_state:
    st.session_state.jogos = {}
if 'falhas' not in st.session_state:
    st.session_state.falhas = {}
if 'atualizacao_automatica' not in st.session_state:
    st.session_state.atualizacao_automatica = {}
if 'auto_inicial_executada' not in st.session_state:
    st.session_state.auto_inicial_executada = False


def atualizar_todas_modalidades(permitir_alternativa=True):
    """Consulta as oito modalidades e completa lacunas recentes sem apagar históricos."""
    instante = datetime.now().astimezone().strftime('%d/%m/%Y %H:%M:%S %Z')
    resumo = {}
    for modalidade in CONFIG:
        existentes = st.session_state.historicos.setdefault(modalidade, {})
        novos = 0
        falhas = []
        try:
            ret = obter(modalidade, permitir_alternativa=permitir_alternativa)
            mais_recente = ret['dados']['numero']
            # Se já houver histórico, tenta preencher até 30 concursos recentes.
            # Em uma sessão nova, consulta apenas o último, evitando 240 requisições.
            anterior = max(existentes) if existentes else None
            candidatos = [mais_recente]
            if anterior is not None and mais_recente > anterior:
                inicio = max(anterior + 1, mais_recente - 29)
                candidatos = list(range(inicio, mais_recente + 1))
            for numero in candidatos:
                if numero in existentes:
                    continue
                try:
                    resultado = ret if numero == mais_recente else obter(modalidade, numero, permitir_alternativa)
                    dado = dict(resultado['dados'])
                    dado['_fonte'] = resultado['fonte']
                    existentes[numero] = dado
                    novos += 1
                except (RuntimeError, requests.RequestException, ValueError) as exc:
                    falhas.append(f'{numero}: {exc}')
            dado_atual = dict(ret['dados'])
            dado_atual['_fonte'] = ret['fonte']
            st.session_state[f'ultimo_{modalidade}'] = existentes.get(mais_recente, dado_atual)
            st.session_state[f'hora_{modalidade}'] = instante
            resumo[modalidade] = {'horario': instante, 'ultimo': mais_recente,
                                  'novos': novos, 'falhas': falhas,
                                  'fonte': ret['fonte']}
        except (RuntimeError, requests.RequestException, ValueError) as exc:
            resumo[modalidade] = {'horario': instante, 'ultimo': None, 'novos': 0,
                                  'falhas': [str(exc)], 'fonte': 'indisponível'}
    st.session_state.atualizacao_automatica = resumo


# Uma execução por sessão: evita consultas repetidas a cada interação no Streamlit.
if not st.session_state.auto_inicial_executada:
    st.session_state.auto_inicial_executada = True
    with st.spinner('Consultando os últimos sorteios das oito modalidades...'):
        atualizar_todas_modalidades(permitir_alternativa=True)

with st.expander('🔄 Atualização automática dos sorteios — oito modalidades', expanded=True):
    st.caption('Consulta automática uma vez ao abrir esta sessão. Para consultar novamente, use o botão abaixo. Não funciona em segundo plano com o aplicativo fechado.')
    if st.button('🔄 Verificar novos sorteios nas oito modalidades'):
        with st.spinner('Verificando novos concursos...'):
            atualizar_todas_modalidades(permitir_alternativa=True)
    linhas_status = []
    for modalidade in CONFIG:
        status = st.session_state.atualizacao_automatica.get(modalidade, {})
        falhas_status = status.get('falhas', [])
        linhas_status.append({'Modalidade': modalidade,
                              'Último concurso consultado': status.get('ultimo') or '—',
                              'Novos importados': status.get('novos', 0),
                              'Atualização': status.get('horario', '—'),
                              'Situação': 'Falha: ' + '; '.join(falhas_status[:2]) if falhas_status else 'OK',
                              'Fonte': status.get('fonte', '—')})
    st.dataframe(pd.DataFrame(linhas_status), hide_index=True, use_container_width=True)
    st.info('Históricos são mantidos na sessão. Para preservar entre sessões ou reinícios, baixe o backup JSON.')

with st.expander('💾 Salvar ou restaurar histórico (backup portátil)', expanded=False):
    st.caption('O backup contém somente os concursos que estão na memória desta sessão. Confira os totais antes de baixar.')
    if 'backup_import_msg' in st.session_state:
        st.success(st.session_state.pop('backup_import_msg'))
    resumo_backup = {m: len(v) for m, v in st.session_state.historicos.items() if v}
    total_backup = sum(resumo_backup.values())
    st.write(f'**Concursos que entrarão no backup: {total_backup}**')
    if resumo_backup:
        st.dataframe(pd.DataFrame([{'Modalidade': m, 'Concursos': n} for m, n in sorted(resumo_backup.items())]),
                     hide_index=True, use_container_width=True)
    else:
        st.warning('Nenhum histórico carregado. Importe seu backup anterior ou carregue os concursos antes de baixar.')
    backup = {'formato': 'LoterIA-Pro-4.2',
              'historicos': {m: list(v.values()) for m, v in st.session_state.historicos.items() if v}}
    st.download_button('Baixar backup JSON de todas as modalidades',
                       json.dumps(backup, ensure_ascii=False, indent=2).encode('utf-8'),
                       'loteria_backup.json', 'application/json', disabled=total_backup == 0)
    st.caption('Atenção: o arquivo novo não recupera históricos de sessões anteriores que já foram perdidos.')
    enviado = st.file_uploader('Restaurar backup JSON', type=['json'])
    if enviado is not None and st.button('Validar e importar backup'):
        try:
            payload = json.load(enviado)
            if not isinstance(payload, dict) or payload.get('formato') != 'LoterIA-Pro-4.2' or not isinstance(payload.get('historicos'), dict):
                raise ValueError('Arquivo de backup incompatível')
            validos, rejeitados = 0, 0
            for modalidade, registros in payload['historicos'].items():
                if modalidade not in CONFIG or not isinstance(registros, list):
                    rejeitados += 1
                    continue
                for d in registros[:20000]:
                    if resultado_validado(modalidade, d):
                        st.session_state.historicos.setdefault(modalidade, {})[d['numero']] = d
                        validos += 1
                    else:
                        rejeitados += 1
            st.session_state.backup_import_msg = f'{validos} registros importados; {rejeitados} rejeitados. Confira o resumo atualizado abaixo.'
            st.rerun()
        except (ValueError, TypeError, json.JSONDecodeError, AttributeError) as e:
            st.error(f'Backup inválido: {e}')

c1, c2 = st.columns([2, 1])
with c1:
    st.write('**Consultar resultado — Caixa primeiro; fonte independente opcional em caso de falha**')
    consultar = st.button('🔄 Consultar último resultado', type='primary')
with c2:
    alternativa = st.checkbox('Permitir fontes alternativas (Guidi, Heroku e ValorFinal para Super Sete)', value=True,
                               help='Fonte de terceiros. Pode ter atraso, limites de acesso ou estar indisponível fora do Brasil.')
    st.caption('Cache de rede: até 15 minutos. A consulta automática acontece na abertura da sessão; o botão acima permite verificar novamente.')
if consultar:
    try:
        retorno = obter(mod, permitir_alternativa=alternativa)
        d = dict(retorno['dados'])
        d['_fonte'] = retorno['fonte']
        st.session_state.historicos.setdefault(mod, {})[d['numero']] = d
        st.session_state[f'ultimo_{mod}'] = d
        st.session_state[f'hora_{mod}'] = datetime.now().astimezone().strftime('%d/%m/%Y %H:%M:%S')
    except RuntimeError as e:
        st.error(f'Consulta não concluída: {e}')
        st.info('Nenhum novo resultado foi confirmado. O gerador aleatório continua disponível.')
ultimo = st.session_state.get(f'ultimo_{mod}')
if ultimo:
    st.success(f"Concurso {ultimo['numero']} — {ultimo['dataApuracao']} | Fonte: {ultimo.get('_fonte', 'não identificada')} | Consultado: {st.session_state.get(f'hora_{mod}', '')}")
    atraso = (date.today() - datetime.strptime(ultimo['dataApuracao'], '%d/%m/%Y').date()).days
    if atraso > 7:
        st.warning(f'Atenção: o resultado recebido tem {atraso} dias. Pode estar desatualizado; confirme o concurso mais recente em fonte oficial.')
    if mod == 'Dupla-Sena':
        st.markdown('**1º sorteio**')
        st.write(' '.join(f'{x:02d}' for x in numeros(ultimo)))
        st.markdown('**2º sorteio**')
        st.write(' '.join(f'{x:02d}' for x in numeros(ultimo, 'listaDezenasSegundoSorteio')))
    else:
        st.write('Resultado:', ' | '.join(map(str, numeros(ultimo))) if mod == 'Super Sete' else ' '.join(f'{x:02d}' for x in numeros(ultimo)))
    if mod == '+Milionária':
        st.markdown('**🍀 Trevos sorteados**')
        st.write('🍀 ' + '   🍀 '.join(str(x) for x in numeros(ultimo, 'trevosSorteados')))
    if mod == 'Dia de Sorte':
        st.write('Mês:', ultimo['nomeTimeCoracaoMesSorte'])
else:
    st.info('Nenhum resultado confirmado nesta sessão. Clique em Consultar.')

aba_jogos, aba_hist, aba_conf = st.tabs(['🎲 Gerador de jogos', '📊 Histórico e estatísticas', '🔍 Conferência e backtest'])
with aba_hist:
    limite = st.number_input('Quantidade de concursos recentes para carregar', min_value=1, max_value=300, value=30, step=10)
    if st.button('Carregar histórico recente'):
        try:
            ultimo_online = obter(mod, permitir_alternativa=alternativa)
            base = ultimo_online['dados']['numero']
            total = min(int(limite), base)
            barra = st.progress(0)
            falhas = {}
            ok = 0
            for i, concurso in enumerate(range(base, base - total, -1)):
                try:
                    ret = ultimo_online if concurso == base else obter(mod, concurso, alternativa)
                    d = dict(ret['dados'])
                    d['_fonte'] = ret['fonte']
                    st.session_state.historicos.setdefault(mod, {})[concurso] = d
                    ok += 1
                except RuntimeError as e:
                    falhas[concurso] = str(e)
                barra.progress((i + 1) / total)
            st.session_state.falhas[mod] = falhas
            st.success(f'{ok} concursos carregados; {len(falhas)} não carregados.')
        except RuntimeError as e:
            st.error(f'Não foi possível iniciar o histórico: {e}')
    falhas = st.session_state.falhas.get(mod, {})
    if falhas:
        st.warning(f'Concursos com falha: {", ".join(map(str, sorted(falhas, reverse=True)))}. Estatísticas usam apenas dados validados.')
        with st.expander('Detalhes das falhas'):
            st.dataframe(pd.DataFrame([{'Concurso': n, 'Motivo': msg} for n, msg in sorted(falhas.items(), reverse=True)]), hide_index=True)
    dados = sorted(st.session_state.historicos.get(mod, {}).values(), key=lambda d: d['numero'])
    st.write(f'Concursos validados nesta sessão: **{len(dados)}**')
    if dados:
        df = pd.DataFrame([linha_historico(d, mod) for d in dados])
        st.dataframe(df, hide_index=True, use_container_width=True)
        st.download_button('Baixar histórico CSV', csv_bytes(df), f'historico_{CONFIG[mod][0]}.csv', 'text/csv')
        if mod == 'Super Sete':
            coluna = st.selectbox('Coluna do Super Sete', list(range(1, 8)))
            freq = Counter(numeros(d)[coluna - 1] for d in dados)
            universo = range(10)
        else:
            freq = Counter(n for d in dados for n in numeros(d))
            universo = range(CONFIG[mod][1], CONFIG[mod][2] + 1)
        st.subheader('Frequência observada (não é previsão)')
        st.bar_chart(pd.Series({n: freq.get(n, 0) for n in universo}, name='Ocorrências'))
        st.caption(f'Amostra: {len(dados)} concursos. Zero significa que o número não apareceu nessa amostra.')
        if mod != 'Super Sete':
            pares = [sum(x % 2 == 0 for x in numeros(d)) for d in dados]
            somas = [sum(numeros(d)) for d in dados]
            a, b, c = st.columns(3)
            a.metric('Média de pares', f'{sum(pares) / len(pares):.1f}')
            b.metric('Média da soma', f'{sum(somas) / len(somas):.1f}')
            c.metric('Dezenas diferentes na amostra', len(freq))
            st.subheader('Distribuição de números pares por concurso')
            st.bar_chart(pd.Series(dict(sorted(Counter(pares).items())), name='Concursos'))
        if mod == 'Dupla-Sena':
            st.subheader('Frequência — segundo sorteio')
            f = Counter(n for d in dados for n in numeros(d, 'listaDezenasSegundoSorteio'))
            st.bar_chart(pd.Series({n: f.get(n, 0) for n in range(1, 51)}))
        if mod == '+Milionária':
            st.subheader('Frequência dos trevos')
            f = Counter(n for d in dados for n in numeros(d, 'trevosSorteados'))
            st.bar_chart(pd.Series({n: f.get(n, 0) for n in range(1, 7)}))
        if mod == 'Dia de Sorte':
            st.subheader('Frequência dos meses')
            f = Counter(d['nomeTimeCoracaoMesSorte'] for d in dados)
            st.bar_chart(pd.Series({m: f.get(m, 0) for m in MESES}))

with aba_jogos:
    qtd = st.number_input('Quantidade de jogos-base', min_value=1, max_value=100, value=10)
    metodos = ['Aleatório uniforme', 'Equilibrado (heurístico)', 'Frequência histórica (experimental)']
    if mod == 'Lotomania':
        metodos = ['Aleatório uniforme', 'Frequência histórica (experimental)']
    if mod == 'Super Sete':
        metodos = ['Aleatório uniforme', 'Frequência histórica por coluna (experimental)']
    metodo = st.selectbox('Estratégia', metodos)
    espelho = st.checkbox('Criar aposta-espelho para cada jogo (Lotomania)', disabled=mod != 'Lotomania')
    if st.button('Gerar combinações'):
        hist = list(st.session_state.historicos.get(mod, {}).values())
        freq = Counter(n for d in hist for n in numeros(d))
        por_coluna = {i: Counter(numeros(d)[i] for d in hist) for i in range(7)} if mod == 'Super Sete' else {}
        if metodo.startswith('Frequência') and not hist:
            st.warning('Não há histórico validado: serão gerados jogos aleatórios uniformes.')
        jogos, vistos = [], set()
        for _ in range(int(qtd)):
            for tentativa in range(200):
                jogo = gerar(mod, metodo, freq, por_coluna)
                chave = json.dumps(jogo, sort_keys=True, ensure_ascii=False)
                if chave not in vistos:
                    break
            if chave in vistos:
                st.warning('Não foi possível gerar mais combinações únicas neste momento.')
                break
            vistos.add(chave)
            jogos.append(jogo)
            if mod == 'Lotomania' and espelho:
                jogos.append({'numeros': sorted(set(range(100)) - set(jogo['numeros']))})
        st.session_state.jogos[mod] = jogos
    jogos = st.session_state.jogos.get(mod, [])
    if jogos:
        texto = '\n'.join(f'{i:02d}: {formatar(j, mod)}' for i, j in enumerate(jogos, 1))
        st.code(texto, language='text')
        st.download_button('Baixar jogos TXT', texto.encode('utf-8'), f'jogos_{CONFIG[mod][0]}.txt', 'text/plain')
    st.caption('Métodos baseados em histórico são descritivos/experimentais e não melhoram comprovadamente as chances.')

with aba_conf:
    jogos = st.session_state.jogos.get(mod, [])
    dados = list(st.session_state.historicos.get(mod, {}).values())
    if not jogos:
        st.info('Primeiro gere jogos na aba Gerador.')
    if not dados:
        st.info('Primeiro consulte ou carregue resultados.')
    if jogos and dados:
        numeros_concursos = sorted((d['numero'] for d in dados), reverse=True)
        escolhido = st.selectbox('Concurso para conferência', numeros_concursos)
        d = st.session_state.historicos[mod][escolhido]
        linhas = [{'Jogo': i, 'Combinação': formatar(j, mod), **acertos(j, d, mod)} for i, j in enumerate(jogos, 1)]
        st.dataframe(pd.DataFrame(linhas), hide_index=True, use_container_width=True)
        st.subheader('Backtest descritivo — jogos fixos versus concursos carregados')
        if st.button('Executar backtest'):
            linhas = [{'Concurso': d['numero'], 'Data': d['dataApuracao'], 'Jogo': i,
                       **acertos(j, d, mod)} for d in dados for i, j in enumerate(jogos, 1)]
            st.session_state[f'backtest_{mod}'] = pd.DataFrame(linhas)
        bt = st.session_state.get(f'backtest_{mod}')
        if bt is not None:
            st.dataframe(bt, hide_index=True, use_container_width=True)
            st.download_button('Baixar backtest CSV', csv_bytes(bt), f'backtest_{CONFIG[mod][0]}.csv', 'text/csv')
        st.caption('O backtest não prevê sorteios futuros e não calcula retorno financeiro.')

st.divider()
st.caption('Fontes: CAIXA (primária); API Guidi, LoteriasCaixa Heroku e ValorFinal (terceiros, alternativas opcionais). Todas sujeitas a falhas. Backup JSON é necessário para guardar dados entre sessões. Uso responsável.')
