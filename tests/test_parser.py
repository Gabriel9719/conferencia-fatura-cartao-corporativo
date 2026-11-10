from datetime import date

from conferencia_cartao.parser import br_para_float, interpretar_texto

TEXTO = """CARTÃO CORPORATIVO EMPRESARIAL - FATURA MENSAL
Período: 26/12/2025 a 25/01/2026 Vencimento: 10/02/2026
Portador: FULANO DE TAL Cartão final 1111
28/12 POSTO TESTE ANAPOLIS 1.200,50
03/01 SOFTWARE INC EXTERIOR 108,40
USD 20,00 Cotação: 5,4200
05/01 ESTORNO POSTO TESTE ANAPOLIS -200,00
Total do portador: 1.108,90
TOTAL DA FATURA: 1.108,90
"""


def test_valores_brasileiros():
    assert br_para_float("1.234,56") == 1234.56
    assert br_para_float("-10,00") == -10.0


def test_interpreta_fatura_com_virada_de_ano():
    fat = interpretar_texto(TEXTO)
    assert fat.inicio == date(2025, 12, 26) and fat.fim == date(2026, 1, 25)
    assert [t.data for t in fat.transacoes] == [date(2025, 12, 28), date(2026, 1, 3), date(2026, 1, 5)]
    assert fat.fecha


def test_identifica_internacional_e_estorno():
    fat = interpretar_texto(TEXTO)
    inter, estorno = fat.transacoes[1], fat.transacoes[2]
    assert inter.tipo == "INTERNACIONAL" and inter.moeda == "USD" and inter.cotacao == 5.42
    assert estorno.tipo == "ESTORNO" and estorno.valor == -200.0
