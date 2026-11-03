"""
Estudo Bíblico em Contexto Judaico
----------------------------------
Instalar:  pip install streamlit google-genai
Correr:    streamlit run biblia_estudo.py

Secrets (.streamlit/secrets.toml ou Streamlit Cloud -> Settings -> Secrets):
    GEMINI_API_KEY = "a_chave_do_gemini"
    ACCESS_CODE = "a_senha_para_os_alunos"
    CONTACTO = "WhatsApp: +244 923030010"     (opcional)
"""
import hmac
import json
import os
import time

import streamlit as st
from google import genai
from google.genai import types

# O primeiro é o principal; se falhar, a app tenta o seguinte
MODELOS = ["gemini-3.8-flash", "gemini-2.5-flash-lite"]

PROMPT = """És um professor de estudo bíblico com formação em hebraico, grego,
literatura judaica do Segundo Templo e hermenêutica. Analisa a passagem abaixo
em português de Portugal, de forma rigorosa e honesta.

Regras:
- Distingue claramente o que é consenso académico do que é interpretação.
- NÃO inventes citações do Talmude, Midrash ou Targum. Se não tiveres certeza
  da referência exata, descreve a ideia sem citar capítulo/página.
- Onde houver interpretações diferentes (judaica, católica, protestante), mostra-as.

Passagem: {passagem}
{texto_extra}

Responde APENAS com JSON válido, neste formato:
{{
  "resumo": "resumo da passagem em 3-4 frases",
  "tema": "tema central e temas secundários",
  "proposito": "propósito do autor e para quem escrevia",
  "tipo_literario": {{
    "genero": "ex.: narrativa, lei, poesia, profecia, sabedoria, epístola, apocalíptico",
    "caracteristicas": "como o género influencia a leitura"
  }},
  "autor_data_destinatarios": "autoria, data provável, público original",
  "contexto_historico": "situação política, social e religiosa",
  "contexto_judaico": {{
    "costumes_e_cultura": "costumes, vida diária, honra/vergonha, família, etc.",
    "festas_e_templo": "festas, sacrifícios, sinagoga, templo, se relevante",
    "leitura_judaica": "como a tradição judaica (Targum, Midrash, Talmude, Rashi) lê este texto",
    "conceitos_hebraicos": "ideias hebraicas por trás do texto (ex.: shalom, hesed, torá)"
  }},
  "estrutura": ["bloco 1 (versículos): descrição", "bloco 2 ..."],
  "exegese": {{
    "observacoes": "observações versículo a versículo, de forma resumida",
    "palavras_chave": [
      {{"palavra": "", "original": "hebraico/grego", "transliteracao": "", "significado": ""}}
    ],
    "dificuldades": "problemas de tradução, variantes ou passagens debatidas"
  }},
  "textos_relacionados": [
    {{"referencia": "Livro cap:vers", "relacao": "paralelo / citação / eco / contraste e porquê"}}
  ],
  "teologia": "o que o texto revela sobre Deus, o ser humano, a aliança, a salvação",
  "aplicacao": "aplicação para hoje, fiel ao sentido original",
  "perguntas": ["pergunta de reflexão 1", "pergunta 2", "pergunta 3"]
}}"""


def segredo(nome: str) -> str:
    try:
        return os.getenv(nome) or st.secrets.get(nome, "")
    except Exception:
        return os.getenv(nome, "")


@st.cache_resource
def cliente():
    chave = segredo("GEMINI_API_KEY")
    if not chave:
        st.error("Falta a GEMINI_API_KEY.")
        st.stop()
    return genai.Client(api_key=chave)


@st.cache_data(show_spinner=False)
def analisar(passagem: str, texto: str) -> dict:
    extra = f"Texto fornecido:\n{texto}" if texto.strip() else ""
    ultimo_erro = None
    for modelo in MODELOS:
        for tentativa in range(3):
            try:
                resp = cliente().models.generate_content(
                    model=modelo,
                    contents=PROMPT.format(passagem=passagem, texto_extra=extra),
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json", temperature=0.3
                    ),
                )
                return json.loads(resp.text)
            except Exception as e:
                ultimo_erro = e
                msg = str(e)
                if "503" in msg or "UNAVAILABLE" in msg:
                    time.sleep(4 * (tentativa + 2))
                    continue
                if "404" in msg or "NOT_FOUND" in msg:
                    break  # este modelo não existe, passa ao seguinte
                raise
    raise ultimo_erro


