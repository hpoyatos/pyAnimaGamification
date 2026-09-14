import os
import uuid
from datetime import datetime, timedelta
from werkzeug.utils import secure_filename
from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app, jsonify
from extensions import db
from models.aviso import AnimaAviso
from models.quiz import TemaInteresse
from forms.aviso_form import AvisoForm
from utils.discord_api import send_discord_channel_message
from utils.llm_helper import gerar_variacao_aviso
from utils.timezone_helper import get_local_now, LOCAL_TZ

aviso_ui_bp = Blueprint('aviso_ui', __name__, url_prefix='/ui/avisos')

CANAL_NOTICIAS = "1020418519470448650"
CANAL_HUMOR = "1021037661940629524"
CANAL_AVISOS = os.getenv("DISCORD_AVISOS_CHANNEL_ID", "1020488574732357632")

_colunas_verificadas = False

def _garantir_colunas_db():
    global _colunas_verificadas
    if _colunas_verificadas:
        return
    try:
        with db.engine.connect() as conn:
            try:
                conn.execute(db.text("ALTER TABLE anima_avisos ADD COLUMN aviso_categoria VARCHAR(30) NOT NULL DEFAULT 'avisos'"))
                conn.commit()
            except Exception:
                pass
            try:
                conn.execute(db.text("ALTER TABLE anima_avisos ADD COLUMN aviso_imagem_url VARCHAR(500) NULL"))
                conn.commit()
            except Exception:
                pass
            try:
                conn.execute(db.text("""
                    CREATE TABLE IF NOT EXISTS anima_aviso_tema (
                        aviso_id INT NOT NULL,
                        temas_interesse_id INT NOT NULL,
                        PRIMARY KEY (aviso_id, temas_interesse_id),
                        CONSTRAINT fk_aviso_tema_aviso FOREIGN KEY (aviso_id) REFERENCES anima_avisos (aviso_id) ON DELETE CASCADE,
                        CONSTRAINT fk_aviso_tema_tema FOREIGN KEY (temas_interesse_id) REFERENCES anima_temas_interesse (temas_interesse_id) ON DELETE CASCADE
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
                """))
                conn.commit()
            except Exception:
                pass
        _colunas_verificadas = True
    except Exception:
        pass

def _salvar_imagem_upload(file_storage) -> str:
    """Salva o arquivo de imagem/meme enviado no disco e retorna o caminho relativo."""
    if not file_storage or not getattr(file_storage, 'filename', None):
        return None
    raw_name = file_storage.filename.strip()
    if not raw_name:
        return None
    filename = secure_filename(raw_name) or "meme.png"
    unique_name = f"{uuid.uuid4().hex[:8]}_{filename}"
    upload_folder = os.path.join(current_app.root_path, 'static', 'uploads', 'avisos')
    os.makedirs(upload_folder, exist_ok=True)
    full_path = os.path.join(upload_folder, unique_name)
    file_storage.save(full_path)
    return f"/static/uploads/avisos/{unique_name}"

def _inferir_categoria(cat_selecionada, canal_id):
    if cat_selecionada in ['avisos', 'noticias', 'humor']:
        return cat_selecionada
    c_str = str(canal_id or '').strip()
    if c_str == CANAL_HUMOR:
        return 'humor'
    elif c_str == CANAL_NOTICIAS:
        return 'noticias'
    return 'avisos'

@aviso_ui_bp.route('/')
def list_avisos():
    _garantir_colunas_db()
    avisos = AnimaAviso.query.order_by(AnimaAviso.aviso_ativo.desc(), AnimaAviso.aviso_id.desc()).all()
    return render_template(
        'avisos/list.html',
        avisos=avisos,
        default_channel_id=CANAL_AVISOS,
        canal_noticias=CANAL_NOTICIAS,
        canal_humor=CANAL_HUMOR
    )

