import streamlit as st
import requests
import re
import time

# IMPORTANDO AS LISTAS DO ARQUIVO EXTERNO
from cnaes import revenda, atacado, construtora, nao_contrib, contribuint

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(
    page_title="Triagem Fiscal",
    page_icon="🏢", 
    layout="centered"
)

def classificar_cnae(codigos):
    codigos = set(str(c) for c in codigos)
    possui_contribuinte = any(c in contribuint for c in codigos)
    possui_revenda = any(c in revenda for c in codigos)
    possui_atacado = any(c in atacado for c in codigos)
    possui_construtora = any(c in construtora for c in codigos)

    if codigos.issubset(nao_contrib):
        return "Não Contribuinte do ICMS", "🔴"
    if codigos.issubset(nao_contrib.union(construtora)) and possui_construtora:
        return "Construtora", "🏗️"
    if possui_revenda:
        return "Revenda", "🛒"
    if possui_atacado:
        return "Atacado", "📦"
    if possui_contribuinte:
        return "Contribuinte do ICMS", "🟢"
    return "Contatar Depto. Contábil", "⚠️"

# --- INTERFACE ---
st.title("🏢 Consulta & Triagem Fiscal")
st.markdown("Digite o CNPJ abaixo para verificar a **Classificação**, **Situação** e **Inscrição Estadual**.")

cnpj_input = st.text_input("CNPJ do Cliente", placeholder="00.000.000/0001-00")
botao_consultar = st.button("Consultar CNPJ", type="primary")

if botao_consultar and cnpj_input:
    cnpj_limpo = re.sub(r'\D', '', cnpj_input)
    
    with st.spinner('Analisando dados nas bases do governo...'):
        time.sleep(0.5) 
        
        sucesso = False
        dados_finais = {}

        # --- TENTATIVA 1: API PREMIUM (CNPJ.WS) ---
        try:
            url_premium = f"https://publica.cnpj.ws/cnpj/{cnpj_limpo}"
            resp = requests.get(url_premium)
            if resp.status_code == 200:
                data = resp.json()
                estab = data.get('estabelecimento', {})
                
                # Dados Básicos
                dados_finais['razao'] = data.get('razao_social')
                dados_finais['situacao'] = estab.get('situacao_cadastral', '')
                dados_finais['cidade'] = estab.get('cidade', {}).get('nome')
                dados_finais['uf'] = estab.get('estado', {}).get('sigla')
                dados_finais['logradouro'] = f"{estab.get('logradouro')}, {estab.get('numero')}"
                dados_finais['bairro'] = estab.get('bairro')
                dados_finais['cep'] = estab.get('cep')
                
                # CNAEs
                cnaes = []
                princ = estab.get('atividade_principal', {})
                if princ.get('id'): cnaes.append(princ.get('id'))
                dados_finais['desc_princ'] = princ.get('descricao')
                
                secundarias = []
                for ativ in estab.get('atividades_secundarias', []):
                    if ativ.get('id'): 
                        cnaes.append(ativ.get('id'))
                        secundarias.append(f"{ativ.get('id')} - {ativ.get('descricao')}")
                
                dados_finais['cnaes_codigos'] = cnaes
                dados_finais['cnaes_secundarios_texto'] = secundarias
                
                # --- LÓGICA DE INSCRIÇÃO ESTADUAL + STATUS ---
                ie_encontrada = None
                status_ie = False # Padrão
                
                inscricoes = estab.get('inscricoes_estaduais', [])
                
                for insc in inscricoes:
                    # Verifica se a IE é do mesmo estado do endereço da empresa
                    if insc.get('estado', {}).get('sigla') == dados_finais['uf']:
                        current_ie = insc.get('inscricao_estadual')
                        current_active = insc.get('ativo') # Pega o valor booleano (true/false)
                        
                        # Se ainda não achamos nenhuma, ou se achamos uma ATIVA (prioridade), salvamos
                        if ie_encontrada is None or current_active:
                            ie_encontrada = current_ie
                            status_ie = current_active
                        
                        # Se achou uma ativa no estado correto, pode parar de procurar
                        if current_active:
                            break
                
                dados_finais['ie'] = ie_encontrada
                # Transforma o True/False em texto legível
                dados_finais['ie_status_texto'] = "Habilitada" if status_ie else "Não Habilitada"
                
                sucesso = True

        except:
            pass

        # --- EXIBIÇÃO NA TELA ---
        if sucesso:
            classificacao, icone = classificar_cnae(dados_finais['cnaes_codigos'])
            
            st.subheader(dados_finais['razao'])
            
            if dados_finais['situacao'] != "Ativa":
                st.error(f"⚠️ EMPRESA NÃO ESTÁ ATIVA! Situação: {dados_finais['situacao']}")
            else:
                with st.container(border=True):
                    c1, c2 = st.columns([1, 2]) 
                    
                    with c1:
                        st.caption("Situação Cadastral")
                        if dados_finais['situacao'] == "Ativa":
                            st.success(f"**{dados_finais['situacao'].upper()}**", icon="✅")
                        else:
                            st.error(f"**{dados_finais['situacao'].upper()}**", icon="🚫")
                    
                    with c2:
                        st.caption("Classificação Fiscal")
                        st.markdown(f"#### {icone} {classificacao.upper()}")

                    st.divider() 

                    st.caption("Inscrição Estadual")
                    st.markdown("Consulte a IE: https://www.consultaie.com.br/")

                st.divider()

                st.markdown(f"**📍 Endereço:** {dados_finais['logradouro']} - {dados_finais['bairro']}")
                st.markdown(f"**🗺️ Cidade:** {dados_finais['cidade']} - {dados_finais['uf']} | **CEP:** {dados_finais['cep']}")

                st.divider()
                
                st.markdown("### 📋 Atividades Econômicas")
                st.markdown(f"**Atividade Principal:** {dados_finais['cnaes_codigos'][0]} - {dados_finais['desc_princ']}")
                
                with st.expander("Ver Atividades Secundárias"):
                    for item in dados_finais['cnaes_secundarios_texto']:
                        st.text(item)

        else:
            st.error("❌ CNPJ não encontrado ou erro nas bases de dados.")
