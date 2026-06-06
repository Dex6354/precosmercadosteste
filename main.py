import streamlit as st
import streamlit.components.v1 as components
import requests
import unicodedata
import re
import time
import math
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed

# --- CONFIGURAÇÕES E CONSTANTES ---
TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzUxMiJ9.eyJpc3MiOiJ2aXBjb21tZXJjZSIsImF1ZCI6ImFwaS1hZG1pbiIsInN1YiI6IjZiYzQ4NjdlLWRjYTktMTFlOS04NzQyLTAyMGQ3OTM1OWNhMCIsInZpcGNvbW1lcmNlQ2xpZW50ZUlkIjpudWxsLCJpYXQiOjE3NTE5MjQ5MjgsInZlciI6MSwiY2xpZW50IjpudWxsLCJvcGVyYXRvciI6bnVsbCwib3JnIjoiMTYxIn0.yDCjqkeJv7D3wJ0T_fu3AaKlX9s5PQYXD19cESWpH-j3F_Is-Zb-bDdUvduwoI_RkOeqbYCuxN0ppQQXb1ArVg"
ORG_ID = "161"
HEADERS_SHIBATA = {
    "Authorization": f"Bearer {TOKEN}",
    "organizationid": ORG_ID,
    "sessao-id": "4ea572793a132ad95d7e758a4eaf6b09",
    "domainkey": "loja.shibata.com.br",
    "User-Agent": "Mozilla/5.0"
}

LOGO_SHIBATA_URL = "https://rawcdn.githack.com/gymbr/precosmercados/main/logo-shibata.png"
LOGO_NAGUMO_URL = "https://rawcdn.githack.com/gymbr/precosmercados/main/logo-nagumo2.png"
DEFAULT_IMAGE_URL = "https://rawcdn.githack.com/gymbr/precosmercados/main/sem-imagem.png"
ID_LOJA = "22" 
ITENS_POR_PAGINA = 24

# Criamos uma sessão global do requests para manter e validar os cookies do servidor
NAGUMO_SESSION = requests.Session()

# --- FUNÇÕES UTILITÁRIAS COMUNS ---
def remover_acentos(texto):
    if not texto: return ""
    return ''.join(c for c in unicodedata.normalize('NFD', texto) if unicodedata.category(c) != 'Mn').lower()

def gerar_formas_variantes(termo):
    variantes = {termo}
    if termo.endswith("s"): variantes.add(termo[:-1])
    else: variantes.add(termo + "s")
    return list(variantes)

def slugify(text):
    text = remover_acentos(text)
    text = re.sub(r'[^a-z0-9\s-]', '', text).strip()
    text = re.sub(r'[-\s]+', '-', text)
    return text

# --- LÓGICA DE CÁLCULO SHIBATA ---
def calcular_precos_papel(descricao, preco_total):
    desc_minus = descricao.lower()
    match_leve = re.search(r'leve\s*(\d+)', desc_minus)
    q_rolos = int(match_leve.group(1)) if match_leve else (
        int(m.group(1)) if (m := re.search(r'(\d+)\s*(rolos|unidades|uni|pacotes|pacote)', desc_minus)) else None
    )
    match_metros = re.search(r'(\d+(?:[\.,]\d+)?)\s*m(?:etros)?', desc_minus)
    m_rolos = float(match_metros.group(1).replace(',', '.')) if match_metros else None
    if q_rolos and m_rolos:
        preco_por_metro = preco_total / (q_rolos * m_rolos)
        return preco_por_metro, f"R$ {preco_por_metro:.3f}".replace('.', ',') + "/m"
    return None, None

def calcular_preco_unidade(descricao, preco_total):
    desc_minus = remover_acentos(descricao)
    m_kg = re.search(r'(\d+(?:[\.,]\d+)?)\s*(kg|quilo)', desc_minus)
    if m_kg:
        peso = float(m_kg.group(1).replace(',', '.'))
        return preco_total / peso, f"R$ {preco_total / peso:.2f}".replace('.', ',') + "/kg"
    m_g = re.search(r'(\d+(?:[\.,]\d+)?)\s*(g|gramas?)', desc_minus)
    if m_g:
        peso = float(m_g.group(1).replace(',', '.')) / 1000
        return preco_total / peso, f"R$ {preco_total / peso:.2f}".replace('.', ',') + "/kg"
    match_l = re.search(r'(\d+(?:[\.,]\d+)?)\s*(l|litros?)', desc_minus)
    if match_l:
        litros = float(match_l.group(1).replace(',', '.'))
        return preco_total / litros, f"R$ {preco_total / litros:.2f}".replace('.', ',') + "/L"
    match_ml = re.search(r'(\d+(?:[\.,]\d+)?)\s*(ml|mililitros?)', desc_minus)
    if match_ml:
        litros = float(match_ml.group(1).replace(',', '.')) / 1000
        return preco_total / litros, f"R$ {preco_total / litros:.2f}".replace('.', ',') + "/L"
    return None, None

