"""Extração das transações da fatura em PDF.

A fatura é lida como texto (pdfplumber) e interpretada linha a linha por uma
pequena máquina de estados: cabeçalho -> seção do portador -> transações ->
total do portador. Linhas de continuação (compras internacionais) são
anexadas à transação anterior.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import pdfplumber

RE_PERIODO = re.compile(r"Per[ií]odo:\s*(\d{2})/(\d{2})/(\d{4})\s*a\s*(\d{2})/(\d{2})/(\d{4})")
RE_VENC = re.compile(r"Vencimento:\s*(\d{2})/(\d{2})/(\d{4})")
RE_PORTADOR = re.compile(r"^Portador:\s*(.+?)\s+Cart[ãa]o final\s+(\d{4})")
RE_TRANS = re.compile(r"^(\d{2})/(\d{2})\s+(.+?)\s+(-?[\d.]+,\d{2})$")
RE_INTER = re.compile(r"^(USD|EUR|GBP)\s+([\d.]+,\d{2})\s+Cota[çc][ãa]o:\s*([\d,]+)")
RE_TOTAL_PORT = re.compile(r"^Total do portador:\s*(-?[\d.]+,\d{2})")
RE_TOTAL_FAT = re.compile(r"^TOTAL DA FATURA:\s*(-?[\d.]+,\d{2})")


def br_para_float(txt: str) -> float:
    return float(txt.replace(".", "").replace(",", "."))


@dataclass
class Transacao:
    portador: str
    final_cartao: str
    data: date
    descricao: str
    valor: float
    tipo: str = "NACIONAL"          # NACIONAL | INTERNACIONAL | ESTORNO
    moeda: str | None = None
    valor_moeda: float | None = None
    cotacao: float | None = None


@dataclass
class Fatura:
    inicio: date
    fim: date
    vencimento: date | None
    transacoes: list[Transacao] = field(default_factory=list)
    totais_portador: dict[str, float] = field(default_factory=dict)
    total_declarado: float | None = None

    @property
    def total_calculado(self) -> float:
        return round(sum(t.valor for t in self.transacoes), 2)

    @property
    def fecha(self) -> bool:
        return self.total_declarado is not None and abs(self.total_calculado - self.total_declarado) < 0.005


def _ano_da_transacao(dia: int, mes: int, inicio: date, fim: date) -> int:
    """Detecta o ano de uma data dd/mm usando o período da fatura (virada de ano)."""
    if inicio.year == fim.year:
        return fim.year
    return inicio.year if mes >= inicio.month else fim.year


def interpretar_texto(texto: str) -> Fatura:
    linhas = [l.strip() for l in texto.splitlines() if l.strip()]
    corpo = "\n".join(linhas)
    m = RE_PERIODO.search(corpo)
    if not m:
        raise ValueError("Período da fatura não encontrado no PDF.")
    d1, m1, a1, d2, m2, a2 = map(int, m.groups())
    inicio, fim = date(a1, m1, d1), date(a2, m2, d2)
    mv = RE_VENC.search(corpo)
    venc = date(int(mv[3]), int(mv[2]), int(mv[1])) if mv else None
    fat = Fatura(inicio, fim, venc)

    portador = final = None
    for l in linhas:
        if (mp := RE_PORTADOR.match(l)):
            portador, final = mp[1].strip(), mp[2]
        elif (mt := RE_TOTAL_PORT.match(l)) and portador:
            fat.totais_portador[portador] = br_para_float(mt[1])
        elif (mf := RE_TOTAL_FAT.match(l)):
            fat.total_declarado = br_para_float(mf[1])
        elif (mi := RE_INTER.match(l)) and fat.transacoes:
            t = fat.transacoes[-1]
            t.tipo, t.moeda = "INTERNACIONAL", mi[1]
            t.valor_moeda, t.cotacao = br_para_float(mi[2]), br_para_float(mi[3])
        elif (mx := RE_TRANS.match(l)) and portador:
            dia, mes = int(mx[1]), int(mx[2])
            desc = mx[3].strip()
            valor = br_para_float(mx[4])
            tipo = "ESTORNO" if desc.upper().startswith("ESTORNO") or valor < 0 else "NACIONAL"
            fat.transacoes.append(Transacao(portador, final, date(_ano_da_transacao(dia, mes, inicio, fim), mes, dia),
                                            desc, valor, tipo))
    return fat


def ler_fatura(caminho: str | Path) -> Fatura:
    with pdfplumber.open(caminho) as pdf:
        texto = "\n".join(p.extract_text() or "" for p in pdf.pages)
    return interpretar_texto(texto)
