import subprocess
import sys
from pathlib import Path

import pandas as pd

from conferencia_cartao.conciliacao import carregar_registro, conciliar, fatura_para_df
from conferencia_cartao.parser import ler_fatura

RAIZ = Path(__file__).resolve().parents[1]


def test_fluxo_completo(tmp_path):
    subprocess.run([sys.executable, str(RAIZ / "scripts/gerar_dados_ficticios.py"), "--saida", str(tmp_path)], check=True)
    fat = ler_fatura(tmp_path / "fatura_ficticia_2026_07.pdf")
    assert fat.fecha, "a soma das linhas deve bater com o total declarado"
    conc = conciliar(fatura_para_df(fat), carregar_registro(tmp_path / "registro_interno_2026_07.csv"))
    contagem = conc["status"].value_counts()
    # divergências plantadas pelo gerador
    assert contagem["NÃO LANÇADO"] == 2
    assert contagem["VALOR DIVERGENTE"] == 1
    assert contagem["LANÇADO SEM FATURA"] == 1
    assert contagem["ESTORNO"] == 1
    assert isinstance(conc, pd.DataFrame)
