# Crypto P/L — Analisador de Extrato Binance (Spot)

Ferramenta web para analisar e calcular lucro/prejuízo (P/L) de suas operações de compra e venda de criptomoedas na Binance.

🌐 **Versão Online**: https://binance-analisador-pl.onrender.com

---

## Funcionalidades

- 📊 **P/L Realizado**: Calcula ganho/perda apenas nas ordens de venda executadas
- 📈 **Posição Atual**: Mostra quantidade e custo acumulado de holdings
- 💰 **P/L Não Realizado**: Calcula ganho/perda potencial com preço atual
- 📱 **Interface Responsiva**: Funciona em desktop, tablet e mobile
- 🌙 **Tema Claro/Escuro**: Toggle entre temas para melhor conforto visual
- 🔍 **Filtro por Par**: Analise pares específicos ou deixe em branco para usar o primeiro encontrado
- 📡 **Preço Automático**: Busca cotação atual na Binance ou permita informar manualmente

> **Método de custo**: FIFO (Primeiro que entra, Primeiro que sai)

---

## Como usar (Online)

1. Acesse https://binance-analisador-pl.onrender.com
2. Exporte seu histórico da Binance:
   - Binance → Orders → Spot Order History → Export
3. Selecione o arquivo `.xlsx`
4. (Opcional) Informe um par específico ou preço atual
5. Clique em **Analisar**

---

## Rodando localmente

### Requisitos
- Python 3.8+
- pip

### Instalação e execução

```bash
# Clonar ou baixar o repositório
git clone <repositório>
cd crypto_pl_site

# Criar ambiente virtual
python -m venv .venv

# Ativar ambiente virtual
# Windows:
.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate

# Instalar dependências
pip install -r requirements.txt

# Rodar aplicação
python app.py
```

Acesse: http://localhost:5000

---

## Notas Importantes

⚠️ **Aviso**: Este app é para acompanhamento pessoal e **não substitui apuração fiscal/contábil**.

### Sobre o processamento de dados

- **Export da Binance**: Ocasionalmente contém linhas de cabeçalho duplicadas; o parser trata automaticamente
- **Taxas (Fees)**:
  - Se em **moeda base** (ex: BTC): reduz quantidade em BUY ou aumenta em SELL
  - Se em **moeda cotada** (ex: BRL): ajusta custo/proventos
  - Se em **outra moeda** (ex: BNB): não converte automaticamente (depende de cotação)
- **Arquivo exportado**: Máximo de 200 últimas ordens do par selecionado
- **Cálculo FIFO**: Mais conservador e aceito para fins fiscais em várias jurisdições

---

## Stack Tecnológico

- **Backend**: Python + Flask
- **Frontend**: HTML5, CSS3, Bootstrap 5.3.3, JavaScript vanilla
- **Processamento**: openpyxl (Excel)
- **Hospedagem**: Render.com

---

## Licença

Livre para uso pessoal e educacional.
