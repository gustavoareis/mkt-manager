# Gerenciador de Campanhas

Uma aplicação web completa para gerenciar campanhas de marketing, rastrear cliques e automatizar processos com integração ao banco de dados PostgreSQL, Python Flask, N8N e Trello.

## Funcionalidades

- **Gerenciamento de Campanhas**: Criação, edição e exclusão de campanhas.
- **Templates Personalizados**: Adicione templates com múltiplos links rastreáveis.
- **Rastreamento de Cliques**: Capture informações detalhadas sobre os cliques, incluindo geolocalização, navegador e referer.
- **Integração com Trello**: Sincronize informações de clientes armazenadas no Trello com o banco de dados.
- **Banco de Dados**: PostgreSQL (via Supabase) para armazenar campanhas, templates, links e cliques.
- **Automatização**: Integração com N8N para automação de processos.
- **Segurança**: Autenticação de usuário com sessões protegidas.

## Tecnologias Utilizadas

- **Backend**: Python, Flask
- **Banco de Dados**: PostgreSQL (via Supabase)
- **Frontend**: HTML, CSS (Bootstrap)
- **Automação**: N8N
- **Geolocalização**: Biblioteca `geocoder` e Google Maps
- **Integração com Trello**: Sincronização de dados de clientes

## Requisitos

- Python 3.8+
- PostgreSQL
- Supabase (URL e chave de API)
- Trello (chave e token de API)
- N8N (opcional para automação)
- Dependências do Python (listadas no arquivo `requirements.txt`)

## Instalação

1. Clone o repositório:
   ```bash
   git clone https://github.com/seu-usuario/seu-repositorio.git
   cd seu-repositorio
   ```

2. Crie e ative um ambiente virtual:
   ```bash
   python -m venv venv
   venv\Scripts\activate  # No Windows
   source venv/bin/activate  # No Linux/Mac
   ```

3. Instale as dependências:
   ```bash
   pip install -r requirements.txt
   ```

4. Configure as variáveis de ambiente:
   Crie um arquivo `.env` na raiz do projeto adicione:
   ```env
   SECRET_KEY=sua_chave_secreta
   FLASK_BASE_DOMAIN=http://127.0.0.1:5002
   SUPABASE_URL=sua_url_supabase
   SUPABASE_KEY=sua_chave_supabase
   ADMIN_USERNAME=admin
   ADMIN_PASSWORD=senha
   IPINFO_TOKEN=seu_token_ipinfo (opcional)
   TRELLO_API_KEY=sua_chave_trello
   TRELLO_API_TOKEN=seu_token_trello
   ```

5. Execute a aplicação:
   ```bash
   python app.py
   ```

6. Acesse no navegador:
   ```
   http://127.0.0.1:5002
   ```

## Integração com Trello

- As informações dos clientes são armazenadas no Trello.
- Um programa separado sincroniza os dados do Trello com o banco de dados PostgreSQL.
- Certifique-se de configurar as variáveis `TRELLO_API_KEY` e `TRELLO_API_TOKEN` no arquivo `.env`.

## Estrutura do Projeto

- **`app.py`**: Arquivo principal da aplicação Flask.
- **`templates/`**: Contém os arquivos HTML para as páginas.
- **`static/`**: Arquivos estáticos (CSS, JS, imagens).
- **`README.md`**: Documentação do projeto.

## Funcionalidades Detalhadas

### 1. Gerenciamento de Campanhas
- Crie campanhas com nome, observações e tipo (Email ou WhatsApp).
- Adicione templates com fases e links rastreáveis.
- Edite ou exclua campanhas existentes.

### 2. Rastreamento de Cliques
- Cada link rastreável captura:
  - Data e hora do clique.
  - IP, navegador, plataforma e referer.
  - Localização geográfica (cidade, estado, país).
- Visualize os cliques na página de relatórios.

### 3. Integração com Trello
- Sincronize informações de clientes armazenadas em quadros do Trello.
- Utilize essas informações para personalizar campanhas.

### 4. Segurança
- Login protegido por senha.
- Sessões expiram após 1 hora de inatividade.

## Contribuição

Contribuições são bem-vindas! Siga os passos abaixo:

1. Faça um fork do repositório.
2. Crie uma branch para sua feature/bugfix:
   ```bash
   git checkout -b minha-feature
   ```
3. Faça commit das suas alterações:
   ```bash
   git commit -m "Descrição da alteração"
   ```
4. Envie para o repositório remoto:
   ```bash
   git push origin minha-feature
   ```
5. Abra um Pull Request.

## Licença

Este projeto está sob a licença [MIT](LICENSE).

---

**Autor**: Gustavo Almeida