def calcular_preco_papel_toalha(descricao, preco_total):
    desc = descricao.lower()
    qtd_unidades = int(m.group(1)) if (m := re.search(r'(\d+)\s*(rolos|unidades|pacotes|pacote|kits?)', desc)) else None
    folhas_por_unidade = int(m.group(1)) if (m := re.search(r'(\d+)\s*(folhas|toalhas)(?:\s*cada)?', desc)) else None
    
    match_leve_folhas = re.search(r'leve\s*(\d+)\s*pague\s*\d+\s*folhas', desc)
    if match_leve_folhas:
        folhas_leve = int(match_leve_folhas.group(1))
        return folhas_leve, preco_total / folhas_leve if folhas_leve else None

    match_leve_pague = re.findall(r'(\d+)', desc)
    folhas_leve = max(int(n) for n in match_leve_pague) if 'leve' in desc and 'folhas' in desc and match_leve_pague else None

    m_kit = re.search(r'unidades por kit[:\- ]+(\d+)', desc)
    m_rolo = re.search(r'quantidade de folhas por (?:rolo|unidade)[:\- ]+(\d+)', desc)
    if m_kit and m_rolo:
        total_folhas = int(m_kit.group(1)) * int(m_rolo.group(1))
        return total_folhas, preco_total / total_folhas if total_folhas else None

    if qtd_unidades and folhas_por_unidade:
        total_folhas = qtd_unidades * folhas_por_unidade
        return total_folhas, preco_total / total_folhas if total_folhas else None

    if folhas_por_unidade: return folhas_por_unidade, preco_total / folhas_por_unidade
    if folhas_leve: return folhas_leve, preco_total / folhas_leve
    return None, None

def formatar_preco_shibata(preco_total, qtd, unidade):
    if not unidade: return f"R$ {preco_total:.2f}".replace('.', ',')
    u = unidade.lower()
    if qtd and qtd != 1:
        return f"R$ {preco_total:.2f}".replace('.', ',') + f"/{str(qtd).replace('.', ',')}{u}"
    return f"R$ {preco_total:.2f}".replace('.', ',') + f"/{u}"

# --- LÓGICA NAGUMO TURBO ---
def contem_papel_toalha(texto):
    texto = remover_acentos(texto.lower())
    return "papel" in texto and "toalha" in texto

def extrair_info_papel_toalha(nome, descricao):
    texto_nome = remover_acentos(nome.lower())
    texto_completo = f"{texto_nome} {remover_acentos(descricao.lower())}"

    for texto in [texto_nome, texto_completo]:
        match = re.search(r'(\d+)\s*(un|unidades?|rolos?)\s*.*?(\d+)\s*(folhas|toalhas)', texto)
        if match:
            rolos, folhas_por_rolo = int(match.group(1)), int(match.group(3))
            return rolos, folhas_por_rolo, rolos * folhas_por_rolo, f"{rolos} {match.group(2)}, {folhas_por_rolo} {match.group(4)}"
        match = re.search(r'(\d+)\s*(folhas|toalhas)', texto)
        if match: return None, None, int(match.group(1)), f"{match.group(1)} {match.group(2)}"
    
    m_un = re.search(r"(\d+)\s*(un|unidades?)", texto_completo)
    if m_un: return None, None, int(m_un.group(1)), f"{m_un.group(1)} unidades"
    return None, None, None, None

