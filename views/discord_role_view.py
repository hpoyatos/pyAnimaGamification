import os
import requests
import logging
from flask import Blueprint, render_template, redirect, url_for, flash, request
from extensions import db
from models.discord_role import AnimaDiscordRole, AnimaUsuarioDiscordRole
from models.usuario_discord import UsuarioDiscord
from models.usuario import Usuario
from forms.discord_role_form import AnimaDiscordRoleForm

logger = logging.getLogger("discord_role_ui")
discord_role_ui_bp = Blueprint('discord_role_ui', __name__, url_prefix='/ui/roles')

@discord_role_ui_bp.route('/')
def list_roles():
    roles = AnimaDiscordRole.query.order_by(AnimaDiscordRole.role_ativo.desc(), AnimaDiscordRole.role_descricao.asc()).all()
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
            role_descricao=form.role_descricao.data.strip(),
            role_ativo=form.role_ativo.data
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
        role.role_ativo = form.role_ativo.data
        db.session.commit()
        flash('Cargo atualizado com sucesso!', 'success')
        return redirect(url_for('discord_role_ui.list_roles'))
    
    return render_template('discord_role/form.html', form=form, title="Editar Cargo Discord", role=role)

@discord_role_ui_bp.route('/alternar-status/<string:id>', methods=['POST'])
def toggle_role_status(id):
    role = AnimaDiscordRole.query.get_or_404(id)
    role.role_ativo = not role.role_ativo
    db.session.commit()
    status_str = "ativado" if role.role_ativo else "desativado"
    flash(f"Cargo '{role.role_descricao}' {status_str} com sucesso!", "info")
    return redirect(url_for('discord_role_ui.list_roles'))

@discord_role_ui_bp.route('/excluir/<string:id>', methods=['POST'])
def delete_role(id):
    role = AnimaDiscordRole.query.get_or_404(id)
    try:
        db.session.delete(role)
        db.session.commit()
        flash('Cargo excluído com sucesso!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Não é possível excluir este cargo pois ele possui associações no banco: {str(e)}', 'danger')
    return redirect(url_for('discord_role_ui.list_roles'))

@discord_role_ui_bp.route('/sincronizar', methods=['POST'])
def sync_roles():
    """
    Sincroniza todas as roles da API do Discord.
    Se um cargo sumir do servidor Discord, apenas atualiza role_ativo = False (não apaga do banco).
    """
    token = os.getenv("DISCORD_BOT_TOKEN")
    if not token:
        flash("Token do bot (DISCORD_BOT_TOKEN) não configurado.", "danger")
        return redirect(url_for('discord_role_ui.list_roles'))

    headers = {"Authorization": f"Bot {token}"}
    try:
        res_guilds = requests.get("https://discord.com/api/v10/users/@me/guilds", headers=headers)
        if res_guilds.status_code != 200:
            flash(f"Erro ao acessar guilds do Discord: {res_guilds.text}", "danger")
            return redirect(url_for('discord_role_ui.list_roles'))

        guilds = res_guilds.json()
        active_discord_role_ids = set()
        total_roles_synced = 0

        for g in guilds:
            g_id = g['id']
            res_roles = requests.get(f"https://discord.com/api/v10/guilds/{g_id}/roles", headers=headers)
            if res_roles.status_code == 200:
                roles = res_roles.json()
                for r in roles:
                    if r['name'] != '@everyone':
                        rid = str(r['id'])
                        rname = r['name']
                        active_discord_role_ids.add(rid)

                        existente = AnimaDiscordRole.query.get(rid)
                        if existente:
                            existente.role_descricao = rname
                            existente.role_ativo = True
                        else:
                            nova = AnimaDiscordRole(role_id=rid, role_descricao=rname, role_ativo=True)
                            db.session.add(nova)
                        total_roles_synced += 1

        # Todas as roles do banco que não estão mais no Discord passam a ser role_ativo = False
        all_db_roles = AnimaDiscordRole.query.all()
        total_deactivated = 0
        for r in all_db_roles:
            if r.role_id not in active_discord_role_ids and r.role_ativo:
                r.role_ativo = False
                total_deactivated += 1

        db.session.commit()

        msg = f"Sucesso! {total_roles_synced} cargos ativos sincronizados do Discord."
        if total_deactivated > 0:
            msg += f" {total_deactivated} cargo(s) que não existem mais no Discord foram desativados (role_ativo = False)."
        flash(msg, "success")

    except Exception as e:
        db.session.rollback()
        logger.error(f"Erro ao sincronizar roles do Discord: {e}")
        flash(f"Erro na sincronização: {str(e)}", "danger")

    return redirect(url_for('discord_role_ui.list_roles'))
