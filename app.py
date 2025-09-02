from flask import Flask, request, redirect, render_template, session, url_for, flash
import os
from datetime import datetime, timedelta
from supabase import create_client, Client
import geocoder

# ==============================
# CONFIG
# ==============================
class Config:
    SECRET_KEY = os.urandom(24)
    BASE_DOMAIN = os.getenv("FLASK_BASE_DOMAIN", "https://mkt.ocenergy.com.br")
    TRACKING_PATH_PREFIX = "r"
    SUPABASE_URL = os.getenv("SUPABASE_URL", "https://api-supabase.ocenergy.com.br")
    SUPABASE_KEY = os.getenv("SUPABASE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJyb2xlIjoic2VydmljZV9yb2xlIiwiaXNzIjoic3VwYWJhc2UiLCJzdWIiOiJzZXJ2aWNlX3JvbGUiLCJleHAiOjIwNzA5MDUwNzF9.ntm52yom-3uF2de_H-mohuyMEv21JnO3QwDiZB0Gc68")
    IPINFO_TOKEN = os.getenv("IPINFO_TOKEN", None)

# ==============================
# SUPABASE
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
    cidade = estado = pais = Maps_link = 'N/A'
    try:
        if ip_address in ['127.0.0.1', 'localhost'] or ip_address.startswith(('192.168.', '10.', '172.16.')):
            return {'cidade': cidade, 'estado': estado, 'pais': pais, 'Maps_link': Maps_link}
        g = geocoder.ip(ip_address)
        if g.ok:
            cidade = g.city or 'N/A'
            estado = g.state or 'N/A'
            pais = g.country or 'N/A'
            if g.latlng and len(g.latlng) == 2:
                Maps_link = f'https://www.google.com/maps?q={g.latlng[0]},{g.latlng[1]}'
    except Exception as geo_e:
        print(f"Erro inesperado ao obter geolocalização para IP {ip_address}: {geo_e}")
    return {'cidade': cidade, 'estado': estado, 'pais': pais, 'Maps_link': Maps_link}

# ==============================
# FLASK APP
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
    # Adicionamos a rota de edição às rotas que precisam de login
    is_public_route = request.path in ['/login', '/logout']
    if not is_tracking_route and not is_public_route and not session.get('logged_in'):
        return redirect(url_for('login'))

# ==============================
# LOGIN / LOGOUT
# ==============================
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if request.form['username'] == "admin" and request.form['password'] == "admin":
            session['logged_in'] = True
            session['username'] = "admin"
            return redirect(url_for('index'))
        else:
            flash("Usuário ou senha inválidos.", "danger")
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# ==============================
# INDEX / CRIAR CAMPANHA
# ==============================
@app.route('/', methods=['GET', 'POST'])
def index():
    supabase = get_supabase_client()
    if not supabase:
        flash("Erro ao conectar com o banco de dados.", "danger")
        return render_template("index.html", todas_campanhas=[])

    if request.method == 'POST':
        try:
            campanha_nome = request.form.get("campanha")
            observacoes = request.form.get("observacoes")
            tipo_campanha = request.form.get("tipo_campanha")

            if not campanha_nome or not tipo_campanha:
                flash("Nome e tipo da campanha são obrigatórios!", "danger")
                return redirect(url_for("index"))

            dados_campanha = {
                "campanha": campanha_nome,
                "observacoes": observacoes,
                "data_criacao": datetime.now().date().isoformat(),
                "tipo_campanha": tipo_campanha
            }
            resp = supabase.from_("campanhas").insert(dados_campanha).execute()
            id_campanha = resp.data[0]["id_campanha"]

            template_index = 1
            while f"template_{template_index}" in request.form:
                corpo = request.form.get(f"template_{template_index}")
                assunto = request.form.get(f"assunto_{template_index}")
                fase = request.form.get(f"fase_{template_index}")

                if corpo and fase:
                    resp_t = supabase.from_("templates").insert({
                        "id_campanha": id_campanha,
                        "assunto": assunto,
                        "corpo": corpo,
                        "fase": int(fase)
                    }).execute()
                    id_template = resp_t.data[0]["id_template"]

                    link_index = 1
                    while f"link_{template_index}_{link_index}" in request.form:
                        url_destino = request.form.get(f"link_{template_index}_{link_index}")
                        if url_destino:
                            rastreavel = f"{campanha_nome.replace(' ', '_')}_T{template_index}_L{link_index}"
                            mascarado = f"{Config.BASE_DOMAIN}/{Config.TRACKING_PATH_PREFIX}/{rastreavel}"
                            supabase.from_("links").insert({
                                "base_link": mascarado,
                                "url_destino": url_destino,
                                "placeholder_link": f"[link{link_index}]",
                                "id_campanha": id_campanha,
                                "id_template": id_template
                            }).execute()
                        link_index += 1
                template_index += 1
            flash("Campanha criada com sucesso!", "success")
        except Exception as e:
            print(f"Erro ao salvar campanha: {e}")
            flash("Erro ao salvar campanha.", "danger")
        return redirect(url_for("index"))

    # GET -> listar campanhas
    campanhas = []
    try:
        # A query aqui não precisa ser tão complexa, só para a listagem
        resp = supabase.from_("campanhas").select("id_campanha, campanha, tipo_campanha, data_criacao").order("id_campanha", desc=True).execute()
        campanhas = resp.data
    except Exception as e:
        print("Erro ao buscar campanhas:", e)

    return render_template("index.html", todas_campanhas=campanhas)

