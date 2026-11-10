"""Gera o relatório de conferência em Excel (openpyxl), pronto para auditoria."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from .parser import Fatura

AZUL = "003641"
CORES_STATUS = {"OK": "D9F2E6", "VALOR DIVERGENTE": "FFF2CC", "NÃO LANÇADO": "F8D7DA",
                "LANÇADO SEM FATURA": "F8D7DA", "ESTORNO": "E7E6E6"}
FMT_BRL = '"R$" #,##0.00;[Red]-"R$" #,##0.00'


def _cabecalho(ws, colunas):
    ws.append(colunas)
    for c in ws[1]:
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor=AZUL)
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    ws.freeze_panes = "A2"


def _df_para_aba(wb, nome, df: pd.DataFrame, colunas_moeda=(), coluna_status=None):
    ws = wb.create_sheet(nome)
    _cabecalho(ws, list(df.columns))
    for row in df.itertuples(index=False):
        ws.append([None if pd.isna(v) else (v.to_pydatetime() if isinstance(v, pd.Timestamp) else v) for v in row])
    for i, col in enumerate(df.columns, start=1):
        letra = get_column_letter(i)
        largura = max(len(str(col)), *(len(str(v)) for v in df[col].head(200))) if len(df) else len(col)
        ws.column_dimensions[letra].width = min(max(largura + 2, 10), 45)
        if col in colunas_moeda:
            for c in ws[letra][1:]:
                c.number_format = FMT_BRL
        if col == "data":
            for c in ws[letra][1:]:
                c.number_format = "DD/MM/YYYY"
    if coluna_status and coluna_status in df.columns:
        j = list(df.columns).index(coluna_status) + 1
        for r in range(2, ws.max_row + 1):
            cor = CORES_STATUS.get(ws.cell(r, j).value)
            if cor:
                ws.cell(r, j).fill = PatternFill("solid", fgColor=cor)
    ws.auto_filter.ref = ws.dimensions
    return ws


def gerar_relatorio(fat: Fatura, conc: pd.DataFrame, por_categoria: pd.DataFrame, saida: str | Path) -> Path:
    wb = Workbook()
    wb.properties.creator = "Gabriel Antônio Ribeiro"
    wb.properties.lastModifiedBy = "Gabriel Antônio Ribeiro"
    wb.properties.title = "Conferência da fatura do cartão corporativo"
    ws = wb.active
    ws.title = "Resumo"
    ws["A1"] = "Conferência da fatura do cartão corporativo"
    ws["A1"].font = Font(bold=True, size=14, color=AZUL)
    info = [
        ("Período", f"{fat.inicio:%d/%m/%Y} a {fat.fim:%d/%m/%Y}"),
        ("Vencimento", f"{fat.vencimento:%d/%m/%Y}" if fat.vencimento else "-"),
        ("Transações lidas", len(fat.transacoes)),
        ("Total declarado na fatura", fat.total_declarado),
        ("Total calculado (soma das linhas)", fat.total_calculado),
        ("Leitura do PDF fecha com o total?", "SIM" if fat.fecha else "NÃO - revisar PDF"),
    ]
    for i, (k, v) in enumerate(info, start=3):
        ws.cell(i, 1, k).font = Font(bold=True)
        c = ws.cell(i, 2, v)
        if isinstance(v, float):
            c.number_format = FMT_BRL
    ws.cell(10, 1, "Status da conciliação").font = Font(bold=True, color=AZUL)
    res = conc.groupby("status").agg(qtd=("status", "size"), valor=("valor", "sum")).reset_index()
    for j, h in enumerate(["Status", "Qtd", "Valor na fatura"], start=1):
        ws.cell(11, j, h).font = Font(bold=True)
    for i, r in enumerate(res.itertuples(index=False), start=12):
        ws.cell(i, 1, r.status).fill = PatternFill("solid", fgColor=CORES_STATUS.get(r.status, "FFFFFF"))
        ws.cell(i, 2, int(r.qtd))
        ws.cell(i, 3, float(r.valor)).number_format = FMT_BRL
    ws.column_dimensions["A"].width = 38
    ws.column_dimensions["B"].width = 26
    ws.column_dimensions["C"].width = 18

    cols = ["origem", "status", "portador", "data", "descricao", "categoria", "tipo", "valor",
            "id_lancamento", "valor_lancado", "diferenca", "moeda", "valor_moeda", "cotacao"]
    _df_para_aba(wb, "Conciliação", conc[[c for c in cols if c in conc.columns]],
                 colunas_moeda=("valor", "valor_lancado", "diferenca"), coluna_status="status")
    _df_para_aba(wb, "Por categoria", por_categoria, colunas_moeda=("valor",))
    saida = Path(saida)
    saida.parent.mkdir(parents=True, exist_ok=True)
    wb.save(saida)
    return saida
