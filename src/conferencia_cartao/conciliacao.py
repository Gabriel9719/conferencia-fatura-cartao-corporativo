"""Conciliação entre a fatura e o registro interno de lançamentos."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from .parser import Fatura

TOLERANCIA_DIAS = 3

STATUS_OK = "OK"
STATUS_DIVERGENTE = "VALOR DIVERGENTE"
STATUS_NAO_LANCADO = "NÃO LANÇADO"
STATUS_SEM_FATURA = "LANÇADO SEM FATURA"
STATUS_ESTORNO = "ESTORNO"


def fatura_para_df(fat: Fatura) -> pd.DataFrame:
    df = pd.DataFrame([t.__dict__ for t in fat.transacoes])
    df["data"] = pd.to_datetime(df["data"])
    return df


def carregar_registro(caminho: str | Path) -> pd.DataFrame:
    df = pd.read_csv(caminho, sep=";", dtype={"conta_contabil": str})
    df["data"] = pd.to_datetime(df["data"])
    return df


def categorizar(df: pd.DataFrame, de_para: pd.DataFrame) -> pd.DataFrame:
    """Aplica a tabela De-Para (palavra-chave -> categoria) na descrição."""
    df = df.copy()
    df["categoria"] = "OUTROS"
    desc = df["descricao"].str.upper()
    for chave, cat in de_para[["palavra_chave", "categoria"]].itertuples(index=False):
        df.loc[desc.str.contains(chave.upper(), regex=False) & (df["categoria"] == "OUTROS"), "categoria"] = cat
    return df


def conciliar(fat_df: pd.DataFrame, reg: pd.DataFrame) -> pd.DataFrame:
    """Casa cada compra da fatura com um lançamento interno.

    Ordem de tentativa por compra: (1) mesmo portador, mesmo valor e data dentro da
    tolerância; (2) mesmo portador, data igual e descrição semelhante, mas valor
    diferente -> VALOR DIVERGENTE. Cada lançamento interno só é usado uma vez.
    """
    reg = reg.copy()
    reg["_usado"] = False
    resultado: dict[int, dict] = {}

    def candidatos(t):
        return reg[(~reg["_usado"]) & (reg["portador"] == t["portador"])
                   & ((reg["data"] - t["data"]).abs().dt.days <= TOLERANCIA_DIAS)]

    # 1ª passada: casamentos exatos (valor igual) têm prioridade sobre qualquer divergência
    for idx, t in fat_df.iterrows():
        base = {"origem": "FATURA", **t.to_dict(), "id_lancamento": None, "valor_lancado": None, "diferenca": None}
        if t["tipo"] == "ESTORNO":
            resultado[idx] = {**base, "status": STATUS_ESTORNO}
            continue
        cand = candidatos(t)
        exato = cand[(cand["valor"] - t["valor"]).abs() < 0.005]
        if not exato.empty:
            i = (exato["data"] - t["data"]).abs().idxmin()
            reg.at[i, "_usado"] = True
            resultado[idx] = {**base, "id_lancamento": reg.at[i, "id_lancamento"], "valor_lancado": reg.at[i, "valor"],
                              "diferenca": 0.0, "status": STATUS_OK}

    # 2ª passada: mesmo estabelecimento com valor diferente -> divergência (escolhe o valor mais próximo)
    for idx, t in fat_df.iterrows():
        if idx in resultado:
            continue
        base = {"origem": "FATURA", **t.to_dict(), "id_lancamento": None, "valor_lancado": None, "diferenca": None}
        cand = candidatos(t)
        mesmo_estab = cand[cand["historico"].str.upper().apply(lambda h: h[:12] in t["descricao"].upper())]
        if not mesmo_estab.empty:
            i = (mesmo_estab["valor"] - t["valor"]).abs().idxmin()
            reg.at[i, "_usado"] = True
            resultado[idx] = {**base, "id_lancamento": reg.at[i, "id_lancamento"], "valor_lancado": reg.at[i, "valor"],
                              "diferenca": round(reg.at[i, "valor"] - t["valor"], 2), "status": STATUS_DIVERGENTE}
        else:
            resultado[idx] = {**base, "status": STATUS_NAO_LANCADO}
    linhas = [resultado[i] for i in fat_df.index]

    for _, r in reg[~reg["_usado"]].iterrows():
        linhas.append({"origem": "REGISTRO", "portador": r["portador"], "data": r["data"], "descricao": r["historico"],
                       "valor": None, "id_lancamento": r["id_lancamento"], "valor_lancado": r["valor"],
                       "diferenca": r["valor"], "status": STATUS_SEM_FATURA})
    return pd.DataFrame(linhas)


def resumo(conc: pd.DataFrame) -> pd.DataFrame:
    return (conc.groupby("status", dropna=False)
                .agg(qtd=("status", "size"), valor_fatura=("valor", "sum"), valor_lancado=("valor_lancado", "sum"))
                .reset_index())
