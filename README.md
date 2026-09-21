# OpsVenda

Sistema de gestão de vendas (Shopee) construído em Flask, com autenticação,
cadastro de produtos, perfis de margem, vendas e importação/exportação de CSV.

Este guia cobre como colocar o ambiente de **desenvolvimento** para rodar no
Windows e no Linux. Para saber como o projeto é organizado (blueprints,
models, services), veja os comentários em [app/\_\_init\_\_.py](app/__init__.py).

## Pré-requisitos

- Python 3.12+
- Git

(Docker é necessário apenas para o modo de execução "produção", descrito no
final deste documento — não é preciso para desenvolver.)

## Windows (PowerShell)

```powershell
cd C:\Users\a958054\Projects\opsvenda\Opsvenda

# 1. Criar e ativar o ambiente virtual
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

> Se o PowerShell bloquear a ativação com um erro de política de execução,
> rode antes: `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`

```powershell
# 2. Instalar as dependências (inclui pytest e ferramentas de dev)
pip install -r requirements-dev.txt

# 3. Configurar variáveis de ambiente da aplicação
$env:FLASK_APP = "wsgi:app"
$env:FLASK_DEBUG = "1"

# 4. Subir o servidor de desenvolvimento
flask run
```

Acesse `http://127.0.0.1:5000`. Como ainda não existe nenhum usuário
cadastrado (banco sqlite local em `instance/app.db`), você é redirecionado
automaticamente para a tela de configuração inicial (`/setup`), onde cria o
usuário administrador pelo navegador.

Nas próximas vezes, só é preciso repetir os passos 1 (ativar) e 4 (subir);
`.venv` e o banco já ficam prontos.

## Linux / macOS (bash)

```bash
cd ~/Projects/opsvenda/Opsvenda

# 1. Criar e ativar o ambiente virtual
python3 -m venv .venv
source .venv/bin/activate

# 2. Instalar as dependências (inclui pytest e ferramentas de dev)
pip install -r requirements-dev.txt

# 3. Configurar variáveis de ambiente da aplicação
export FLASK_APP=wsgi:app
export FLASK_DEBUG=1

# 4. Subir o servidor de desenvolvimento
flask run
```

Acesse `http://127.0.0.1:5000`. Como ainda não existe nenhum usuário
cadastrado, você é redirecionado automaticamente para a tela de
configuração inicial (`/setup`), onde cria o usuário administrador pelo
navegador.

## Rodando os testes

Com o ambiente virtual ativado (Windows ou Linux):

```bash
pytest
```

## Comandos úteis do Flask CLI

Definidos em [app/cli.py](app/cli.py):

```bash
flask create-admin       # cria ou troca a senha de um usuário específico (pede username/senha via prompt) - útil para recuperar acesso
```

## Modo produção (Docker)

Para rodar via Docker/Gunicorn — útil para deploy em servidor. Requer
Docker Desktop/Engine instalado (com privilégios de administrador para
instalar o Docker em si):

```bash
cp .env.example .env
docker compose up -d --build
```

Isso sobe em `http://localhost:5000` (ou a porta definida em `APP_PORT` no
`.env`) dentro de um container, usando Gunicorn como servidor WSGI. No
primeiro acesso, a tela `/setup` pede pra criar o usuário administrador.

Também existem instaladores automatizados que fazem esse passo a passo do
Docker e ainda criam um atalho para o launcher desktop
([run_desktop.py](run_desktop.py), via `pywebview`, apontando pro
container):

- Windows: `.\install.ps1`
- Linux: `./install.sh`

## Distribuição standalone (sem admin, sem Docker)

Para distribuir o OpsVenda como um "programa solo" para máquinas sem
Docker e sem acesso de administrador (ex: notebook de um vendedor), existe
um pacote autocontido: um interpretador Python portátil com todas as
dependências já instaladas, rodando o Flask in-process e abrindo numa
janela nativa via `pywebview` (motor Chromium: WebView2 no Windows, Qt
WebEngine no Linux).

Esse pacote é gerado uma vez por um desenvolvedor (precisa de internet, só
nessa etapa) e depois distribuído como um único arquivo `.zip`/`.tar.gz`
que o usuário final descompacta e instala sem precisar de internet nem de
privilégios administrativos.

**1. Gerar o pacote** (na máquina do desenvolvedor, uma vez por versão):

```powershell
# Windows
.\packaging\build_windows.ps1
```
```bash
# Linux
./packaging/build_linux.sh
```

No Windows, `build_windows.ps1` também compila um **instalador de verdade**
com [Inno Setup](https://jrsoft.org/isinfo.php) (grátis) — assistente com
tela de boas-vindas, barra de progresso, aparece em "Aplicativos e
recursos" com desinstalador. Se o Inno Setup não estiver instalado, o
script instala sozinho via `winget install --id JRSoftware.InnoSetup -e`
(sem admin) e você só precisa rodar o build de novo.

O build gera:
- `dist/OpsVenda-Setup.exe` — **instalador recomendado pro usuário final**
  (Windows). Um duplo clique, assistente normal, cria atalho na Área de
  Trabalho e no menu Iniciar, sem admin.
- `dist/OpsVenda-windows-x64.zip` — versão portátil alternativa: descompacta
  e roda `Instalar OpsVenda.bat` de dentro da pasta.
- `dist/OpsVenda-linux-x64.tar.gz` (via `build_linux.sh`) — descompacta e
  roda `Instalar OpsVenda.sh`.

Em ambos os casos, no primeiro uso o app abre direto na tela de
configuração inicial para criar o usuário administrador.

## Estrutura do projeto

```
app/
  __init__.py       # application factory: cria o Flask app e registra tudo
  config.py         # configurações (banco, chaves, uploads)
  cli.py            # comandos flask CLI (create-admin)
  extensions.py     # instâncias das extensões (db, login_manager, csrf, migrate)
  blueprints/        # rotas HTTP, uma pasta por domínio (auth, setup, sales, products, ...)
  models/           # tabelas do banco (SQLAlchemy)
  services/         # regras de negócio (pricing, import/export de CSV)
  templates/        # HTML (Jinja2)
  static/           # CSS/JS
wsgi.py             # ponto de entrada WSGI (usado por `flask run` e pelo Gunicorn)
run_desktop.py      # launcher desktop (pywebview) - sobe o backend embutido ou aponta pra um já rodando (--url)
packaging/          # scripts de build dos pacotes standalone (Windows/Linux) e seus instaladores
tests/              # testes pytest
```

## Licença

Distribuído sob a licença [MIT](LICENSE).