def extrair_descricao_remota_nagumo(url_produto):
    """Acessa a URL interna do produto no Nagumo para capturar a especificação detalhada"""
    if not url_produto or url_produto == '#': return ""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    try:
        # Reutiliza os cookies fixados da sessão global para manter a consistência com a loja selecionada
        cookies_fixos = {
            "dw_store": ID_LOJA,
            "hasSelectedStore": ID_LOJA,
            "selectedStore": ID_LOJA,
            "meunagumo_store": ID_LOJA
        }
        response = NAGUMO_SESSION.get(url_produto, headers=headers, cookies=cookies_fixos, timeout=6)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "html.parser")
            tag_descricao = soup.find("p", class_="product-detail__longDescription")
            if tag_descricao:
                return tag_descricao.get_text(strip=True)
    except: pass
    return ""

def calcular_preco_unitario_nagumo(preco_valor, nome, descricao, medida_venda, is_weighable=False, link_produto='#'):
    nome_lower = nome.lower()
    nome_norm = remover_acentos(nome_lower)
    
    if "papel higi" in nome_norm:
        def extrair_rolos_metros(texto):
            r, m = None, None
            m_rolos = re.search(r'\bleve\s*(\d+)', texto)
            if not m_rolos:
                m_rolos = re.search(r'\bl\s*(\d+)\s*p\s*\d+', texto)
            if not m_rolos:
                m_rolos = re.search(r'(\d+)\s*(?:rolos?|unidades?|un)\b', texto)
            if not m_rolos:
                m_rolos = re.search(r'(?:c/|com)\s*(\d+)', texto)
            if m_rolos:
                r = float(m_rolos.group(1))
                
            m_metros = re.search(r'(\d+[.,]?\d*)\s*(m|metros?|mts?)(?!\w)', texto)
            if m_metros:
                m = float(m_metros.group(1).replace(',', '.'))
            return r, m

        rolos, metros = extrair_rolos_metros(nome_lower)
        
        # Condição de Contingência: Se for papel higiênico e NÃO tiver metros no título, acessa o link individual
        if not metros and link_produto != '#':
            descricao_html = extrair_descricao_remota_nagumo(link_produto)
            if descricao_html:
                descricao = (descricao or "") + " " + descricao_html

        # Consulta a descrição acumulada se faltar alguma informação
        if (not rolos or not metros) and descricao:
            desc_lower = descricao.lower()
            r_desc, m_desc = extrair_rolos_metros(desc_lower)
            if not rolos and r_desc: rolos = r_desc
            if not metros and m_desc: metros = m_desc

        if rolos and metros and rolos > 0 and metros > 0:
            return f"R$ {preco_valor / (rolos * metros):.3f}/m".replace('.', ',')

    if is_weighable:
        return f"R$ {preco_valor:.2f}/kg".replace('.', ',')

    match = re.search(r'(\d+[.,]?\d*)\s*(kg|g|l|ml)', nome_lower)
    if match:
        try:
            valor = float(match.group(1).replace(',', '.'))
            unid = match.group(2)
            if valor > 0:
                if unid == 'g': return f"R$ {preco_valor / (valor/1000):.2f}/kg".replace('.', ',')
                if unid == 'kg': return f"R$ {preco_valor / valor:.2f}/kg".replace('.', ',')
                if unid == 'ml': return f"R$ {preco_valor / (valor/1000):.2f}/L".replace('.', ',')
                if unid == 'l': return f"R$ {preco_valor / valor:.2f}/L".replace('.', ',')
        except: pass
        
    match_un = re.search(r'(\d+)\s*(un|unidades?|rolos?)', nome_lower)
    if match_un:
        try:
            qtd = float(match_un.group(1))
            if qtd > 0: return f"R$ {preco_valor / qtd:.2f}/un".replace('.', ',')
        except: pass

    if medida_venda == "unity": 
        return f"R$ {preco_valor:.2f}/un".replace('.', ',')
        
    return "---"

def extrair_valor_unitario(label):
    match = re.search(r"R\$ (\d+[.,]?\d*)", label)
    return float(match.group(1).replace(',', '.')) if match else float('inf')

def inicializar_sessao_nagumo():
    """Garante que a sessão inicial no HTML público exista antes das requisições AJAX paralelas"""
    url_inicializacao = f"https://www.nagumo.com.br/busca?q=Cenoura&idLoja={ID_LOJA}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    cookies_fixos = {
        "dw_store": ID_LOJA,
        "hasSelectedStore": ID_LOJA,
        "selectedStore": ID_LOJA,
        "meunagumo_store": ID_LOJA
    }
    try:
        # Faz uma chamada simples para gerar e estabelecer os cookies de sessão internos (dwsid, sid, etc.)
        NAGUMO_SESSION.get(url_inicializacao, headers=headers, cookies=cookies_fixos, timeout=8)
    except: pass

