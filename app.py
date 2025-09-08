# Importa as bibliotecas necessárias para o projeto web
from flask import Flask, request, redirect, render_template, session, url_for, flash, jsonify
import os
from datetime import datetime, timedelta
from supabase import create_client, Client
import geocoder
from dotenv import load_dotenv
import requests

# Carrega as variáveis de ambiente do arquivo .env
load_dotenv()

# --- Configuração do Aplicativo ---
class Config:
    """Classe de configuração que armazena todas as variáveis de ambiente e constantes."""
    SECRET_KEY = os.getenv("SECRET_KEY")
    BASE_DOMAIN = os.getenv("FLASK_BASE_DOMAIN", "http://127.0.0.1:5002")
    TRACKING_PATH_PREFIX = "r"
    SUPABASE_URL = os.getenv("SUPABASE_URL")
    SUPABASE_KEY = os.getenv("SUPABASE_KEY")
    IPINFO_TOKEN = os.getenv("IPINFO_TOKEN", None)
    TRELLO_API_KEY = os.getenv("TRELLO_API_KEY")
    TRELLO_TOKEN = os.getenv("TRELLO_TOKEN")
    TRELLO_BOARD_IDS = ['kFrWQqjm', 'tXcXz9Pl', 'WXyXBHeb', 'e30OHAsU']

# --- Funções Auxiliares ---

def get_supabase_client() -> Client:
    """Cria e retorna um cliente Supabase, verificando se as variáveis de ambiente estão configuradas."""
    try:
        if not Config.SUPABASE_URL or not Config.SUPABASE_KEY:
            print("ERRO: As variáveis de ambiente SUPABASE_URL e SUPABASE_KEY não foram definidas.")
            return None
        return create_client(Config.SUPABASE_URL, Config.SUPABASE_KEY)
    except Exception as e:
        print(f"Erro ao conectar ao Supabase: {e}")
        return None

def get_trello_board_details(board_id):
    """Busca os detalhes (nome) de um quadro (board) específico do Trello usando a API."""
    url = f"https://api.trello.com/1/boards/{board_id}"
    params = {'key': Config.TRELLO_API_KEY, 'token': Config.TRELLO_TOKEN, 'fields': 'name'}
    try:
        response = requests.get(url, params=params)
        response.raise_for_status() # Lança um erro se a requisição falhar
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Erro ao buscar board do Trello {board_id}: {e}")
        return None

def get_trello_lists_for_board(board_id):
    """Busca todas as listas de um quadro específico do Trello."""
    url = f"https://api.trello.com/1/boards/{board_id}/lists"
    params = {'key': Config.TRELLO_API_KEY, 'token': Config.TRELLO_TOKEN, 'fields': 'name,id'}
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Erro ao buscar listas do Trello para o board {board_id}: {e}")
        return []

def get_geolocation_from_ip(ip_address):
    """Obtém a geolocalização (cidade, estado, país) de um endereço IP."""
    cidade = estado = pais = maps_link = 'N/A'
    try:
        # Ignora IPs locais para evitar erros
        if ip_address in ['127.0.0.1', 'localhost'] or ip_address.startswith(('192.168.', '10.', '172.16.')):
            return {'cidade': cidade, 'estado': estado, 'pais': pais, 'maps_link': maps_link}
        
        # Usa a biblioteca geocoder para buscar informações do IP
        g = geocoder.ip(ip_address)
        if g.ok:
            cidade = g.city or 'N/A'
            estado = g.state or 'N/A'
            pais = g.country or 'N/A'
            if g.latlng and len(g.latlng) == 2:
                # Cria um link para o Google Maps se as coordenadas existirem
                maps_link = f"http://googleusercontent.com/maps/google.com/3{g.latlng[0]},{g.latlng[1]}"
    except Exception as geo_e:
        print(f"Erro inesperado ao obter geolocalização para IP {ip_address}: {geo_e}")
    return {'cidade': cidade, 'estado': estado, 'pais': pais, 'maps_link': maps_link}

# --- Inicialização do Flask ---

app = Flask(__name__)
app.config.from_object(Config) # Carrega as configurações da classe Config
app.permanent_session_lifetime = timedelta(hours=1) # Define o tempo de vida da sessão