@aviso_ui_bp.route('/api/eventos')
def api_eventos():
    """Retorna publicações agendadas e já enviadas formatadas para o FullCalendar."""
    _garantir_colunas_db()
    avisos = AnimaAviso.query.all()
    eventos = []

    for a in avisos:
        cor = a.categoria_cor_hex
        icone = a.categoria_icone
        label = a.categoria_label

        # 1. Evento do Próximo Disparo / Agendamento Ativo
        if a.aviso_dt_proximo_envio and a.aviso_ativo:
            eventos.append({
                'id': f"agendado_{a.aviso_id}",
                'aviso_id': a.aviso_id,
                'title': f"{icone} {a.aviso_titulo}",
                'start': a.aviso_dt_proximo_envio.isoformat(),
                'backgroundColor': cor,
                'borderColor': cor,
                'textColor': '#ffffff',
                'extendedProps': {
                    'categoria': a.aviso_categoria,
                    'categoria_label': label,
                    'icone': icone,
                    'status': 'Agendado' if a.aviso_tipo != 'recorrente' else 'Recorrente Ativo',
                    'status_icon': '📌' if a.aviso_tipo != 'recorrente' else '🔄',
                    'tipo': a.aviso_tipo,
                    'recorrencia': a.aviso_recorrencia_tipo,
                    'conteudo': a.aviso_conteudo,
                    'canal_id': a.aviso_canal_id,
                    'imagem_url': a.aviso_imagem_url,
                    'temas': [t.temas_interesse_nome for t in a.temas],
                    'edit_url': url_for('aviso_ui.update_aviso', id=a.aviso_id),
                    'disparar_url': url_for('aviso_ui.disparar_aviso', id=a.aviso_id)
                }
            })

        # 2. Evento de Histórico do Último Envio Realizado
        if a.aviso_dt_ultimo_envio:
            eventos.append({
                'id': f"enviado_{a.aviso_id}",
                'aviso_id': a.aviso_id,
                'title': f"✅ {icone} {a.aviso_titulo}",
                'start': a.aviso_dt_ultimo_envio.isoformat(),
                'backgroundColor': '#10b981',
                'borderColor': '#059669',
                'textColor': '#ffffff',
                'extendedProps': {
                    'categoria': a.aviso_categoria,
                    'categoria_label': label,
                    'icone': icone,
                    'status': 'Publicado',
                    'status_icon': '✅',
                    'tipo': a.aviso_tipo,
                    'recorrencia': a.aviso_recorrencia_tipo,
                    'conteudo': a.aviso_conteudo,
                    'canal_id': a.aviso_canal_id,
                    'imagem_url': a.aviso_imagem_url,
                    'temas': [t.temas_interesse_nome for t in a.temas],
                    'edit_url': url_for('aviso_ui.update_aviso', id=a.aviso_id),
                    'disparar_url': url_for('aviso_ui.disparar_aviso', id=a.aviso_id)
                }
            })

    return jsonify(eventos)

