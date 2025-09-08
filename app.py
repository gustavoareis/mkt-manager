# ==============================
# IMPORTS
# ==============================
from flask import Flask, request, redirect, render_template, session, url_for, flash, jsonify
import os
from datetime import datetime, timedelta
from supabase import create_client, Client
import geocoder
from dotenv import load_dotenv
import requests

load_dotenv()

# ==============================
# CONFIGURAÇÃO DA APLICAÇÃO
# ==============================
class Config:
    # ... (sem alterações aqui)
    SECRET_KEY = os.getenv("SECRET_KEY")
    BASE_DOMAIN = os.getenv("FLASK_BASE_DOMAIN", "http://127.0.0.1:5002")
    TRACKING_PATH_PREFIX = "r"
    SUPABASE_URL = os.getenv("SUPABASE_URL")
    SUPABASE_KEY = os.getenv("SUPABASE_KEY")
    IPINFO_TOKEN = os.getenv("IPINFO_TOKEN", None)
    TRELLO_API_KEY = os.getenv("TRELLO_API_KEY")
    TRELLO_TOKEN = os.getenv("TRELLO_TOKEN")
    TRELLO_BOARD_IDS = ['kFrWQqjm', 'tXcXz9Pl', 'WXyXBHeb', 'e30OHAsU']

# ==============================
# FUNÇÕES E CLIENTES (sem alterações)
# ==============================
def get_supabase_client() -> Client:
    # ... (código existente)
    try:
        if not Config.SUPABASE_URL or not Config.SUPABASE_KEY:
            print("ERRO: As variáveis de ambiente SUPABASE_URL e SUPABASE_KEY não foram definidas.")
            return None
        return create_client(Config.SUPABASE_URL, Config.SUPABASE_KEY)
    except Exception as e:
        print(f"Erro ao conectar ao Supabase: {e}")
        return None

def get_trello_board_details(board_id):
    # ... (código existente)
    url = f"https://api.trello.com/1/boards/{board_id}"
    params = {'key': Config.TRELLO_API_KEY, 'token': Config.TRELLO_TOKEN, 'fields': 'name'}
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Erro ao buscar board do Trello {board_id}: {e}")
        return None

def get_trello_lists_for_board(board_id):
    # ... (código existente)
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
    # ... (código existente)
    cidade = estado = pais = maps_link = 'N/A'
    try:
        if ip_address in ['127.0.0.1', 'localhost'] or ip_address.startswith(('192.168.', '10.', '172.16.')):
            return {'cidade': cidade, 'estado': estado, 'pais': pais, 'maps_link': maps_link}
        g = geocoder.ip(ip_address)
        if g.ok:
            cidade = g.city or 'N/A'
            estado = g.state or 'N/A'
            pais = g.country or 'N/A'
            if g.latlng and len(g.latlng) == 2:
                maps_link = f"http://googleusercontent.com/maps/google.com/3{g.latlng[0]},{g.latlng[1]}"
    except Exception as geo_e:
        print(f"Erro inesperado ao obter geolocalização para IP {ip_address}: {geo_e}")
    return {'cidade': cidade, 'estado': estado, 'pais': pais, 'maps_link': maps_link}

# ==============================
# INICIALIZAÇÃO E ROTAS (sem alterações até 'edit')
# ==============================
app = Flask(__name__)
app.config.from_object(Config)
app.permanent_session_lifetime = timedelta(hours=1)

@app.before_request
def protect_routes():
    # ... (código existente)
    is_tracking_route = request.path.startswith(f'/{Config.TRACKING_PATH_PREFIX}/')
    is_public_route = request.path in ['/login', '/logout'] or request.path.startswith('/get_trello_lists')
    if not is_tracking_route and not is_public_route and not session.get('logged_in'):
        return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    # ... (código existente)
    if request.method == 'POST':
        admin_user, admin_pass = os.getenv("ADMIN_USERNAME"), os.getenv("ADMIN_PASSWORD")
        if request.form['username'] == admin_user and request.form['password'] == admin_pass:
            session['logged_in'], session['username'] = True, admin_user
            return redirect(url_for('index'))
        else:
            flash("Usuário ou senha inválidos.", "danger")
    return render_template('login.html')

@app.route('/logout')
def logout():
    # ... (código existente)
    session.clear()
    return redirect(url_for('login'))

@app.route('/get_trello_lists/<board_id>')
def get_trello_lists(board_id):
    # ... (código existente)
    if not session.get('logged_in'):
        return jsonify({"error": "Não autorizado"}), 401
    lists = get_trello_lists_for_board(board_id)
    return jsonify(lists)