# --- Middlewares (Executado antes de cada requisição) ---

@app.before_request
def protect_routes():
    """Protege as rotas, redirecionando para a página de login se o usuário não estiver autenticado."""
    is_tracking_route = request.path.startswith(f'/{Config.TRACKING_PATH_PREFIX}/')
    is_public_route = request.path in ['/login', '/logout'] or request.path.startswith('/get_trello_lists')
    
    # Se a rota não for de rastreamento ou pública E o usuário não estiver logado, redireciona para o login
    if not is_tracking_route and not is_public_route and not session.get('logged_in'):
        return redirect(url_for('login'))

# --- Rotas (URLs do Aplicativo) ---

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Rota para a página de login. Processa a autenticação do usuário."""
    if request.method == 'POST':
        admin_user, admin_pass = os.getenv("ADMIN_USERNAME"), os.getenv("ADMIN_PASSWORD")
        if request.form['username'] == admin_user and request.form['password'] == admin_pass:
            session['logged_in'], session['username'] = True, admin_user # Define a sessão como logada
            return redirect(url_for('index')) # Redireciona para a página principal
        else:
            flash("Usuário ou senha inválidos.", "danger") # Exibe uma mensagem de erro
    return render_template('login.html')

@app.route('/logout')
def logout():
    """Limpa a sessão e desloga o usuário."""
    session.clear()
    return redirect(url_for('login'))

@app.route('/get_trello_lists/<board_id>')
def get_trello_lists(board_id):
    """Rota para buscar listas de um quadro Trello via AJAX, usada no frontend."""
    if not session.get('logged_in'):
        return jsonify({"error": "Não autorizado"}), 401
    lists = get_trello_lists_for_board(board_id)
    return jsonify(lists)

@app.route('/', methods=['GET', 'POST'])
def index():
    """Página principal para criar e visualizar campanhas."""
    supabase = get_supabase_client()
    if not supabase:
        flash("Erro ao conectar com o banco de dados.", "danger")
        return render_template("index.html", todas_campanhas=[], trello_boards=[])

    if request.method == 'POST':
        # Processa o formulário de criação de uma nova campanha
        try:
            # Coleta os dados da campanha do formulário
            dados_campanha = {
                "campanha": request.form.get("campanha"), "observacoes": request.form.get("observacoes"),
                "data_criacao": datetime.now().date().isoformat(), "tipo_campanha": request.form.get("tipo_campanha"),
                "trello_board_id": request.form.get("trello_board"), "trello_list_id": request.form.get("trello_list"),
                "periodicidade_cron": request.form.get("periodicidade_cron")
            }
            if not dados_campanha["campanha"] or not dados_campanha["tipo_campanha"]:
                flash("Nome e tipo da campanha são obrigatórios!", "danger")
                return redirect(url_for("index"))
            
            # Insere a nova campanha no Supabase
            resp = supabase.from_("campanhas").insert(dados_campanha).execute()
            id_campanha, campanha_nome = resp.data[0]["id_campanha"], dados_campanha["campanha"]
            
            # Processa e salva os templates e links
            template_index = 1
            while f"template_{template_index}" in request.form:
                corpo, assunto, fase = request.form.get(f"template_{template_index}"), request.form.get(f"assunto_{template_index}"), request.form.get(f"fase_{template_index}")
                if corpo and fase:
                    resp_t = supabase.from_("templates").insert({"id_campanha": id_campanha, "assunto": assunto, "corpo": corpo, "fase": int(fase)}).execute()
                    id_template = resp_t.data[0]["id_template"]
                    
                    # Cria e insere os links rastreáveis
                    link_index = 1
                    while f"link_{template_index}_{link_index}" in request.form:
                        url_destino = request.form.get(f"link_{template_index}_{link_index}")
                        if url_destino:
                            # Cria o link mascarado para rastreamento
                            rastreavel = f"{campanha_nome.replace(' ', '_')}_T{template_index}_L{link_index}"
                            mascarado = f"{Config.BASE_DOMAIN}/{Config.TRACKING_PATH_PREFIX}/{rastreavel}"
                            
                            supabase.from_("links").insert({"base_link": mascarado, "url_destino": url_destino, "placeholder_link": f"[link{link_index}]", "id_campanha": id_campanha, "id_template": id_template}).execute()
                        link_index += 1
                template_index += 1
            flash("Campanha criada com sucesso!", "success")
        except Exception as e:
            print(f"Erro ao salvar campanha: {e}")
            flash("Erro ao salvar campanha.", "danger")
        return redirect(url_for("index"))

    # Processa o método GET para exibir as campanhas existentes
    campanhas, trello_boards = [], []
    try:
        # Busca todas as campanhas do banco de dados
        resp = supabase.from_("campanhas").select("id_campanha, campanha, tipo_campanha, data_criacao").order("id_campanha", desc=True).execute()
        campanhas = resp.data
        
        # Busca os nomes dos quadros do Trello
        for board_id in Config.TRELLO_BOARD_IDS:
            details = get_trello_board_details(board_id)
            if details:
                trello_boards.append({'id': details['id'], 'name': details['name']})
    except Exception as e:
        print("Erro ao buscar dados para a página inicial:", e)
    return render_template("index.html", todas_campanhas=campanhas, trello_boards=trello_boards)

@app.route('/edit/<int:id_campanha>', methods=['GET', 'POST'])
def edit(id_campanha):
    """Rota para editar uma campanha existente."""
    supabase = get_supabase_client()
    if not supabase:
        flash("Erro ao conectar com o banco de dados.", "danger")
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        # Processa a submissão do formulário de edição
        try:
            # Atualiza os dados da campanha
            dados_para_atualizar = {
                "campanha": request.form.get("campanha"),
                "observacoes": request.form.get("observacoes"),
                "tipo_campanha": request.form.get("tipo_campanha"),
                "trello_board_id": request.form.get("trello_board"),
                "trello_list_id": request.form.get("trello_list"),
                "periodicidade_cron": request.form.get("periodicidade_cron")
            }
            supabase.from_("campanhas").update(dados_para_atualizar).eq("id_campanha", id_campanha).execute()
            campanha_nome = dados_para_atualizar["campanha"]
            
            # Deleta os templates e links antigos para recriá-los
            supabase.from_("links").delete().eq("id_campanha", id_campanha).execute()
            supabase.from_("templates").delete().eq("id_campanha", id_campanha).execute()
            
            # Recria os templates e links (lógica similar à da criação)
            template_index = 1
            while f"template_{template_index}" in request.form:
                corpo, assunto, fase = request.form.get(f"template_{template_index}"), request.form.get(f"assunto_{template_index}"), request.form.get(f"fase_{template_index}")
                if corpo and fase:
                    resp_t = supabase.from_("templates").insert({"id_campanha": id_campanha, "assunto": assunto, "corpo": corpo, "fase": int(fase)}).execute()
                    id_template = resp_t.data[0]["id_template"]
                    
                    link_index = 1
                    while f"link_{template_index}_{link_index}" in request.form:
                        url_destino = request.form.get(f"link_{template_index}_{link_index}")
                        if url_destino:
                            rastreavel = f"{campanha_nome.replace(' ', '_')}_T{template_index}_L{link_index}"
                            mascarado = f"{Config.BASE_DOMAIN}/{Config.TRACKING_PATH_PREFIX}/{rastreavel}"
                            supabase.from_("links").insert({"base_link": mascarado, "url_destino": url_destino, "placeholder_link": f"[link{link_index}]", "id_campanha": id_campanha, "id_template": id_template}).execute()
                        link_index += 1
                template_index += 1
            flash("Campanha atualizada com sucesso!", "success")
            return redirect(url_for('index'))
        except Exception as e:
            print(f"Erro ao atualizar campanha: {e}")
            flash("Ocorreu um erro ao atualizar a campanha.", "danger")
            return redirect(url_for('edit', id_campanha=id_campanha))

    # Processa o método GET para exibir o formulário de edição
    try:
        # Busca a campanha completa com templates e links aninhados
        resp = supabase.from_("campanhas").select("*, templates(*, links(*))").eq("id_campanha", id_campanha).single().execute()
        campanha = resp.data
        if not campanha:
            flash("Campanha não encontrada.", "warning")
            return redirect(url_for('index'))
        
        # Ordena os templates e links para uma exibição consistente
        campanha['templates'].sort(key=lambda t: t['fase'])
        for t in campanha['templates']:
            if t['links']:
                t['links'].sort(key=lambda l: l['placeholder_link'])
        
        # Busca os quadros do Trello para o dropdown
        trello_boards = []
        for board_id in Config.TRELLO_BOARD_IDS:
            details = get_trello_board_details(board_id)
            if details:
                trello_boards.append({'id': details['id'], 'name': details['name']})
        
        return render_template("edit.html", campanha=campanha, trello_boards=trello_boards)
    except Exception as e:
        print(f"Erro ao buscar campanha para edição: {e}")
        flash("Erro ao carregar dados da campanha.", "danger")
        return redirect(url_for('index'))

@app.route('/delete/<int:id_campanha>', methods=['POST'])
def delete(id_campanha):
    """Rota para deletar uma campanha e todos os dados relacionados (templates e links)."""
    supabase = get_supabase_client()
    if not supabase:
        flash("Erro de conexão com o banco de dados.", "danger")
        return redirect(url_for('index'))
    try:
        # Deleta os dados relacionados em cascata
        supabase.from_("links").delete().eq("id_campanha", id_campanha).execute()
        supabase.from_("templates").delete().eq("id_campanha", id_campanha).execute()
        supabase.from_("campanhas").delete().eq("id_campanha", id_campanha).execute()
        flash("Campanha removida com sucesso!", "success")
    except Exception as e:
        print(f"Erro ao remover campanha: {e}")
        flash("Ocorreu um erro ao remover a campanha.", "danger")
    return redirect(url_for('index'))

@app.route('/cliques')
def cliques_page():
    """Página para visualizar todos os cliques registrados."""
    supabase = get_supabase_client()
    if not supabase:
        flash("Erro de conexão com o banco de dados.", "danger")
        return render_template("cliques.html", cliques=[])
    try:
        # Busca os dados de cliques do banco de dados
        resp = supabase.from_("cliques").select("*").order("data_hora", desc=True).execute()
        cliques_data = resp.data
    except Exception as e:
        print(f"Erro ao buscar cliques: {e}")
        flash("Não foi possível carregar os dados dos cliques.", "danger")
        cliques_data = []
    return render_template("cliques.html", cliques=cliques_data)

@app.route(f'/{Config.TRACKING_PATH_PREFIX}/<rastreador>', methods=['GET'])
def rastrear_e_redirecionar(rastreador):
    """Rota de rastreamento. Registra o clique e redireciona o usuário."""
    supabase = get_supabase_client()
    if not supabase: return "Erro interno", 500
    try:
        # Constrói o link completo e busca os dados no Supabase
        base_link_completo = f"{Config.BASE_DOMAIN}/{Config.TRACKING_PATH_PREFIX}/{rastreador}"
        resp = supabase.from_("links").select("url_destino, campanhas(campanha)").eq("base_link", base_link_completo).single().execute()
        link_data = resp.data
        
        if not link_data: return "Link não encontrado", 404
        
        destino, campanha_nome = link_data["url_destino"], link_data["campanhas"]["campanha"]
        
        # Coleta informações do clique (IP, navegador, etc.)
        ip = request.remote_addr
        geo = get_geolocation_from_ip(ip)
        
        # Cria um registro do clique para salvar no banco de dados
        clique = {
            "data_hora": datetime.now().isoformat(), "ip": ip, "navegador": request.user_agent.browser,
            "plataforma": request.user_agent.platform, "campanha": campanha_nome, "link_original": destino,
            "referer": request.referrer or "Direto", "cidade": geo["cidade"], "estado": geo["estado"],
            "pais": geo["pais"], "maps_link": geo["maps_link"], "observacoes": f"Rastreamento {campanha_nome}"
        }
        
        # Salva o registro do clique no Supabase
        supabase.from_("cliques").insert([clique]).execute()
        
        # Redireciona o usuário para o link de destino
        return redirect(destino, code=302)
    except Exception as e:
        print("Erro rastrear:", e)
        return "Erro no sistema de rastreamento", 500

# --- Execução do Servidor ---

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5002) # Inicia o servidor web em modo de depuração