# ==============================
# EDITAR CAMPANHA
# ==============================
@app.route('/edit/<int:id_campanha>', methods=['GET', 'POST'])
def edit(id_campanha):
    supabase = get_supabase_client()
    if not supabase:
        flash("Erro ao conectar com o banco de dados.", "danger")
        return redirect(url_for('index'))

    if request.method == 'POST':
        try:
            campanha_nome = request.form.get("campanha")
            observacoes = request.form.get("observacoes")
            tipo_campanha = request.form.get("tipo_campanha")
            
            supabase.from_("campanhas").update({
                "campanha": campanha_nome,
                "observacoes": observacoes,
                "tipo_campanha": tipo_campanha
            }).eq("id_campanha", id_campanha).execute()

            supabase.from_("links").delete().eq("id_campanha", id_campanha).execute()
            supabase.from_("templates").delete().eq("id_campanha", id_campanha).execute()

            template_index = 1
            while f"template_{template_index}" in request.form:
                corpo = request.form.get(f"template_{template_index}")
                assunto = request.form.get(f"assunto_{template_index}")
                fase = request.form.get(f"fase_{template_index}")

                if corpo and fase:
                    resp_t = supabase.from_("templates").insert({
                        "id_campanha": id_campanha,
                        "assunto": assunto,
                        "corpo": corpo,
                        "fase": int(fase)
                    }).execute()
                    id_template = resp_t.data[0]["id_template"]

                    link_index = 1
                    while f"link_{template_index}_{link_index}" in request.form:
                        url_destino = request.form.get(f"link_{template_index}_{link_index}")
                        if url_destino:
                            rastreavel = f"{campanha_nome.replace(' ', '_')}_T{template_index}_L{link_index}"
                            mascarado = f"{Config.BASE_DOMAIN}/{Config.TRACKING_PATH_PREFIX}/{rastreavel}"
                            supabase.from_("links").insert({
                                "base_link": mascarado,
                                "url_destino": url_destino,
                                "placeholder_link": f"[link{link_index}]",
                                "id_campanha": id_campanha,
                                "id_template": id_template
                            }).execute()
                        link_index += 1
                template_index += 1
            
            flash("Campanha atualizada com sucesso!", "success")
            return redirect(url_for('index'))

        except Exception as e:
            print(f"Erro ao atualizar campanha: {e}")
            flash("Ocorreu um erro ao atualizar a campanha.", "danger")
            return redirect(url_for('edit', id_campanha=id_campanha))
    
    try:
        resp = supabase.from_("campanhas").select("*, templates(*, links(*))").eq("id_campanha", id_campanha).single().execute()
        campanha = resp.data
        if not campanha:
            flash("Campanha não encontrada.", "warning")
            return redirect(url_for('index'))
            
        campanha['templates'].sort(key=lambda t: t['fase'])
        for t in campanha['templates']:
            t['links'].sort(key=lambda l: l['placeholder_link'])

        return render_template("edit.html", campanha=campanha)
    except Exception as e:
        print(f"Erro ao buscar campanha para edição: {e}")
        flash("Erro ao carregar dados da campanha.", "danger")
        return redirect(url_for('index'))

# ==============================
# TRACKING
# ==============================
@app.route(f'/{Config.TRACKING_PATH_PREFIX}/<rastreador>', methods=['GET'])
def rastrear_e_redirecionar(rastreador):
    supabase = get_supabase_client()
    if not supabase:
        return "Erro interno", 500

    try:
        resp = supabase.from_("links").select("url_destino, campanhas(campanha)").eq("base_link", f"{Config.BASE_DOMAIN}/{Config.TRACKING_PATH_PREFIX}/{rastreador}").single().execute()
        link_data = resp.data
        if not link_data:
            return "Link não encontrado", 404

        destino = link_data["url_destino"]
        campanha_nome = link_data["campanhas"]["campanha"]

        ip = request.remote_addr
        geo = get_geolocation_from_ip(ip)
        clique = {
            "data_hora": datetime.now().isoformat(),
            "ip": ip,
            "navegador": request.user_agent.browser,
            "plataforma": request.user_agent.platform,
            "campanha": campanha_nome,
            "link_original": destino,
            "referer": request.referrer or "Direto",
            "cidade": geo["cidade"],
            "estado": geo["estado"],
            "pais": geo["pais"],
            "maps_link": geo["Maps_link"],
            "observacoes": f"Rastreamento {campanha_nome}"
        }
        supabase.from_("cliques").insert([clique]).execute()

        return redirect(destino, code=302)
    except Exception as e:
        print("Erro rastrear:", e)
        return "Erro no rastreamento", 500

# ==============================
# RUN
# ==============================
if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5002)