@aviso_ui_bp.route('/api/densidade')
def api_densidade():
    """
    Inspeciona a grade horária de uma data específica para detectar conflitos e sobrecarga de postagens.
    Parâmetros GET:
      - data: YYYY-MM-DD (ou YYYY-MM-DDTHH:MM)
      - canal_id: id do canal do Discord
      - aviso_id: id do aviso atual (para ignorar a si mesmo na edição)
    """
    _garantir_colunas_db()
    data_str = request.args.get('data', '').strip()
    canal_id = request.args.get('canal_id', '').strip()
    aviso_id_str = request.args.get('aviso_id', '').strip()
    aviso_id_atual = int(aviso_id_str) if aviso_id_str.isdigit() else None

    if not data_str:
        return jsonify({'erro': 'Data não fornecida'}), 400

    try:
        if 'T' in data_str:
            dt_alvo = datetime.fromisoformat(data_str)
        elif len(data_str) == 10:
            dt_alvo = datetime.strptime(data_str, '%Y-%m-%d')
        else:
            dt_alvo = datetime.strptime(data_str[:16], '%Y-%m-%d %H:%M')
    except Exception:
        return jsonify({'erro': 'Formato de data inválido'}), 400

    inicio_dia = dt_alvo.replace(hour=0, minute=0, second=0, microsecond=0)
    fim_dia = dt_alvo.replace(hour=23, minute=59, second=59, microsecond=999999)

    # Busca agendamentos do mesmo dia
    query = AnimaAviso.query.filter(
        AnimaAviso.aviso_ativo == True,
        AnimaAviso.aviso_dt_proximo_envio.between(inicio_dia, fim_dia)
    )
    if canal_id:
        query = query.filter(AnimaAviso.aviso_canal_id == canal_id)
    if aviso_id_atual:
        query = query.filter(AnimaAviso.aviso_id != aviso_id_atual)

    agendados_dia = query.order_by(AnimaAviso.aviso_dt_proximo_envio.asc()).all()

    # Detecta se há disparos muito próximos (ex: dentro de 2 horas da data_alvo se a hora foi informada)
    conflitos_proximos = []
    lista_dia = []

    for a in agendados_dia:
        dt_envio = a.aviso_dt_proximo_envio
        minutos_dif = abs((dt_envio - dt_alvo).total_seconds()) / 60.0
        
        info_item = {
            'aviso_id': a.aviso_id,
            'titulo': a.aviso_titulo,
            'categoria': a.aviso_categoria,
            'icone': a.categoria_icone,
            'horario': dt_envio.strftime('%H:%M'),
            'hora_iso': dt_envio.isoformat(),
            'canal_id': a.aviso_canal_id
        }
        lista_dia.append(info_item)

        # Se a diferença for menor que 120 minutos (2 horas)
        if 'T' in data_str or len(data_str) > 10:
            if minutos_dif <= 120:
                info_item_conflito = dict(info_item)
                info_item_conflito['minutos_diferenca'] = int(minutos_dif)
                conflitos_proximos.append(info_item_conflito)

    total_dia = len(lista_dia)
    tem_sobrecarga = (total_dia >= 3) or (len(conflitos_proximos) > 0)

    return jsonify({
        'data_consultada': dt_alvo.strftime('%d/%m/%Y'),
        'total_agendamentos_dia': total_dia,
        'tem_sobrecarga': tem_sobrecarga,
        'conflitos_proximos': conflitos_proximos,
        'agendamentos_dia': lista_dia
    })

@aviso_ui_bp.route('/novo', methods=['GET', 'POST'])
def create_aviso():
    _garantir_colunas_db()
    form = AvisoForm()
    
    temas_disponiveis = TemaInteresse.query.order_by(TemaInteresse.temas_interesse_nome).all()
    form.temas.choices = [(t.temas_interesse_id, f"{t.temas_interesse_nome} (#{t.temas_interesse_tag})" if t.temas_interesse_tag else t.temas_interesse_nome) for t in temas_disponiveis]

    if request.method == 'GET':
        form.aviso_categoria.data = 'avisos'
        form.aviso_canal_id.data = CANAL_AVISOS
        
        # Se veio data pela URL (ex: clique no calendário)
        data_param = request.args.get('data')
        if data_param:
            try:
                if len(data_param) == 10:
                    dt_parsed = datetime.strptime(data_param, '%Y-%m-%d').replace(hour=12, minute=0)
                else:
                    dt_parsed = datetime.fromisoformat(data_param)
                form.aviso_dt_proximo_envio.data = dt_parsed
            except Exception:
                form.aviso_dt_proximo_envio.data = get_local_now()
        else:
            form.aviso_dt_proximo_envio.data = get_local_now()

    if form.validate_on_submit():
        # Trata upload de imagem ou URL
        imagem_path = None
        if form.aviso_imagem_file.data:
            imagem_path = _salvar_imagem_upload(form.aviso_imagem_file.data)
        if not imagem_path and form.aviso_imagem_url.data:
            imagem_path = form.aviso_imagem_url.data.strip()

        categoria = _inferir_categoria(form.aviso_categoria.data, form.aviso_canal_id.data)

        novo_aviso = AnimaAviso(
            aviso_titulo=form.aviso_titulo.data.strip(),
            aviso_conteudo=form.aviso_conteudo.data.strip(),
            aviso_canal_id=form.aviso_canal_id.data.strip() or CANAL_AVISOS,
            aviso_categoria=categoria,
            aviso_imagem_url=imagem_path,
            aviso_tipo=form.aviso_tipo.data,
            aviso_recorrencia_tipo=form.aviso_recorrencia_tipo.data if form.aviso_tipo.data == 'recorrente' else 'nenhum',
            aviso_recorrencia_valor=form.aviso_recorrencia_valor.data or 1,
            aviso_usar_ia=bool(form.aviso_usar_ia.data),
            aviso_ia_prompt=form.aviso_ia_prompt.data.strip() if form.aviso_ia_prompt.data else None,
            aviso_ativo=bool(form.aviso_ativo.data),
            aviso_dt_proximo_envio=form.aviso_dt_proximo_envio.data or get_local_now()
        )

        # Associa temas de interesse se selecionados
        if form.temas.data:
            novo_aviso.temas = TemaInteresse.query.filter(TemaInteresse.temas_interesse_id.in_(form.temas.data)).all()

        db.session.add(novo_aviso)
        db.session.commit()
        flash('Publicação cadastrada com sucesso!', 'success')
        return redirect(url_for('aviso_ui.list_avisos'))

    return render_template(
        'avisos/form.html',
        form=form,
        title="Nova Publicação (Aviso, Notícia ou Humor)",
        canal_avisos=CANAL_AVISOS,
        canal_noticias=CANAL_NOTICIAS,
        canal_humor=CANAL_HUMOR
    )

