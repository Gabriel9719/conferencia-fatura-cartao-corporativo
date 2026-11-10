"""Gera uma fatura de cartão corporativo FICTÍCIA em PDF e o registro interno
correspondente (lançamentos contábeis) em CSV, com divergências propositais
para demonstrar a conciliação.

Uso:
    python scripts/gerar_dados_ficticios.py --saida data/exemplo --seed 42
"""
from __future__ import annotations

import argparse
import csv
import random
from datetime import date, timedelta
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

EMPRESA = "COOPERATIVA DE CRÉDITO ALFA LTDA"
PORTADORES = [
    ("ANA PAULA MOREIRA", "4821"),
    ("CARLOS EDUARDO LIMA", "7730"),
    ("JULIANA COSTA REIS", "1194"),
]
ESTABELECIMENTOS = [
    ("POSTO RODOVIA SUL", "ANAPOLIS", (150, 420)),
    ("HOTEL CENTRAL PLAZA", "GOIANIA", (280, 690)),
    ("RESTAURANTE SABOR DO CERRADO", "ANAPOLIS", (45, 180)),
    ("PAPELARIA ESCRITORIO TOTAL", "BRASILIA", (60, 350)),
    ("UBER *TRIP", "GOIANIA", (18, 75)),
    ("LATAM AIRLINES", "SAO PAULO", (620, 1850)),
    ("ESTACIONAMENTO CENTRO", "GOIANIA", (12, 40)),
    ("MERCADO LIVRE *PECAS", "OSASCO", (90, 540)),
]
INTERNACIONAIS = [("AMAZON WEB SERVICES", "USD"), ("ZOOM VIDEO COMMUNICATIONS", "USD"), ("CANVA PTY LTD", "USD")]


def brl(v: float) -> str:
    s = f"{abs(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"-{s}" if v < 0 else s


def gerar_transacoes(rng: random.Random, inicio: date, fim: date) -> list[dict]:
    dias = (fim - inicio).days
    trans = []
    for nome, final in PORTADORES:
        for _ in range(rng.randint(9, 14)):
            est, cidade, (lo, hi) = rng.choice(ESTABELECIMENTOS)
            trans.append({
                "portador": nome, "final": final,
                "data": inicio + timedelta(days=rng.randint(0, dias)),
                "descricao": est, "cidade": cidade,
                "valor": round(rng.uniform(lo, hi), 2), "tipo": "NACIONAL",
            })
        if rng.random() < 0.8:
            est, moeda = rng.choice(INTERNACIONAIS)
            usd = round(rng.uniform(10, 90), 2)
            cot = round(rng.uniform(5.30, 5.70), 4)
            trans.append({
                "portador": nome, "final": final,
                "data": inicio + timedelta(days=rng.randint(0, dias)),
                "descricao": est, "cidade": "EXTERIOR", "valor": round(usd * cot, 2),
                "tipo": "INTERNACIONAL", "moeda": moeda, "valor_moeda": usd, "cotacao": cot,
            })
    # um estorno por fatura
    alvo = rng.choice([t for t in trans if t["tipo"] == "NACIONAL"])
    trans.append({**alvo, "data": alvo["data"] + timedelta(days=2), "descricao": "ESTORNO " + alvo["descricao"],
                  "valor": -alvo["valor"], "tipo": "ESTORNO"})
    trans.sort(key=lambda t: (t["portador"], t["data"]))
    return trans


def desenhar_pdf(trans: list[dict], inicio: date, fim: date, venc: date, caminho: Path) -> None:
    c = canvas.Canvas(str(caminho), pagesize=A4)
    c.setTitle("Fatura fictícia - Cartão Corporativo")
    c.setAuthor("Gabriel Antônio Ribeiro")
    c.setCreator("Gabriel Antônio Ribeiro")
    w, h = A4
    y = h - 20 * mm

    def linha(txt: str, x: float = 15 * mm, bold: bool = False, size: int = 9):
        nonlocal y
        if y < 20 * mm:
            c.showPage(); y = h - 20 * mm
        c.setFont("Helvetica-Bold" if bold else "Helvetica", size)
        c.drawString(x, y, txt)
        y -= 5 * mm

    linha("CARTÃO CORPORATIVO EMPRESARIAL - FATURA MENSAL (DOCUMENTO FICTÍCIO)", bold=True, size=11)
    linha(f"Empresa: {EMPRESA}")
    linha(f"Período: {inicio:%d/%m/%Y} a {fim:%d/%m/%Y}    Vencimento: {venc:%d/%m/%Y}")
    y -= 3 * mm
    total = 0.0
    for nome, final in PORTADORES:
        itens = [t for t in trans if t["portador"] == nome]
        linha(f"Portador: {nome}   Cartão final {final}", bold=True)
        sub = 0.0
        for t in itens:
            c.setFont("Helvetica", 9)
            linha(f"{t['data']:%d/%m}  {t['descricao'][:38]:<38} {t['cidade']:<12}", x=18 * mm)
            y += 5 * mm
            c.drawRightString(w - 15 * mm, y, brl(t["valor"]))
            y -= 5 * mm
            if t["tipo"] == "INTERNACIONAL":
                linha(f"      {t['moeda']} {brl(t['valor_moeda'])}  Cotação: {t['cotacao']:.4f}".replace(".", ","), x=18 * mm, size=8)
            sub += t["valor"]
        linha(f"Total do portador: {brl(round(sub, 2))}", x=120 * mm, bold=True)
        total += sub
        y -= 2 * mm
    linha(f"TOTAL DA FATURA: {brl(round(total, 2))}", x=120 * mm, bold=True, size=11)
    c.save()


def gerar_registro_interno(rng: random.Random, trans: list[dict], caminho: Path) -> None:
    """Simula os lançamentos feitos no sistema contábil, com divergências propositais."""
    regs = [t for t in trans if t["tipo"] != "ESTORNO"]
    rng.shuffle(regs)
    faltando = regs[:2]                       # compras sem lançamento
    valor_errado = regs[2]                     # digitação incorreta
    with caminho.open("w", newline="", encoding="utf-8") as f:
        wr = csv.writer(f, delimiter=";")
        wr.writerow(["id_lancamento", "data", "portador", "historico", "valor", "conta_contabil"])
        n = 1000
        for t in regs:
            if t in faltando:
                continue
            v = t["valor"] + (10.0 if t is valor_errado else 0.0)
            wr.writerow([n, f"{t['data']:%Y-%m-%d}", t["portador"], t["descricao"], f"{v:.2f}", "8.1.7.99.00.01"])
            n += 1
        # lançamento sem compra correspondente na fatura
        wr.writerow([n, f"{trans[0]['data']:%Y-%m-%d}", PORTADORES[0][0], "DESPESA SEM COMPROVANTE", "99.90", "8.1.7.99.00.01"])


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--saida", default="data/exemplo")
    ap.add_argument("--seed", type=int, default=42)
    a = ap.parse_args()
    rng = random.Random(a.seed)
    saida = Path(a.saida); saida.mkdir(parents=True, exist_ok=True)
    inicio, fim, venc = date(2026, 6, 26), date(2026, 7, 25), date(2026, 8, 10)
    trans = gerar_transacoes(rng, inicio, fim)
    desenhar_pdf(trans, inicio, fim, venc, saida / "fatura_ficticia_2026_07.pdf")
    gerar_registro_interno(rng, trans, saida / "registro_interno_2026_07.csv")
    print(f"{len(trans)} transações fictícias geradas em {saida}")


if __name__ == "__main__":
    main()
