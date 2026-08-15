import os
import requests
import logging
from flask import Blueprint, render_template, redirect, url_for, flash, request
from extensions import db
from models.discord_role import AnimaDiscordRole
from forms.discord_role_form import AnimaDiscordRoleForm

logger = logging.getLogger("discord_role_ui")
discord_role_ui_bp = Blueprint('discord_role_ui', __name__, url_prefix='/ui/roles')

@discord_role_ui_bp.route('/')
def list_roles():
    roles = AnimaDiscordRole.query.order_by(AnimaDiscordRole.role_descricao.asc()).all()
    return render_template('discord_role/list.html', roles=roles)

@discord_role_ui_bp.route('/novo', methods=['GET', 'POST'])
def create_role():
    form = AnimaDiscordRoleForm()
    if form.validate_on_submit():
        role_id_clean = form.role_id.data.strip()
        existente = AnimaDiscordRole.query.get(role_id_clean)
        if existente:
            flash(f'O Cargo com ID {role_id_clean} já existe no sistema.', 'warning')
            return render_template('discord_role/form.html', form=form, title="Novo Cargo Discord")
            
        nova_role = AnimaDiscordRole(
            role_id=role_id_clean,
            role_descricao=form.role_descricao.data.strip()
        )
        db.session.add(nova_role)
        db.session.commit()
        flash('Cargo do Discord cadastrado com sucesso!', 'success')
        return redirect(url_for('discord_role_ui.list_roles'))
    return render_template('discord_role/form.html', form=form, title="Novo Cargo Discord")

@discord_role_ui_bp.route('/editar/<string:id>', methods=['GET', 'POST'])
def update_role(id):
    role = AnimaDiscordRole.query.get_or_404(id)
    form = AnimaDiscordRoleForm(obj=role)
    
    if form.validate_on_submit():
        role.role_descricao = form.role_descricao.data.strip()
        db.session.commit()
        flash('Descrição do cargo atualizada com sucesso!', 'success')
        return redirect(url_for('discord_role_ui.list_roles'))
    
    return render_template('discord_role/form.html', form=form, title="Editar Cargo Discord", role=role)

@discord_role_ui_bp.route('/excluir/<string:id>', methods=['POST'])
def delete_role(id):
    role = AnimaDiscordRole.query.get_or_404(id)
    try:
        db.session.delete(role)
        db.session.commit()
        flash('Cargo excluído com sucesso!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Não é possível excluir este cargo pois ele está em uso por cursos ou UCs: {str(e)}', 'danger')
    return redirect(url_for('discord_role_ui.list_roles'))

@discord_role_ui_bp.route('/sincronizar', methods=['POST'])
def sync_roles():
    """Sincroniza todas as roles diretamente da API do Discord."""
    token = os.getenv("DISCORD_BOT_TOKEN")
    if not token:
        flash("Token do bot (DISCORD_BOT_TOKEN) não configurado nas variáveis de ambiente.", "danger")
        return redirect(url_for('discord_role_ui.list_roles'))

    headers = {"Authorization": f"Bot {token}"}
    try:
        res_guilds = requests.get("https://discord.com/api/v10/users/@me/guilds", headers=headers)
        if res_guilds.status_code != 200:
            flash(f"Erro ao acessar guilds do Discord: {res_guilds.text}", "danger")
            return redirect(url_for('discord_role_ui.list_roles'))

        guilds = res_guilds.json()
        total_synced = 0

        for g in guilds:
            g_id = g['id']
            res_roles = requests.get(f"https://discord.com/api/v10/guilds/{g_id}/roles", headers=headers)
            if res_roles.status_code == 200:
                roles = res_roles.json()
                for r in roles:
                    if r['name'] != '@everyone':
                        rid = str(r['id'])
                        rname = r['name']
                        existente = AnimaDiscordRole.query.get(rid)
                        if existente:
                            existente.role_descricao = rname
                        else:
                            nova = AnimaDiscordRole(role_id=rid, role_descricao=rname)
                            db.session.add(nova)
                        total_synced += 1

        db.session.commit()
        flash(f"Sucesso! {total_synced} cargos sincronizados diretamente do servidor Discord.", "success")
    except Exception as e:
        db.session.rollback()
        logger.error(f"Erro ao sincronizar roles do Discord: {e}")
        flash(f"Erro na sincronização: {str(e)}", "danger")

    return redirect(url_for('discord_role_ui.list_roles'))