@aviso_ui_bp.route('/editar/<int:id>', methods=['GET', 'POST'])
def update_aviso(id):
    _garantir_colunas_db()
    aviso = AnimaAviso.query.get_or_404(id)
    form = AvisoForm(obj=aviso)

    temas_disponiveis = TemaInteresse.query.order_by(TemaInteresse.temas_interesse_nome).all()
    form.temas.choices = [(t.temas_interesse_id, f"{t.temas_interesse_nome} (#{t.temas_interesse_tag})" if t.temas_interesse_tag else t.temas_interesse_nome) for t in temas_disponiveis]

    if request.method == 'GET':
        if aviso.aviso_categoria:
            form.aviso_categoria.data = aviso.aviso_categoria
        form.temas.data = [t.temas_interesse_id for t in aviso.temas]

    if form.validate_on_submit():
        # Trata upload de imagem nova ou atualização de URL
        if form.aviso_imagem_file.data:
            novo_upload = _salvar_imagem_upload(form.aviso_imagem_file.data)
            if novo_upload:
                aviso.aviso_imagem_url = novo_upload
        elif form.aviso_imagem_url.data is not None:
            aviso.aviso_imagem_url = form.aviso_imagem_url.data.strip() or None

        aviso.aviso_titulo = form.aviso_titulo.data.strip()
        aviso.aviso_conteudo = form.aviso_conteudo.data.strip()
        aviso.aviso_canal_id = form.aviso_canal_id.data.strip()
        aviso.aviso_categoria = _inferir_categoria(form.aviso_categoria.data, aviso.aviso_canal_id)
        aviso.aviso_tipo = form.aviso_tipo.data
        aviso.aviso_recorrencia_tipo = form.aviso_recorrencia_tipo.data if form.aviso_tipo.data == 'recorrente' else 'nenhum'
        aviso.aviso_recorrencia_valor = form.aviso_recorrencia_valor.data or 1
        aviso.aviso_usar_ia = bool(form.aviso_usar_ia.data)
        aviso.aviso_ia_prompt = form.aviso_ia_prompt.data.strip() if form.aviso_ia_prompt.data else None
        aviso.aviso_ativo = bool(form.aviso_ativo.data)
        aviso.aviso_dt_proximo_envio = form.aviso_dt_proximo_envio.data

        # Atualiza temas de interesse vinculados
        if form.temas.data:
            aviso.temas = TemaInteresse.query.filter(TemaInteresse.temas_interesse_id.in_(form.temas.data)).all()
        else:
            aviso.temas = []

        db.session.commit()
        flash('Publicação atualizada com sucesso!', 'success')
        return redirect(url_for('aviso_ui.list_avisos'))

    return render_template(
        'avisos/form.html',
        form=form,
        title="Editar Publicação",
        aviso=aviso,
        canal_avisos=CANAL_AVISOS,
        canal_noticias=CANAL_NOTICIAS,
        canal_humor=CANAL_HUMOR
    )

@aviso_ui_bp.route('/toggle/<int:id>', methods=['POST'])
def toggle_aviso(id):
    aviso = AnimaAviso.query.get_or_404(id)
    aviso.aviso_ativo = not aviso.aviso_ativo
    db.session.commit()
    estado = "ativado" if aviso.aviso_ativo else "desativado"
    flash(f"Item #{aviso.aviso_id} {estado} com sucesso!", 'info')
    return redirect(url_for('aviso_ui.list_avisos'))

