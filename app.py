from flask import Flask, request, redirect, render_template, jsonify, session, url_for, flash
import os
from datetime import datetime, timedelta
from supabase import create_client, Client
import geocoder

class Config:
    SECRET_KEY = os.urandom(24)
    
    BASE_DOMAIN = os.getenv("FLASK_BASE_DOMAIN", "https://mkt.ocenergy.com.br")
    TRACKING_PATH_PREFIX = "r"
    
    SUPABASE_URL = os.getenv("SUPABASE_URL", "https://api-supabase.ocenergy.com.br")
    SUPABASE_KEY = os.getenv("SUPABASE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJyb2xlIjoic2VydmljZV9yb2xlIiwiaXNzIjoic3VwYWJhc2UiLCJzdWIiOiJzZXJ2aWNlX3JvbGUiLCJleHAiOjIwNzA5MDUwNzF9.ntm52yom-3uF2de_H-mohuyMEv21JnO3QwDiZB0Gc68")

    IPINFO_TOKEN = os.getenv("IPINFO_TOKEN", None)

def get_supabase_client() -> Client:
    try:
        supabase_client: Client = create_client(Config.SUPABASE_URL, Config.SUPABASE_KEY)
        return supabase_client
    except Exception as e:
        print(f"Erro ao conectar ao Supabase: {e}")
        return None

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

app = Flask(__name__)
app.config.from_object(Config)
app.permanent_session_lifetime = timedelta(hours=1)

@app.before_request
def protect_routes():
    is_tracking_route = request.path.startswith(f'/{Config.TRACKING_PATH_PREFIX}/')
    is_public_route = request.path in ['/login', '/logout']
    
    if not is_tracking_route and not is_public_route and not session.get('logged_in'):
        return redirect(url_for('login'))

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

# ==============================================
# CRIAÇÃO DE CAMPANHAS
# ==============================================
@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        nome_campanha_form = request.form.get('campanha')
        observacoes = request.form.get('observacoes')
        fase = request.form.get('fase')
        template = request.form.get('template')
        assunto = request.form.get('assunto') # <-- 1. ADICIONADO: Captura o novo campo
        
        links_originais = [
            request.form.get('link_original_1'),
            request.form.get('link_original_2'),
            request.form.get('link_original_3'),
            request.form.get('link_original_4')
        ]

        if not nome_campanha_form:
            flash("O campo 'Nome da Campanha' é obrigatório!", 'danger')
            return redirect(url_for('index'))
        
        links_originais_validos = [link for link in links_originais if link]
        if not links_originais_validos:
            flash("É necessário preencher pelo menos um campo de link!", 'danger')
            return redirect(url_for('index'))

        links_do_projeto = []
        for i, link_original in enumerate(links_originais_validos, 1):
            campanha_rastreavel = f"{nome_campanha_form.replace(' ', '_')}_{i}"
            link_mascarado = f"{Config.BASE_DOMAIN}/{Config.TRACKING_PATH_PREFIX}/{campanha_rastreavel}"
            links_do_projeto.append({
                'link_original': link_original,
                'link_mascarado': link_mascarado,
                'placeholder': f'[link{i}]'
            })

        supabase = get_supabase_client()
        if not supabase:
            flash("Erro ao conectar com o banco de dados.", 'danger')
            return redirect(url_for('index'))

        try:
            # 1) Inserir na tabela CAMPANHAS
            dados_nova_campanha = {
                'campanha': nome_campanha_form,
                'observacoes': observacoes,
                'data_criacao': datetime.now().date().isoformat()
            }
            response = supabase.from_('campanhas').insert(dados_nova_campanha).execute()
            new_campaign_id = response.data[0]['id_campanha']

            # 2) Inserir na tabela FASES
            tabela2 = {
                'template': template,
                'fase': fase,
                'assunto': assunto, # <-- 2. ADICIONADO: Inclui o assunto para inserção
                'id_campanha': new_campaign_id
            }
            supabase.from_('fases').insert(tabela2).execute()

            # 3) Inserir na tabela LINKS
            dados_links_insert = []
            for link_info in links_do_projeto:
                dados_links_insert.append({
                    'base_link': link_info['link_mascarado'],
                    'placeholder_link': link_info['placeholder'],
                    'url_destino': link_info['link_original'],
                    'id_campanha': new_campaign_id
                })
            supabase.from_('links').insert(dados_links_insert).execute()

            flash("Nova campanha salva com sucesso!", 'success')

        except Exception as e:
            print(f"Erro ao salvar no Supabase: {e}")
            flash(f"Erro ao salvar a campanha: {e}", 'danger')

        return redirect(url_for('index'))

    # --- GET ---
    supabase = get_supabase_client()
    todas_campanhas = []
    if supabase:
        try:
            # Busca campanhas + fases (template, fase)
            # Para exibir o assunto na listagem, você precisaria adicioná-lo aqui também
            # Ex: .select('..., fases(template, fase, assunto)')
            response = supabase.from_('campanhas') \
                .select('id_campanha, campanha, observacoes, data_criacao, fases(template, fase)') \
                .order('campanha') \
                .execute()
            todas_campanhas = response.data
        except Exception as e:
            print(f"Erro ao buscar campanhas: {e}")
            
    return render_template(
        'index.html', 
        todas_campanhas=todas_campanhas
    )

# ==============================================
# RASTREAMENTO E REDIRECIONAMENTO
# ==============================================
@app.route(f'/{Config.TRACKING_PATH_PREFIX}/<campanha_rastreavel>', methods=['GET'])
def rastrear_e_redirecionar(campanha_rastreavel):
    supabase = get_supabase_client()
    if not supabase:
        return 'Erro interno do servidor', 500
    
    try:
        # Busca na tabela LINKS com relação CAMPANHAS
        response = supabase.from_('links') \
            .select('url_destino, id_campanha, campanhas(campanha)') \
            .eq('base_link', f"{Config.BASE_DOMAIN}/{Config.TRACKING_PATH_PREFIX}/{campanha_rastreavel}") \
            .single().execute()

        link_data = response.data
        url_destino = link_data['url_destino']
        campanha_nome = link_data['campanhas']['campanha']

    except Exception as e:
        print(f"Erro ao buscar link no Supabase: {e}")
        return 'Link não reconhecido', 400

    try:
        # Registrar clique
        ip_address = request.remote_addr
        geo_data = get_geolocation_from_ip(ip_address)
        dados_do_clique = {
            'data_hora': datetime.now().isoformat(), 
            'ip': ip_address,
            'navegador': request.user_agent.browser, 
            'plataforma': request.user_agent.platform,
            'os': request.user_agent.platform, 
            'campanha': campanha_nome,
            'link_original': url_destino, 
            'referer': request.referrer or 'Direto',
            'cidade': geo_data['cidade'], 
            'estado': geo_data['estado'], 
            'pais': geo_data['pais'],
            'maps_link': geo_data['Maps_link'],
            'observacoes': f'Rastreamento para a campanha {campanha_nome}'
        }
        supabase.from_('cliques').insert([dados_do_clique]).execute()
    except Exception as e:
        print(f"Erro ao registrar o clique: {e}")

    return redirect(url_destino, code=302)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5002)