def bloco(titulo: str, conteudo):
    st.subheader(titulo)
    if isinstance(conteudo, dict):
        for k, v in conteudo.items():
            st.markdown(f"*{k.replace('_', ' ').capitalize()}*")
            st.write(v)
    elif isinstance(conteudo, list):
        for item in conteudo:
            st.markdown(f"- {item}")
    else:
        st.write(conteudo)


def para_markdown(passagem: str, d: dict) -> str:
    linhas = [f"# Estudo: {passagem}\n"]
    for k, v in d.items():
        linhas.append(f"## {k.replace('_', ' ').capitalize()}")
        linhas.append(json.dumps(v, ensure_ascii=False, indent=2) if not isinstance(v, str) else v)
        linhas.append("")
    return "\n".join(linhas)


def aviso_sem_acesso():
    contacto = segredo("CONTACTO")
    msg = ("🔒 Para ver o resultado do estudo precisa da *chave de acesso*. "
           "Obtenha a senha com o Teacher Pedro e escreva-a na barra lateral.")
    if contacto:
        msg += f"\n\n{contacto}"
    st.warning(msg)


# ---------------- Interface ----------------
st.set_page_config(page_title="Estudo Bíblico", page_icon="📖", layout="wide")
st.title("📖 Estudo Bíblico em Contexto Judaico")

codigo_certo = segredo("ACCESS_CODE")

with st.sidebar:
    passagem = st.text_input("Passagem", placeholder="Ex.: João 3:1-21, Salmo 23, Gn 22")
    texto = st.text_area("Texto (opcional)", height=150,
                         help="Cola o texto se quiseres analisar uma tradução específica.")
    senha = st.text_input("Chave de acesso", type="password",
                          help="Peça a senha ao Teacher Pedro.")
    ir = st.button("Estudar", type="primary", use_container_width=True)

# Verifica a senha (sem senha configurada, ninguém entra)
tem_acesso = bool(codigo_certo) and hmac.compare_digest(
    senha.encode("utf-8"), codigo_certo.encode("utf-8")
)

if ir and passagem.strip():
    if not codigo_certo:
        st.error("A app ainda não tem ACCESS_CODE configurado nos Secrets.")
    elif not senha:
        aviso_sem_acesso()
    elif not tem_acesso:
        st.error("Chave de acesso incorrecta.")
        aviso_sem_acesso()
    else:
        with st.spinner("A preparar o estudo..."):
            try:
                dados = analisar(passagem.strip(), texto)
            except Exception as e:
                st.error(f"Erro: {e}")
                st.stop()
        st.session_state["dados"], st.session_state["passagem"] = dados, passagem
elif ir:
    st.info("Escreve uma passagem na barra lateral.")

# Só mostra resultados a quem tem a senha certa
if tem_acesso and "dados" in st.session_state:
    d, p = st.session_state["dados"], st.session_state["passagem"]
    st.header(p)
    st.info(d.get("resumo", ""))

    abas = st.tabs(["Visão geral", "Contexto judaico", "Exegese",
                    "Textos relacionados", "Teologia e aplicação"])

    with abas[0]:
        bloco("Tema", d.get("tema"))
        bloco("Propósito", d.get("proposito"))
        bloco("Tipo literário", d.get("tipo_literario"))
        bloco("Autor, data e destinatários", d.get("autor_data_destinatarios"))
        bloco("Estrutura", d.get("estrutura", []))

    with abas[1]:
        bloco("Contexto histórico", d.get("contexto_historico"))
        bloco("Contexto judaico", d.get("contexto_judaico"))

    with abas[2]:
        ex = d.get("exegese", {})
        bloco("Observações", ex.get("observacoes"))
        st.subheader("Palavras-chave")
        st.table(ex.get("palavras_chave", []))
        bloco("Dificuldades e debates", ex.get("dificuldades"))

    with abas[3]:
        st.subheader("Textos relacionados")
        for t in d.get("textos_relacionados", []):
            st.markdown(f"*{t.get('referencia')}* — {t.get('relacao')}")

    with abas[4]:
        bloco("Teologia", d.get("teologia"))
        bloco("Aplicação", d.get("aplicacao"))
        bloco("Perguntas para reflexão", d.get("perguntas", []))

    st.download_button("⬇️ Descarregar estudo (.md)", para_markdown(p, d),
                       file_name=f"estudo_{p.replace(' ', '_')}.md")
elif not ir:
    st.write("Escreve uma passagem na barra lateral, a chave de acesso, e clica em Estudar.")
    if not tem_acesso:
        aviso_sem_acesso()