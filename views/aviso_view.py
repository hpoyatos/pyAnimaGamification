import os
from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, flash, request
from extensions import db
from models.aviso import AnimaAviso
from forms.aviso_form import AvisoForm
from utils.discord_api import send_discord_channel_message
from utils.llm_helper import gerar_variacao_aviso

aviso_ui_bp = Blueprint('aviso_ui', __name__, url_prefix='/ui/avisos')

@aviso_ui_bp.route('/')
def list_avisos():
    avisos = AnimaAviso.query.order_by(AnimaAviso.aviso_ativo.desc(), AnimaAviso.aviso_id.desc()).all()
    default_channel_id = os.getenv("DISCORD_AVISOS_CHANNEL_ID", "1020488574732357632")
    return render_template('avisos/list.html', avisos=avisos, default_channel_id=default_channel_id)

@aviso_ui_bp.route('/novo', methods=['GET', 'POST'])
def create_aviso():
    default_channel_id = os.getenv("DISCORD_AVISOS_CHANNEL_ID", "1020488574732357632")
    form = AvisoForm()
    
    if request.method == 'GET':
        form.aviso_canal_id.data = default_channel_id
        form.aviso_dt_proximo_envio.data = datetime.now()

    if form.validate_on_submit():
        novo_aviso = AnimaAviso(
            aviso_titulo=form.aviso_titulo.data.strip(),
            aviso_conteudo=form.aviso_conteudo.data.strip(),
            aviso_canal_id=form.aviso_canal_id.data.strip() or default_channel_id,
            aviso_tipo=form.aviso_tipo.data,
            aviso_recorrencia_tipo=form.aviso_recorrencia_tipo.data if form.aviso_tipo.data == 'recorrente' else 'nenhum',
            aviso_recorrencia_valor=form.aviso_recorrencia_valor.data or 1,
            aviso_usar_ia=bool(form.aviso_usar_ia.data),
            aviso_ia_prompt=form.aviso_ia_prompt.data.strip() if form.aviso_ia_prompt.data else None,
            aviso_ativo=bool(form.aviso_ativo.data),
            aviso_dt_proximo_envio=form.aviso_dt_proximo_envio.data or datetime.now()
        )
        db.session.add(novo_aviso)
        db.session.commit()
        flash('Aviso cadastrado com sucesso!', 'success')
        return redirect(url_for('aviso_ui.list_avisos'))

    return render_template('avisos/form.html', form=form, title="Novo Aviso")

@aviso_ui_bp.route('/editar/<int:id>', methods=['GET', 'POST'])
def update_aviso(id):
    aviso = AnimaAviso.query.get_or_404(id)
    form = AvisoForm(obj=aviso)

    if form.validate_on_submit():
        aviso.aviso_titulo = form.aviso_titulo.data.strip()
        aviso.aviso_conteudo = form.aviso_conteudo.data.strip()
        aviso.aviso_canal_id = form.aviso_canal_id.data.strip()
        aviso.aviso_tipo = form.aviso_tipo.data
        aviso.aviso_recorrencia_tipo = form.aviso_recorrencia_tipo.data if form.aviso_tipo.data == 'recorrente' else 'nenhum'
        aviso.aviso_recorrencia_valor = form.aviso_recorrencia_valor.data or 1
        aviso.aviso_usar_ia = bool(form.aviso_usar_ia.data)
        aviso.aviso_ia_prompt = form.aviso_ia_prompt.data.strip() if form.aviso_ia_prompt.data else None
        aviso.aviso_ativo = bool(form.aviso_ativo.data)
        aviso.aviso_dt_proximo_envio = form.aviso_dt_proximo_envio.data

        db.session.commit()
        flash('Aviso atualizado com sucesso!', 'success')
        return redirect(url_for('aviso_ui.list_avisos'))

    return render_template('avisos/form.html', form=form, title="Editar Aviso", aviso=aviso)

@aviso_ui_bp.route('/toggle/<int:id>', methods=['POST'])
def toggle_aviso(id):
    aviso = AnimaAviso.query.get_or_404(id)
    aviso.aviso_ativo = not aviso.aviso_ativo
    db.session.commit()
    estado = "ativado" if aviso.aviso_ativo else "desativado"
    flash(f"Aviso #{aviso.aviso_id} {estado} com sucesso!", 'info')
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

    # 2. Monta Embed para o canal de avisos
    embed = {
        "title": f"📢 {aviso.aviso_titulo}",
        "description": conteudo_final,
        "color": 0x3b82f6, # Azul Gamificação
        "footer": {
            "text": "JocastaBOT • Avisos & Comunidade" + (" • 🤖 Texto dinamizado com IA" if usou_ia else "")
        },
        "timestamp": datetime.utcnow().isoformat()
    }

    # 3. Dispara no canal do Discord
    canal_alvo = aviso.aviso_canal_id or os.getenv("DISCORD_AVISOS_CHANNEL_ID", "1020488574732357632")
    sucesso = send_discord_channel_message(channel_id=canal_alvo, embed_dict=embed)

    if sucesso:
        aviso.aviso_dt_ultimo_envio = datetime.now()
        
        # Se for recorrente, recalcula próximo envio; se for único, pode desativar
        if aviso.aviso_tipo == 'recorrente':
            aviso.aviso_dt_proximo_envio = aviso.calcular_proximo_envio()
        else:
            aviso.aviso_ativo = False # Concluído

        db.session.commit()
        detalhe_ia = " (com variação gerada via LLaMA)" if usou_ia else ""
        flash(f"Aviso #{aviso.aviso_id} publicado com sucesso no canal {canal_alvo}{detalhe_ia}!", 'success')
    else:
        flash(f"Falha ao publicar aviso no Discord. Verifique o token e as permissões do bot no canal {canal_alvo}.", 'danger')

    return redirect(url_for('aviso_ui.list_avisos'))

@aviso_ui_bp.route('/excluir/<int:id>', methods=['POST'])
def delete_aviso(id):
    aviso = AnimaAviso.query.get_or_404(id)
    db.session.delete(aviso)
    db.session.commit()
    flash(f"Aviso #{id} excluído com sucesso!", 'info')
    return redirect(url_for('aviso_ui.list_avisos'))
