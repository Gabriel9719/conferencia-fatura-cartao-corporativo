"""Linha de comando: python -m conferencia_cartao FATURA.pdf REGISTRO.csv [--de-para ...] [--saida ...]"""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from .conciliacao import carregar_registro, categorizar, conciliar, fatura_para_df
from .parser import ler_fatura
from .relatorio import gerar_relatorio


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="conferencia_cartao", description="Concilia a fatura do cartão corporativo com o registro interno.")
    ap.add_argument("fatura", type=Path)
    ap.add_argument("registro", type=Path)
    ap.add_argument("--de-para", type=Path, default=Path("data/de_para_categorias.csv"))
    ap.add_argument("--saida", type=Path, default=None, help="Arquivo .xlsx de saída (padrão: saida/conferencia_AAAA_MM.xlsx)")
    a = ap.parse_args(argv)

    fat = ler_fatura(a.fatura)
    df = fatura_para_df(fat)
    if a.de_para.exists():
        df = categorizar(df, pd.read_csv(a.de_para, sep=";"))
    else:
        df["categoria"] = "OUTROS"
    conc = conciliar(df, carregar_registro(a.registro))
    conc["categoria"] = conc["categoria"].fillna("-") if "categoria" in conc else "-"
    por_cat = (df.groupby(["portador", "categoria"])["valor"].sum().round(2).reset_index()
                 .sort_values(["portador", "valor"], ascending=[True, False]))
    saida = a.saida or Path("saida") / f"conferencia_{fat.fim:%Y_%m}.xlsx"
    gerar_relatorio(fat, conc, por_cat, saida)

    print(f"Período detectado: {fat.inicio:%d/%m/%Y} a {fat.fim:%d/%m/%Y}")
    print(f"Transações lidas: {len(fat.transacoes)} | Total fatura: {fat.total_declarado:,.2f} | "
          f"Total calculado: {fat.total_calculado:,.2f} | Fecha: {'SIM' if fat.fecha else 'NÃO'}")
    print(conc["status"].value_counts().to_string())
    print(f"Relatório: {saida}")
    return 0 if fat.fecha else 1


if __name__ == "__main__":
    raise SystemExit(main())