def fetch_api_nagumo(url):
    cookies_fixos = {
        "dw_store": ID_LOJA,
        "hasSelectedStore": ID_LOJA,
        "selectedStore": ID_LOJA,
        "meunagumo_store": ID_LOJA
    }
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "X-Requested-With": "XMLHttpRequest",
        "Referer": "https://www.nagumo.com.br/"
    }
    try:
        # Usamos o objeto de sessão persistente para herdar os tokens gerados
        r = NAGUMO_SESSION.get(url, headers=headers, cookies=cookies_fixos, timeout=10)
        if r.status_code == 200:
            return r.json()
    except: pass
    return {}

def buscar_nagumo_turbo_total(termo_usuario):
    palavras_chave = remover_acentos(termo_usuario).split()
    if not palavras_chave: return []
    
    termo_api = palavras_chave[0]
    
    # Executa a simulação do acesso inicial para forçar a criação da sessão correta no servidor deles
    inicializar_sessao_nagumo()
    
    url_inicial = f"https://www.nagumo.com.br/on/demandware.store/Sites-Nagumo-Site/pt_BR/Search-UpdateGrid?q={termo_api}&start=00&sz={ITENS_POR_PAGINA}&idLoja={ID_LOJA}"
    data_inicial = fetch_api_nagumo(url_inicial)
    
    total_count = data_inicial.get('productSearch', {}).get('count', 0)
    if total_count == 0: return []
    
    num_paginas = math.ceil(total_count / ITENS_POR_PAGINA)
    urls = [
        f"https://www.nagumo.com.br/on/demandware.store/Sites-Nagumo-Site/pt_BR/Search-UpdateGrid?q={termo_api}&start={i*ITENS_POR_PAGINA:02d}&sz={ITENS_POR_PAGINA}&idLoja={ID_LOJA}"
        for i in range(num_paginas)
    ]
    
    all_raw_products = []
    with ThreadPoolExecutor(max_workers=10) as executor:
        resultados = list(executor.map(fetch_api_nagumo, urls))
        for res in resultados:
            all_raw_products.extend(res.get('productsSearchResult', []))
            
    vistos = set()
    pre_final_list = []
    
    for p in all_raw_products:
        pid = p.get('id')
        if not pid or pid in vistos or not p.get('available'): continue
        
        nome = p.get('productName', '')
        nome_norm = remover_acentos(nome)
        
        if all(k in nome_norm for k in palavras_chave):
            vistos.add(pid)
            
            sales = p.get('price', {}).get('sales', {})
            preco_final = float(sales.get('value', 0)) if sales.get('value') else 0.0
            
            list_price = p.get('price', {}).get('list')
            preco_normal = float(list_price.get('value', 0)) if (list_price and list_price.get('value')) else preco_final
            
            for flag in p.get('flagtypes', []):
                if flag.get('valueFlag'):
                    try:
                        val_flag = float(flag['valueFlag'])
                        if val_flag < preco_final and val_flag > 0:
                            preco_normal = preco_final
                            preco_final = val_flag
                    except: pass
            
            has_promo = (preco_final < preco_normal and preco_normal > 0)
            is_weighable = p.get('weighable', False)
            
            descricao_item = p.get('shortDescription', '') or p.get('longDescription', '') or p.get('description', '')
            if not descricao_item:
                descricao_item = " ".join([str(v) for k, v in p.items() if isinstance(v, str) and 'desc' in k.lower()])

            img_data = p.get('images', {}).get('large', [{}])
            link_item = p.get('productShowFullUrl', '#')

            pre_final_list.append({
                'productName': nome,
                'preco_final': preco_final,
                'preco_normal': preco_normal,
                'has_promo': has_promo,
                'is_weighable': is_weighable,
                'descricao_item': descricao_item,
                'productMeasureValue': p.get('productMeasureValue'),
                'img_url': img_data[0].get('alt', DEFAULT_IMAGE_URL) if img_data else DEFAULT_IMAGE_URL,
                'link': link_item
            })
            
    # Processamento em lote das labels de cálculo para dar suporte às chamadas remotas concorrentes
    final_list = []
    with ThreadPoolExecutor(max_workers=10) as label_executor:
        futures = {
            label_executor.submit(
                calcular_preco_unitario_nagumo,
                item['preco_final'], item['productName'], item['descricao_item'], 
                item['productMeasureValue'], item['is_weighable'], item['link']
            ): item for item in pre_final_list
        }
        for future in as_completed(futures):
            item = futures[future]
            label = future.result()
            final_list.append({
                'productName': item['productName'],
                'preco_final': item['preco_final'],
                'preco_normal': item['preco_normal'],
                'has_promo': item['has_promo'],
                'calc_label': label,
                'sort_val': extrair_valor_unitario(label),
                'img_url': item['img_url'],
                'link': item['link']
            })

    return sorted(final_list, key=lambda x: x['sort_val'])

