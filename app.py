from flask import Flask, request, redirect, render_template, session, url_for, flash
import os
from datetime import datetime, timedelta
from supabase import create_client, Client
import geocoder

# ==============================
# CONFIGURAÇÕES
# ==============================
class Config:
    SECRET_KEY = os.urandom(24)
    BASE_DOMAIN = os.getenv("FLASK_BASE_DOMAIN", "https://mkt.ocenergy.com.br")
    TRACKING_PATH_PREFIX = "r"
    SUPABASE_URL = os.getenv("SUPABASE_URL", "https://api-supabase.ocenergy.com.br")
    SUPABASE_KEY = os.getenv("SUPABASE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJyb2xlIjoic2VydmljZV9yb2xlIiwiaXNzIjoic3VwYWJhc2UiLCJzdWIiOiJzZXJ2aWNlX3JvbGUiLCJleHAiOjIwNzA5MDUwNzF9.ntm52yom-3uF2de_H-mohuyMEv21JnO3QwDiZB0Gc68")
    IPINFO_TOKEN = os.getenv("IPINFO_TOKEN", None)

# ==============================
# SUPABASE CLIENT
# ==============================
def get_supabase_client() -> Client:
    try:
        return create_client(Config.SUPABASE_URL, Config.SUPABASE_KEY)
    except Exception as e:
        print(f"Erro ao conectar ao Supabase: {e}")
        return None

# ==============================
# GEOLOCALIZAÇÃO
# ==============================
def get_geolocation_from_ip(ip_address):
    cidade = 'N/A'
    estado = 'N/A'
    pais = 'N/A'
    Maps_link = 'N/A'
    try:
        if ip_address in ['127.0.0.1', 'localhost'] or ip_address.startswith(('192.168.', '10.', '172.16.')):
            return {'cidade': cidade, 'estado': estado, 'pais': pais, 'Maps_link': Maps_link}
        g = geocoder.ip(ip_address)
        if g.ok:
            cidade = g.city or 'N/A'
            estado = g.state or 'N/A'
            pais = g.country or 'N/A'
            if g.latlng and len(g.latlng) == 2:
                Maps_link = f'https://maps.google.com/maps?q={g.latlng[0]},{g.latlng[1]}'
    except Exception as geo_e:
        print(f"Erro inesperado ao obter geolocalização para IP {ip_address}: {geo_e}")
    return {'cidade': cidade, 'estado': estado, 'pais': pais, 'Maps_link': Maps_link}

# ==============================
# APP FLASK
# ==============================
app = Flask(__name__)
app.config.from_object(Config)
app.permanent_session_lifetime = timedelta(hours=1)

# ==============================
# PROTEÇÃO DE ROTAS
# ==============================
@app.before_request
def protect_routes():
    is_tracking_route = request.path.startswith(f'/{Config.TRACKING_PATH_PREFIX}/')
    is_public_route = request.path in ['/login', '/logout']
    if not is_tracking_route and not is_public_route and not session.get('logged_in'):
        return redirect(url_for('login'))

# ==============================
# LOGIN / LOGOUT
# ==============================
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if username == "admin" and password == "admin":
            session['logged_in'] = True
            session['username'] = username
            return redirect(url_for('index'))
        else:
            flash('Usuário ou senha inválidos.', 'danger')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# ==============================
