# Crypto P/L — Analisador de extrato Binance (Spot)

Este mini-site lê o arquivo **"Binance Spot Order History" (.xlsx)** e calcula:

- **P/L realizado** (somente ordens de venda)
- **posição atual** (quantidade e custo acumulado)
- **P/L não realizado** (com preço atual informado ou buscado automaticamente)

> Método de custo: **FIFO** (primeiro que entra, primeiro que sai).

## Rodando localmente

```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/macOS:
# source .venv/bin/activate

pip install -r requirements.txt
python app.py
```

Acesse: http://127.0.0.1:5000

## Observações (importantes)

- O export da Binance às vezes tem linhas de cabeçalho repetidas; o parser tenta limpar isso.
- A taxa (fee) pode vir na moeda base (ex: BTC), na cotada (ex: BRL) ou em outra (ex: BNB).  
  - Se for em **base**: reduz a quantidade recebida (BUY) / aumenta a quantidade vendida (SELL)  
  - Se for em **cotada**: ajusta custo/proventos  
  - Se for em **outra moeda**: **não converte automaticamente** (depende de cotação da taxa)
- Isso não substitui apuração fiscal/contábil. É para acompanhamento.