def buscar_pagina_shibata(termo, pagina):
    url = f"https://services.vipcommerce.com.br/api-admin/v1/org/{ORG_ID}/filial/1/centro_distribuicao/1/loja/buscas/produtos/termo/{termo}?page={pagina}"
    try:
        r = requests.get(url, headers=HEADERS_SHIBATA, timeout=10)
        if r.status_code == 200: return r.json().get('data', {}).get('produtos', [])
    except: pass
    return []

# --- INTERFACE STREAMLIT ---
st.set_page_config(page_title="Preços Mercados", page_icon="🛒", layout="wide")

st.markdown("""
    <style>
        .block-container { padding-top: 0rem; }
        footer {visibility: hidden;}
        #MainMenu {visibility: hidden;}
        div, span, strong, small { font-size: 0.75rem !important; }
        img { max-width: 100px; height: auto; }
        .product-container { display: flex; align-items: center; gap: 10px; }
        .product-image { min-width: 80px; max-width: 80px; flex-shrink: 0; }
        .product-info { flex: 1 1 auto; min-width: 0; word-break: break-word; overflow-wrap: break-word; }
        hr.product-separator { border: none; border-top: 1px solid #eee; margin: 10px 0; }
        .info-cinza { color: gray; font-size: 0.8rem; }
        [data-testid="stColumn"] {
            overflow-y: auto; max-height: 90vh; padding: 10px; border: 1px solid #f0f2f6; border-radius: 8px;
            max-width: 480px; margin-left: auto; margin-right: auto; background: transparent;
            scrollbar-width: thin; scrollbar-color: gray transparent;
        }
        [data-testid="stColumn"]::-webkit-scrollbar { width: 6px; background: transparent; }
        [data-testid="stColumn"]::-webkit-scrollbar-track { background: transparent; }
        [data-testid="stColumn"]::-webkit-scrollbar-thumb { background-color: gray; border-radius: 3px; border: 1px solid transparent; }
        [data-testid="stColumn"]::-webkit-scrollbar-thumb:hover { background-color: white; }
        .block-container { padding-right: 47px !important; padding-bottom: 15px !important; margin-bottom: 15px !important; }
        input[type="text"] { font-size: 0.8rem !important; }
        [data-testid="stColumn"] { margin-bottom: 20px; }
        header[data-testid="stHeader"] { display: none; }
    </style>
""", unsafe_allow_html=True)

st.markdown("<h6>🛒 Preços Mercados</h6>", unsafe_allow_html=True)
termo = st.text_input("🔎 Digite o nome do produto:", "Banana").strip()

