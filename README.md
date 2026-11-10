# Conferência automática da fatura do cartão corporativo

![testes](https://img.shields.io/badge/testes-pytest-0A9EDC) ![python](https://img.shields.io/badge/python-3.10%2B-3776AB) ![licença](https://img.shields.io/badge/licen%C3%A7a-MIT-green)

Script em Python que **lê a fatura oficial em PDF**, extrai as compras de cada portador e **concilia automaticamente** com os lançamentos registrados no sistema contábil. Gera um relatório em Excel com o status de cada compra.

> **Todos os dados deste repositório são fictícios.** Empresa, portadores, estabelecimentos e valores foram gerados por script e não representam nenhuma pessoa ou instituição real.

## O problema

Na rotina de contas a pagar de uma cooperativa de crédito, a fatura mensal dos cartões corporativos era conferida manualmente: compra por compra, contra os lançamentos contábeis. Os principais pontos de atenção eram:

- compras **sem lançamento** ou lançadas com **valor digitado errado**;
- lançamentos **sem compra correspondente** na fatura;
- **estornos** e **compras internacionais** (valor em moeda, cotação e IOF em linha separada);
- identificar o **período** da fatura, inclusive na **virada de ano**.

A primeira versão era uma macro VBA que dependia de copiar e colar dados do portal. Esta versão lê o **PDF diretamente**.

## A solução

```
Fatura (PDF) ──► parser.py ──► transações ──┐
                                            ├──► conciliacao.py ──► relatorio.py ──► conferencia_AAAA_MM.xlsx
Registro interno (CSV) ─────────────────────┘          ▲
                                       De-Para de categorias (CSV)
```

| Etapa | O que faz |
|---|---|
| **Leitura do PDF** | `pdfplumber` + expressões regulares em uma máquina de estados (cabeçalho → portador → compras → total). Linhas de continuação das compras internacionais são anexadas à compra anterior. |
| **Validação** | Soma das linhas extraídas **= total declarado** na fatura. Se não bater, o script retorna código 1, o que é útil para agendamento. |
| **Período automático** | Lido do próprio PDF, com tratamento de faturas que atravessam a virada do ano (dez → jan). |
| **Conciliação** | Em duas passadas: (1) mesmo portador, mesmo valor e data em até ±3 dias; (2) mesmo estabelecimento com valor diferente, marcado como divergência. Cada lançamento é usado uma única vez. |
| **Categorização** | Tabela De-Para (palavra-chave → categoria), editável sem mexer no código. |

### Status gerados

| Status | Significado |
|---|---|
| `OK` | Compra encontrada no registro com o mesmo valor |
| `VALOR DIVERGENTE` | Lançamento encontrado, mas com valor diferente (diferença calculada) |
| `NÃO LANÇADO` | Compra da fatura sem lançamento correspondente |
| `LANÇADO SEM FATURA` | Lançamento interno sem compra na fatura |
| `ESTORNO` | Crédito/estorno identificado na fatura |

## Como executar

```bash
pip install -r requirements.txt

# 1) gerar uma fatura fictícia em PDF e o registro interno com divergências propositais
python scripts/gerar_dados_ficticios.py --saida data/exemplo --seed 42

# 2) rodar a conferência
PYTHONPATH=src python -m conferencia_cartao data/exemplo/fatura_ficticia_2026_07.pdf \
    data/exemplo/registro_interno_2026_07.csv --saida saida/conferencia_2026_07.xlsx
```

No Windows (PowerShell), use `$env:PYTHONPATH="src"; py -m conferencia_cartao ...`.

Saída do exemplo:

```
Período detectado: 26/06/2026 a 25/07/2026
Transações lidas: 34 | Total fatura: 11,405.53 | Total calculado: 11,405.53 | Fecha: SIM
OK                    30
NÃO LANÇADO            2
VALOR DIVERGENTE       1
ESTORNO                1
LANÇADO SEM FATURA     1
```

O relatório de exemplo está em [`docs/exemplo_relatorio.xlsx`](docs/exemplo_relatorio.xlsx), com as abas **Resumo**, **Conciliação** (status coloridos e filtros) e **Por categoria**.

## Testes

```bash
pytest -q
```

Os testes cobrem a conversão de valores no formato brasileiro, a virada de ano, as compras internacionais e os estornos, além de um teste **ponta a ponta** que gera um PDF fictício e confere se todas as divergências plantadas foram encontradas. O GitHub Actions roda os testes a cada push.

## Estrutura

```
├── src/conferencia_cartao/
│   ├── parser.py        # leitura do PDF e máquina de estados
│   ├── conciliacao.py   # regras de casamento e status
│   ├── relatorio.py     # Excel formatado (openpyxl)
│   └── cli.py           # linha de comando
├── scripts/gerar_dados_ficticios.py
├── data/de_para_categorias.csv
├── tests/
└── docs/exemplo_relatorio.xlsx
```

## Resultados na rotina real

- A conferência manual, compra a compra, deu lugar a um comando que roda em segundos.
- A validação "soma das linhas = total da fatura" garante que nenhuma compra fique de fora na leitura.
- A ferramenta roda no Windows corporativo sem instalar nada além do Python.

## Stack

Python · pdfplumber · pandas · openpyxl · reportlab (geração dos dados fictícios) · pytest · GitHub Actions

---
Autor: **Gabriel Antônio Ribeiro**, Analista Financeiro · [LinkedIn](https://www.linkedin.com/in/gabriel-ant%C3%B4nio-ribeiro-017808210)