@app.route('/', methods=['GET', 'POST'])
def index():
    # ... (código existente)
    supabase = get_supabase_client()
    if not supabase:
        flash("Erro ao conectar com o banco de dados.", "danger")
        return render_template("index.html", todas_campanhas=[], trello_boards=[])
    if request.method == 'POST':
        try:
            dados_campanha = {
                "campanha": request.form.get("campanha"), "observacoes": request.form.get("observacoes"),
                "data_criacao": datetime.now().date().isoformat(), "tipo_campanha": request.form.get("tipo_campanha"),
                "trello_board_id": request.form.get("trello_board"), "trello_list_id": request.form.get("trello_list"),
                "periodicidade_cron": request.form.get("periodicidade_cron")
            }
            if not dados_campanha["campanha"] or not dados_campanha["tipo_campanha"]:
                flash("Nome e tipo da campanha são obrigatórios!", "danger")
                return redirect(url_for("index"))
            resp = supabase.from_("campanhas").insert(dados_campanha).execute()
            id_campanha, campanha_nome = resp.data[0]["id_campanha"], dados_campanha["campanha"]
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
            flash("Campanha criada com sucesso!", "success")
        except Exception as e:
            print(f"Erro ao salvar campanha: {e}")
            flash("Erro ao salvar campanha.", "danger")
        return redirect(url_for("index"))
    campanhas, trello_boards = [], []
    try:
        resp = supabase.from_("campanhas").select("id_campanha, campanha, tipo_campanha, data_criacao").order("id_campanha", desc=True).execute()
        campanhas = resp.data
        for board_id in Config.TRELLO_BOARD_IDS:
            details = get_trello_board_details(board_id)
            if details:
                trello_boards.append({'id': details['id'], 'name': details['name']})
    except Exception as e:
        print("Erro ao buscar dados para a página inicial:", e)
    return render_template("index.html", todas_campanhas=campanhas, trello_boards=trello_boards)

# ==============================
# ROTA DE EDIÇÃO (ALTERADA)
# ==============================
@app.route('/edit/<int:id_campanha>', methods=['GET', 'POST'])
def edit(id_campanha):
    supabase = get_supabase_client()
    if not supabase:
        flash("Erro ao conectar com o banco de dados.", "danger")
        return redirect(url_for('index'))

    if request.method == 'POST':
        try:
            # Pega todos os dados do formulário, incluindo os novos
            dados_para_atualizar = {
                "campanha": request.form.get("campanha"),
                "observacoes": request.form.get("observacoes"),
                "tipo_campanha": request.form.get("tipo_campanha"),
                "trello_board_id": request.form.get("trello_board"),
                "trello_list_id": request.form.get("trello_list"),
                "periodicidade_cron": request.form.get("periodicidade_cron")
            }
            supabase.from_("campanhas").update(dados_para_atualizar).eq("id_campanha", id_campanha).execute()
            
            # A lógica de "deletar e recriar" templates e links continua
            campanha_nome = dados_para_atualizar["campanha"]
            supabase.from_("links").delete().eq("id_campanha", id_campanha).execute()
            supabase.from_("templates").delete().eq("id_campanha", id_campanha).execute()
            
            template_index = 1
            while f"template_{template_index}" in request.form:
                # ... (lógica de salvar templates e links, sem alterações)
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

    # GET: Busca os dados da campanha E a lista de boards do Trello
    try:
        resp = supabase.from_("campanhas").select("*, templates(*, links(*))").eq("id_campanha", id_campanha).single().execute()
        campanha = resp.data
        if not campanha:
            flash("Campanha não encontrada.", "warning")
            return redirect(url_for('index'))
        
        # Ordena templates e links para exibição
        campanha['templates'].sort(key=lambda t: t['fase'])
        for t in campanha['templates']:
            if t['links']:
                t['links'].sort(key=lambda l: l['placeholder_link'])

        # Busca a lista de boards do Trello para popular o seletor
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

# ... (O resto do seu app.py, com delete, cliques, e rastrear, continua aqui sem alterações)
@app.route('/delete/<int:id_campanha>', methods=['POST'])
def delete(id_campanha):
    supabase = get_supabase_client()
    if not supabase:
        flash("Erro de conexão com o banco de dados.", "danger")
        return redirect(url_for('index'))
    try:
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
    supabase = get_supabase_client()
    if not supabase:
        flash("Erro de conexão com o banco de dados.", "danger")
        return render_template("cliques.html", cliques=[])
    try:
        resp = supabase.from_("cliques").select("*").order("data_hora", desc=True).execute()
        cliques_data = resp.data
    except Exception as e:
        print(f"Erro ao buscar cliques: {e}")
        flash("Não foi possível carregar os dados dos cliques.", "danger")
        cliques_data = []
    return render_template("cliques.html", cliques=cliques_data)

@app.route(f'/{Config.TRACKING_PATH_PREFIX}/<rastreador>', methods=['GET'])
def rastrear_e_redirecionar(rastreador):
    supabase = get_supabase_client()
    if not supabase: return "Erro interno", 500
    try:
        base_link_completo = f"{Config.BASE_DOMAIN}/{Config.TRACKING_PATH_PREFIX}/{rastreador}"
        resp = supabase.from_("links").select("url_destino, campanhas(campanha)").eq("base_link", base_link_completo).single().execute()
        link_data = resp.data
        if not link_data: return "Link não encontrado", 404
        destino, campanha_nome = link_data["url_destino"], link_data["campanhas"]["campanha"]
        ip = request.remote_addr
        geo = get_geolocation_from_ip(ip)
        clique = {
            "data_hora": datetime.now().isoformat(), "ip": ip, "navegador": request.user_agent.browser,
            "plataforma": request.user_agent.platform, "campanha": campanha_nome, "link_original": destino,
            "referer": request.referrer or "Direto", "cidade": geo["cidade"], "estado": geo["estado"],
            "pais": geo["pais"], "maps_link": geo["maps_link"], "observacoes": f"Rastreamento {campanha_nome}"
        }
        supabase.from_("cliques").insert([clique]).execute()
        return redirect(destino, code=302)
    except Exception as e:
        print("Erro rastrear:", e)
        return "Erro no sistema de rastreamento", 500

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5002)