if termo:
    col1, col2 = st.columns(2)
    termos_busca = gerar_formas_variantes(remover_acentos(termo))
    palavras_chave = remover_acentos(termo).split()

    with st.spinner("🔍 Buscando nos mercados..."):
        # --- PROCESSAMENTO SHIBATA ---
        raw_shibata = []
        with ThreadPoolExecutor(max_workers=8) as exe:
            fs = [exe.submit(buscar_pagina_shibata, t, p) for t in termos_busca for p in range(1, 6)]
            for f in as_completed(fs): raw_shibata.extend(f.result())
        
        vistos_shibata = set()
        shibata_final = []
        for p in raw_shibata:
            pid = p.get('id')
            if pid and pid not in vistos_shibata and p.get("disponivel", True):
                vistos_shibata.add(pid)
                desc = p.get('descricao', '')
                if all(k in remover_acentos(desc) for k in palavras_chave):
                    oferta = p.get('oferta') or {}
                    preco_oferta = oferta.get('preco_oferta')
                    preco_base = p.get('preco') or 0
                    preco_final = float(preco_oferta) if (p.get('em_oferta') and preco_oferta) else float(preco_base)
                    
                    p['url_final'] = f"https://www.loja.shibata.com.br/produto/{p.get('produto_id')}/{slugify(desc)}"
                    
                    unidade_sigla = p.get('unidade_sigla')
                    if unidade_sigla and unidade_sigla.lower() == "grande": unidade_sigla = None
                    p['preco_str'] = formatar_preco_shibata(preco_final, p.get('quantidade_unidade_diferente'), unidade_sigla)
                    p['preco_final'] = preco_final
                    
                    val_metro, _ = calcular_precos_papel(desc, preco_final)
                    _, val_folha = calcular_preco_papel_toalha(desc, preco_final)
                    val_unidade, _ = calcular_preco_unidade(desc, preco_final)

                    # Fallback 1: extrai preco unitario do preco_str quando a descricao nao tem o peso
                    # Ex: "R$ 1,80/0,2kg" -> 1.80 / 0.2 = 9.00/kg (preco correto para ordenacao)
                    if val_unidade is None:
                        match_ps = re.search(r"/\s*([\d.,]+)\s*(kg|g|l|ml)", p['preco_str'].lower())
                        if match_ps:
                            try:
                                q = float(match_ps.group(1).replace(",", "."))
                                u = match_ps.group(2).lower()
                                if u == "g": q /= 1000
                                elif u == "ml": q /= 1000
                                if q > 0: val_unidade = preco_final / q
                            except: pass

                    # Fallback 2: itens contaveis na descricao (ovos, unidades, duzia...)
                    # Ex: "30 Unidades" -> 9,99 / 30 = 0,333/unidade
                    val_item = None
                    if re.search(r'1\s*d[uú]zia', desc.lower()):
                        val_item = preco_final / 12
                    else:
                        match_contavel = re.search(r'(\d+)\s*(unidades?|ovos?)\b', desc.lower())
                        if match_contavel:
                            try:
                                qtd = int(match_contavel.group(1))
                                if qtd > 1:
                                    val_item = preco_final / qtd
                            except: pass

                    # Seleciona o menor valor calculado disponivel, independente da categoria (kg, L, m, folha...)
                    # val_item entra apenas como ultimo recurso: evita misturar preco/unidade com preco/metro ou preco/folha
                    candidatos = [v for v in [val_metro, val_folha, val_unidade] if v is not None and v > 0]
                    if not candidatos and val_item is not None and val_item > 0:
                        candidatos = [val_item]
                    p['sort_val'] = min(candidatos) if candidatos else preco_final
                    
                    shibata_final.append(p)
        shibata_final = sorted(shibata_final, key=lambda x: x['sort_val'] or 999)

        # --- PROCESSAMENTO NAGUMO TURBO ---
        nagumo_final = buscar_nagumo_turbo_total(termo)

    # --- EXIBIÇÃO COLUNA 1 (SHIBATA) ---
    with col1:
        st.markdown(f"""
            <h5 style="display: flex; align-items: center; justify-content: center;">
            <img src="{LOGO_SHIBATA_URL}" width="80" alt="Shibata" style="margin-right:8px; background-color: white; border-radius: 4px; padding: 3px;"/>
            </h5>
        """, unsafe_allow_html=True)
        st.markdown(f"<small>🔎 {len(shibata_final)} produto(s) encontrado(s).</small>", unsafe_allow_html=True)
        
        if not shibata_final:
            st.warning("Nenhum produto encontrado.")
            
        for p in shibata_final:
            img = f"https://produto-assets-vipcommerce-com-br.br-se1.magaluobjects.com/500x500/{p.get('imagem')}" if p.get('imagem') else DEFAULT_IMAGE_URL
            
            descricao = p.get('descricao', '')
            descricao_modificada = descricao
            preco_info_extra = ""
            preco_total = p['preco_final']
            preco_formatado = p['preco_str']

            match = re.search(r"/\s*([\d.,]+)\s*(kg|g|l|ml)", preco_formatado.lower())
            if match:
                try:
                    q = float(match.group(1).replace(",", "."))
                    u = match.group(2).lower()
                    if u == "g": q /= 1000; u = "kg"
                    elif u == "ml": q /= 1000; u = "l"
                    if q > 0: preco_info_extra += f"<div style='color:gray; font-size:0.75em;'>R$ {preco_total / q:.2f}/{u}</div>"
                except: pass

            if 'papel higienico' in remover_acentos(descricao):
                descricao_modificada = re.sub(r'(folha simples)', r"<span style='color:red;'><b>\1</b></span>", descricao_modificada, flags=re.IGNORECASE)
                descricao_modificada = re.sub(r'(folha dupla|folha tripla)', r"<span style='color:green;'><b>\1</b></span>", descricao_modificada, flags=re.IGNORECASE)

            total_folhas, preco_por_folha = calcular_preco_papel_toalha(descricao, preco_total)
            if total_folhas and preco_por_folha:
                descricao_modificada += f" <span style='color:gray;'>({total_folhas} folhas)</span>"
                preco_info_extra += f"<div style='color:gray; font-size:0.75em;'>R$ {preco_por_folha:.3f}/folha</div>"
            else:
                _, preco_por_metro_str = calcular_precos_papel(descricao, preco_total)
                if preco_por_metro_str:
                    preco_info_extra += f"<div style='color:gray; font-size:0.75em;'>{preco_por_metro_str}</div>"
                elif not re.search(r"/\s*([\d.,]+)\s*(kg|g|l|ml|un|l|ml|folhas?|m)", preco_formatado.lower()):
                    _, preco_por_unidade_str = calcular_preco_unidade(descricao, preco_total)
                    if preco_por_unidade_str: preco_info_extra += f"<div style='color:gray; font-size:0.75em;'>{preco_por_unidade_str}</div>"

            # Preco por unidade contavel: ovos, forminhas, sacos, qualquer item com "X unidades" na descricao
            # So exibe se ainda nao ha nenhum preco extra calculado (evita duplicar com kg/L/metro/folha)
            if not preco_info_extra:
                if re.search(r'1\s*d[uú]zia', descricao.lower()):
                    preco_info_extra += f"<div style='color:gray; font-size:0.75em;'>R$ {preco_total / 12:.4f}/unidade (duzia)</div>"
                else:
                    match_contavel = re.search(r'(\d+)\s*(unidades?|ovos?)\b', descricao.lower())
                    if match_contavel:
                        try:
                            qtd = int(match_contavel.group(1))
                            if qtd > 1:
                                preco_info_extra += f"<div style='color:gray; font-size:0.75em;'>R$ {preco_total / qtd:.4f}/unidade</div>"
                        except: pass

            oferta = p.get('oferta') or {}
            if p.get('em_oferta') and oferta.get('preco_oferta') and oferta.get('preco_antigo'):
                preco_antigo_val = float(oferta.get('preco_antigo'))
                desconto = round(100 * (preco_antigo_val - float(oferta.get('preco_oferta'))) / preco_antigo_val) if preco_antigo_val else 0
                preco_html = f"<div><b>{preco_formatado}</b><br> <span style='color:red;font-weight: bold;'>({desconto}% OFF)</span></div><div><span style='color:gray; text-decoration: line-through;'>R$ {preco_antigo_val:.2f}</span></div>"
            else:
                preco_html = f"<div><b>{preco_formatado}</b></div>"

            st.markdown(f"""
                <div class='product-container'>
                    <a href='{p['url_final']}' target='_blank' class='product-image' style='text-decoration:none;'>
                        <img src='{img}' width='80' style='background-color: white; border-top-left-radius: 6px; border-top-right-radius: 6px; border-bottom-left-radius: 0; border-bottom-right-radius: 0; display: block;'/>
                        <img src='{LOGO_SHIBATA_URL}' width='80' 
                            style='background-color: white; display: block; margin: 0 auto; border-top: 1.5px solid black; border-top-left-radius: 0; border-top-right-radius: 0; border-bottom-left-radius: 4px; border-bottom-right-radius: 4px; padding: 3px;'/>
                    </a>
                    <div class='product-info'>
                        <div style='margin-bottom: 4px;'><a href='{p['url_final']}' target='_blank' style='text-decoration:none; color:inherit;'><b>{descricao_modificada}</b></a></div>
                        <div style='font-size:0.85em;'>{preco_html}</div>
                        <div style='font-size:0.85em;'>{preco_info_extra}</div>
                    </div>
                </div>
                <hr class='product-separator' />
            """, unsafe_allow_html=True)

    # --- EXIBIÇÃO COLUNA 2 (NAGUMO) ---
    with col2:
        st.markdown(f"""
            <h5 style="display: flex; align-items: center; justify-content: center;">
                <img src="{LOGO_NAGUMO_URL}" width="80" alt="Nagumo" style="margin-right:8px; border-radius: 6px; border: 1.5px solid white; padding: 0px;"/>
            </h5>
        """, unsafe_allow_html=True)
        st.markdown(f"<small>🔎 {len(nagumo_final)} produto(s) encontrado(s).</small>", unsafe_allow_html=True)
        
        if not nagumo_final:
            st.warning("Nenhum produto encontrado.")
            
        for p in nagumo_final:
            img = p.get('img_url', DEFAULT_IMAGE_URL)
            titulo = p['productName']
            
            if contem_papel_toalha(titulo):
                _, _, _, texto_exibicao = extrair_info_papel_toalha(titulo, "")
                if texto_exibicao: titulo += f" <span class='info-cinza'>({texto_exibicao})</span>"
                
            if "papel higi" in remover_acentos(titulo.lower()):
                titulo = re.sub(r"(folha simples)", r"<span style='color:red; font-weight:bold;'>\1</span>", titulo, flags=re.IGNORECASE)
                titulo = re.sub(r"(folha dupla|folha tripla)", r"<span style='color:green; font-weight:bold;'>\1</span>", titulo, flags=re.IGNORECASE)

            preco_normal = p.get('preco_normal', 0.0)
            preco_final = p.get('preco_final', 0.0)
            
            if p.get('has_promo') and preco_final < preco_normal and preco_normal > 0:
                desconto_percentual = ((preco_normal - preco_final) / preco_normal) * 100
                preco_html = f"<span style='font-weight: bold; font-size: 1rem;'>R$ {preco_final:.2f}</span><br><span style='color: red; font-weight: bold;'> ({desconto_percentual:.0f}% OFF)</span><br><span style='text-decoration: line-through; color: gray;'>R$ {preco_normal:.2f}</span>"
            else:
                preco_html = f"<span style='font-weight: bold; font-size: 1rem;'>R$ {preco_final:.2f}</span>"

            st.markdown(f"""
                <div style="display: flex; align-items: flex-start; gap: 10px; margin-bottom: 0rem; flex-wrap: wrap;">
                    <a href='{p['link']}' target='_blank' style='flex: 0 0 auto; text-decoration:none;'>
                        <img src="{img}" width="80" style="background-color: white; border-top-left-radius: 6px; border-top-right-radius: 6px; border-bottom-left-radius: 0; border-bottom-right-radius: 0; display: block;"/>
                        <img src="{LOGO_NAGUMO_URL}" width="80" style="border-top-left-radius: 0; border-top-right-radius: 0; border-bottom-left-radius: 6px; border-bottom-right-radius: 6px; border: 1.5px solid white; padding: 0px; display: block;"/>
                    </a>
                    <div style="flex: 1; word-break: break-word; overflow-wrap: anywhere;">
                        <a href='{p['link']}' target='_blank' style='text-decoration:none; color:inherit;'><strong>{titulo}</strong></a><br>
                        <strong>{preco_html}</strong><br>
                        <div style="margin-top: 4px; font-size: 0.85em; color: gray;">{p['calc_label']}</div>
                    </div>
                </div>
                <hr class='product-separator' />
            """, unsafe_allow_html=True)

    # --- FORÇAR ROLAGEM PARA O TOPO ---
    # O timestamp torna o HTML único a cada busca, forçando o Streamlit a recriar
    # o iframe e re-executar o script (sem isso, o conteúdo idêntico é cacheado).
    components.html(
        f"""
        <script>
            /* {termo} | {time.time()} */
            function scrollColunas() {{
                const cols = window.parent.document.querySelectorAll('[data-testid="stColumn"]');
                cols.forEach(col => {{ col.scrollTop = 0; }});
            }}
            scrollColunas();
            setTimeout(scrollColunas, 150);
            setTimeout(scrollColunas, 400);
            setTimeout(scrollColunas, 800);
        </script>
        """,
        height=0,
        width=0,
        )