# CRIAÇÃO DE CAMPANHAS
# ==============================
@app.route('/', methods=['GET', 'POST'])
def index():
    supabase = get_supabase_client()
    if not supabase:
        flash("Erro ao conectar com o banco de dados.", 'danger')
        return render_template('index.html', todas_campanhas=[])

    if request.method == 'POST':
        nome_campanha_form = request.form.get('campanha')
        observacoes = request.form.get('observacoes')
        fase_campanha = int(request.form.get('fase'))  # <-- CONVERTIDO PARA INTEIRO
        template = request.form.get('template')
        assunto = request.form.get('assunto')

        links_originais = [
            request.form.get('link_original_1'),
            request.form.get('link_original_2'),
            request.form.get('link_original_3'),
            request.form.get('link_original_4')
        ]

        if not nome_campanha_form:
            flash("O campo 'Nome da Campanha' é obrigatório!", 'danger')
            return redirect(url_for('index'))

        links_validos = [l for l in links_originais if l]
        if not links_validos:
            flash("É necessário preencher pelo menos um link!", 'danger')
            return redirect(url_for('index'))

        links_do_projeto = []
        for i, link in enumerate(links_validos, 1):
            rastreavel = f"{nome_campanha_form.replace(' ', '_')}_{i}"
            mascarado = f"{Config.BASE_DOMAIN}/{Config.TRACKING_PATH_PREFIX}/{rastreavel}"
            links_do_projeto.append({'link_original': link, 'link_mascarado': mascarado, 'placeholder': f'[link{i}]'})

        try:
            # Inserir campanha
            dados_campanha = {'campanha': nome_campanha_form, 'observacoes': observacoes, 'data_criacao': datetime.now().date().isoformat()}
            resp = supabase.from_('campanhas').insert(dados_campanha).execute()
            new_id = resp.data[0]['id_campanha']

            # Inserir fase
            tabela_fase = {'template': template, 'fase_campanha': fase_campanha, 'assunto': assunto, 'id_campanha': new_id}
            supabase.from_('fases').insert(tabela_fase).execute()

            # Inserir links COM fase_links
            dados_links = [
                {
                    'base_link': l['link_mascarado'],
                    'placeholder_link': l['placeholder'],
                    'url_destino': l['link_original'],
                    'id_campanha': new_id,
                    'fase_links': fase_campanha  # <-- CORREÇÃO
                } for l in links_do_projeto
            ]
            supabase.from_('links').insert(dados_links).execute()

            flash("Nova campanha salva com sucesso!", 'success')
        except Exception as e:
            print(f"Erro ao salvar no Supabase: {e}")
            flash(f"Erro ao salvar a campanha: {e}", 'danger')

        return redirect(url_for('index'))

    # --- GET ---
    todas_campanhas = []
    try:
        resp = supabase.from_('campanhas').select('id_campanha, campanha, observacoes, data_criacao, fases(template, fase_campanha, assunto)').order('campanha').execute()
        todas_campanhas = resp.data
    except Exception as e:
        print(f"Erro ao buscar campanhas: {e}")

    return render_template('index.html', todas_campanhas=todas_campanhas)

# ==============================
# RASTREAMENTO
# ==============================
@app.route(f'/{Config.TRACKING_PATH_PREFIX}/<campanha_rastreavel>', methods=['GET'])
def rastrear_e_redirecionar(campanha_rastreavel):
    supabase = get_supabase_client()
    if not supabase:
        return 'Erro interno do servidor', 500
    try:
        resp = supabase.from_('links').select('url_destino, id_campanha, campanhas(campanha)').eq('base_link', f"{Config.BASE_DOMAIN}/{Config.TRACKING_PATH_PREFIX}/{campanha_rastreavel}").single().execute()
        link_data = resp.data
        url_destino = link_data['url_destino']
        campanha_nome = link_data['campanhas']['campanha']
    except Exception as e:
        print(f"Erro ao buscar link no Supabase: {e}")
        return 'Link não reconhecido', 400

    # Registrar clique
    try:
        ip = request.remote_addr
        geo = get_geolocation_from_ip(ip)
        dados_clique = {
            'data_hora': datetime.now().isoformat(),
            'ip': ip,
            'navegador': request.user_agent.browser,
            'plataforma': request.user_agent.platform,
            'os': request.user_agent.platform,
            'campanha': campanha_nome,
            'link_original': url_destino,
            'referer': request.referrer or 'Direto',
            'cidade': geo['cidade'],
            'estado': geo['estado'],
            'pais': geo['pais'],
            'maps_link': geo['Maps_link'],
            'observacoes': f'Rastreamento para a campanha {campanha_nome}'
        }
        supabase.from_('cliques').insert([dados_clique]).execute()
    except Exception as e:
        print(f"Erro ao registrar clique: {e}")

    return redirect(url_destino, code=302)

# ==============================
# RUN
# ==============================
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5002)
