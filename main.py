"""
Estudo Bíblico em Contexto Judaico - backend FastAPI
Correr local:  uvicorn main:app --reload
Variáveis de ambiente: GEMINI_API_KEY, ACCESS_CODE, CONTACTO (opcional), GEMINI_MODEL (opcional)
Ficheiros na mesma pasta: index.html, DejaVuSans.ttf
"""
import hmac
import json
import os
import time
from functools import lru_cache

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, Response
from fpdf import FPDF
from google import genai
from google.genai import types
from pydantic import BaseModel

BASE = os.path.dirname(os.path.abspath(__file__))
FONTE_PDF = os.path.join(BASE, "DejaVuSans.ttf")

# O primeiro é o principal; se falhar, tenta o seguinte
MODELOS = ["gemini-3.8-flash", "gemini-3.5-flash", "gemini-3.5-flash-lite"]
if os.environ.get("GEMINI_MODEL"):
    MODELOS.insert(0, os.environ["GEMINI_MODEL"])

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

app = FastAPI()


class PedidoEstudo(BaseModel):
    passagem: str
    texto: str = ""
    chave: str


class PedidoPdf(BaseModel):
    passagem: str
    dados: dict
    chave: str


def verificar(chave: str):
    codigos = [c.strip() for c in os.environ.get("ACCESS_CODE", "").split(",") if c.strip()]
    if not codigos:
        raise HTTPException(500, "A app ainda não tem ACCESS_CODE configurado.")
    if not chave:
        raise HTTPException(401, "Escreve a chave de acesso.")
    if not any(hmac.compare_digest(chave.encode("utf-8"), c.encode("utf-8")) for c in codigos):
        raise HTTPException(401, "Chave de acesso incorrecta.")


@lru_cache(maxsize=1)
def cliente():
    chave = os.environ.get("GEMINI_API_KEY", "")
    if not chave:
        raise HTTPException(500, "Falta a GEMINI_API_KEY.")
    return genai.Client(api_key=chave)


@lru_cache(maxsize=128)
def analisar(passagem: str, texto: str) -> dict:
    extra = f"Texto fornecido:\n{texto}" if texto.strip() else ""
    ultimo_erro = None
    for modelo in MODELOS:
        for _ in range(3):
            try:
                resp = cliente().models.generate_content(
                    model=modelo,
                    contents=PROMPT.format(passagem=passagem, texto_extra=extra),
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json", temperature=0.3
                    ),
                )
                return json.loads(resp.text)
            except HTTPException:
                raise
            except Exception as e:
                ultimo_erro = e
                msg = str(e)
                if "503" in msg or "UNAVAILABLE" in msg:
                    time.sleep(2)
                    break  # passa ao modelo seguinte
                if "404" in msg or "NOT_FOUND" in msg:
                    break  # modelo inexistente, passa ao seguinte
                raise
    raise ultimo_erro


def _texto(v) -> str:
    if v is None:
        return ""
    if isinstance(v, str):
        return v
    if isinstance(v, list):
        return "\n".join("• " + _texto(i).replace("\n", "; ") for i in v)
    if isinstance(v, dict):
        return "\n".join(f"{k.replace('_', ' ').capitalize()}: {_texto(x)}" for k, x in v.items())
    return str(v)


def para_pdf(passagem: str, d: dict) -> bytes:
    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)
    if os.path.exists(FONTE_PDF):
        pdf.add_font("DejaVu", "", FONTE_PDF)
        fonte = "DejaVu"
        limpar = lambda t: t
    else:
        fonte = "Helvetica"
        limpar = lambda t: t.encode("latin-1", "replace").decode("latin-1")
    nl = dict(new_x="LMARGIN", new_y="NEXT")

    pdf.set_font(fonte, size=18)
    pdf.multi_cell(0, 10, limpar(f"Estudo: {passagem}"), **nl)
    pdf.ln(3)
    for k, v in d.items():
        pdf.set_font(fonte, size=14)
        pdf.multi_cell(0, 9, limpar(k.replace("_", " ").capitalize()), **nl)
        pdf.set_font(fonte, size=11)
        pdf.multi_cell(0, 6, limpar(_texto(v)), **nl)
        pdf.ln(3)
    return bytes(pdf.output())


@app.get("/")
def home():
    return FileResponse(os.path.join(BASE, "index.html"))
@app.get("/style.css")
def css():
    return FileResponse(os.path.join(BASE, "style.css"), media_type="text/css")

@app.get("/api/config")
def config():
    return {"contacto": os.environ.get("CONTACTO", "")}


@app.post("/api/estudar")
def estudar(p: PedidoEstudo):
    verificar(p.chave)
    if not p.passagem.strip():
        raise HTTPException(400, "Falta a passagem.")
    try:
        return {"dados": analisar(p.passagem.strip(), p.texto)}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(502, f"Erro: {e}")


@app.post("/api/pdf")
def pdf(p: PedidoPdf):
    verificar(p.chave)
    return Response(para_pdf(p.passagem, p.dados), media_type="application/pdf")