@aviso_ui_bp.route('/disparar/<int:id>', methods=['POST'])
def disparar_aviso(id):
    aviso = AnimaAviso.query.get_or_404(id)
    
    # 1. Aplica variação de IA se configurado
    conteudo_final = aviso.aviso_conteudo
    usou_ia = False
    if aviso.aviso_usar_ia:
        conteudo_variado = gerar_variacao_aviso(aviso.aviso_conteudo, aviso.aviso_ia_prompt)
        if conteudo_variado and conteudo_variado != aviso.aviso_conteudo:
            conteudo_final = conteudo_variado
            usou_ia = True

    # 2. Formata mensagem aberta de largura total (sem moldura/embed)
    icone = aviso.categoria_icone
    linhas = [
        f"## {icone} {aviso.aviso_titulo}\n",
        conteudo_final
    ]

    # Destaca temas de interesse vinculados
    if aviso.temas:
        tags_str = "  ".join([f"`#{t.temas_interesse_tag or t.temas_interesse_nome.replace(' ', '')}`" for t in aviso.temas])
        linhas.append(f"\n🎯 **Temas:** {tags_str}")

    mensagem_completa = "\n".join(linhas)

    # 3. Trata anexo de imagem / meme local ou remoto
    # Se a mensagem já contém link do YouTube (ou a imagem for thumbnail do YouTube), não anexa a imagem avulsa para não duplicar com o player nativo do Discord
    tem_video_youtube = "youtube.com" in conteudo_final.lower() or "youtu.be" in conteudo_final.lower()
    
    file_path_to_send = None
    if aviso.aviso_imagem_url and not tem_video_youtube:
        img_val = aviso.aviso_imagem_url.strip()
        # Ignora se for thumbnail explícita do YouTube (ex: ytimg.com)
        if "ytimg.com" not in img_val.lower():
            if img_val.startswith('/static/'):
                # Arquivo local no servidor (upload de meme ou banner)
                local_rel = img_val.lstrip('/')
                abs_local = os.path.join(current_app.root_path, local_rel)
                if os.path.exists(abs_local) and os.path.isfile(abs_local):
                    file_path_to_send = abs_local
            elif img_val.startswith('http://') or img_val.startswith('https://'):
                mensagem_completa += f"\n\n{img_val}"

    # 4. Dispara no canal correspondente do Discord com largura total
    canal_alvo = aviso.aviso_canal_id or CANAL_AVISOS
    sucesso = send_discord_channel_message(channel_id=canal_alvo, content=mensagem_completa, file_path=file_path_to_send)

    if sucesso:
        aviso.aviso_dt_ultimo_envio = get_local_now()
        
        # Se for recorrente, recalcula próximo envio; se for único, pode desativar
        if aviso.aviso_tipo == 'recorrente':
            aviso.aviso_dt_proximo_envio = aviso.calcular_proximo_envio(get_local_now())
        else:
            aviso.aviso_ativo = False # Concluído

        db.session.commit()

        detalhe_ia = " (com variação gerada via LLaMA)" if usou_ia else ""
        flash(f"Publicação #{aviso.aviso_id} enviada com sucesso ao canal {canal_alvo}{detalhe_ia}!", 'success')
    else:
        flash(f"Falha ao publicar no canal {canal_alvo}. Verifique as permissões do bot.", 'danger')

    return redirect(url_for('aviso_ui.list_avisos'))

@aviso_ui_bp.route('/excluir/<int:id>', methods=['POST'])
def delete_aviso(id):
    aviso = AnimaAviso.query.get_or_404(id)
    # Se houver arquivo local associado, podemos limpá-lo opcionalmente
    if aviso.aviso_imagem_url and aviso.aviso_imagem_url.startswith('/static/uploads/'):
        try:
            local_file = os.path.join(current_app.root_path, aviso.aviso_imagem_url.lstrip('/'))
            if os.path.exists(local_file):
                os.remove(local_file)
        except Exception:
            pass
    db.session.delete(aviso)
    db.session.commit()
    flash('Item excluído com sucesso!', 'info')
    return redirect(url_for('aviso_ui.list_avisos'))
