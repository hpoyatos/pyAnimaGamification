import os
import requests
import logging
from flask import Blueprint, render_template, redirect, url_for, flash, request
from extensions import db
from models.discord_role import AnimaDiscordRole, AnimaUsuarioDiscordRole
from models.usuario_discord import UsuarioDiscord
from models.usuario import Usuario
from models.quiz import TemaInteresse
from models.curso import Curso
from models.uc import Uc
from forms.discord_role_form import AnimaDiscordRoleForm

logger = logging.getLogger("discord_role_ui")
discord_role_ui_bp = Blueprint('discord_role_ui', __name__, url_prefix='/ui/roles')


def _garantir_schema_db():
    """Garante de forma idempotente a criação das tabelas e colunas necessárias no MariaDB."""
    try:
        with db.engine.connect() as conn:
            # 1. Cria tabela anima_discord_role se não existir
            conn.execute(db.text("""
                CREATE TABLE IF NOT EXISTS `anima_discord_role` (
                    `role_id` VARCHAR(20) NOT NULL,
                    `role_descricao` VARCHAR(150) NOT NULL,
                    `role_ativo` TINYINT(1) NOT NULL DEFAULT 1,
                    `role_created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (`role_id`)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """))
            conn.commit()

            # 2. Adiciona role_ativo se não existir
            try:
                conn.execute(db.text("ALTER TABLE anima_discord_role ADD COLUMN role_ativo TINYINT(1) NOT NULL DEFAULT 1 AFTER role_descricao"))
                conn.commit()
            except Exception:
                pass

            # 3. Adiciona role_created_at se não existir
            try:
                conn.execute(db.text("ALTER TABLE anima_discord_role ADD COLUMN role_created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP AFTER role_ativo"))
                conn.commit()
            except Exception:
                pass

            # 4. Cria tabela de vinculo de membros anima_usuario_discord_role se não existir
            conn.execute(db.text("""
                CREATE TABLE IF NOT EXISTS `anima_usuario_discord_role` (
                    `discord_user_id` VARCHAR(25) NOT NULL,
                    `role_id` VARCHAR(20) NOT NULL,
                    `data_associacao` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (`discord_user_id`, `role_id`),
                    KEY `idx_audr_role` (`role_id`),
                    CONSTRAINT `fk_audr_role` FOREIGN KEY (`role_id`) REFERENCES `anima_discord_role` (`role_id`) ON DELETE CASCADE ON UPDATE CASCADE
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """))
            conn.commit()
    except Exception as e:
        logger.warning(f"Aviso ao verificar schema de anima_discord_role: {e}")


@discord_role_ui_bp.route('/')
def list_roles():
    _garantir_schema_db()
    roles = AnimaDiscordRole.query.order_by(AnimaDiscordRole.role_ativo.desc(), AnimaDiscordRole.role_descricao.asc()).all()
    
    total_ativos = sum(1 for r in roles if r.role_ativo)
    total_inativos = len(roles) - total_ativos
    total_com_temas = sum(1 for r in roles if r.total_temas > 0)
    total_com_membros = sum(1 for r in roles if r.total_usuarios > 0)

    return render_template(
        'discord_role/list.html',
        roles=roles,
        total_ativos=total_ativos,
        total_inativos=total_inativos,
        total_com_temas=total_com_temas,
        total_com_membros=total_com_membros
    )


@discord_role_ui_bp.route('/<string:id>')
@discord_role_ui_bp.route('/detalhes/<string:id>')
def view_role(id):
    _garantir_schema_db()
    role = AnimaDiscordRole.query.get_or_404(id)
    
    temas = []
    try:
        if hasattr(role, 'temas_interesse') and role.temas_interesse is not None:
            temas = role.temas_interesse.all()
    except Exception:
        pass

    return render_template(
        'discord_role/detail.html',
        role=role,
        temas=temas,
        cursos=role.cursos or [],
        ucs=role.ucs or [],
        membros=role.usuarios_associados or []
    )


@discord_role_ui_bp.route('/novo', methods=['GET', 'POST'])
def create_role():
    _garantir_schema_db()
    form = AnimaDiscordRoleForm()
    if form.validate_on_submit():
        role_id_clean = form.role_id.data.strip()
        existente = AnimaDiscordRole.query.get(role_id_clean)
        if existente:
            flash(f'O Cargo com ID {role_id_clean} já existe no sistema ({existente.role_descricao}).', 'warning')
            return render_template('discord_role/form.html', form=form, title="Novo Cargo Discord")
            
        nova_role = AnimaDiscordRole(
            role_id=role_id_clean,
            role_descricao=form.role_descricao.data.strip(),
            role_ativo=form.role_ativo.data
        )
        db.session.add(nova_role)
        db.session.commit()
        flash(f"Cargo '{nova_role.role_descricao}' ({nova_role.role_id}) cadastrado com sucesso!", 'success')
        return redirect(url_for('discord_role_ui.list_roles'))
    return render_template('discord_role/form.html', form=form, title="Novo Cargo Discord")


@discord_role_ui_bp.route('/editar/<string:id>', methods=['GET', 'POST'])
def update_role(id):
    _garantir_schema_db()
    role = AnimaDiscordRole.query.get_or_404(id)
    form = AnimaDiscordRoleForm(obj=role)
    
    if form.validate_on_submit():
        role.role_descricao = form.role_descricao.data.strip()
        role.role_ativo = form.role_ativo.data
        db.session.commit()
        flash(f"Cargo '{role.role_descricao}' ({role.role_id}) atualizado com sucesso!", 'success')
        return redirect(url_for('discord_role_ui.list_roles'))
    
    return render_template('discord_role/form.html', form=form, title="Editar Cargo Discord", role=role)


@discord_role_ui_bp.route('/alternar-status/<string:id>', methods=['POST'])
def toggle_role_status(id):
    _garantir_schema_db()
    role = AnimaDiscordRole.query.get_or_404(id)
    role.role_ativo = not role.role_ativo
    db.session.commit()
    status_str = "ativado" if role.role_ativo else "desativado"
    flash(f"Cargo '{role.role_descricao}' {status_str} com sucesso!", "info")
    return redirect(request.referrer or url_for('discord_role_ui.list_roles'))


@discord_role_ui_bp.route('/excluir/<string:id>', methods=['POST'])
def delete_role(id):
    _garantir_schema_db()
    role = AnimaDiscordRole.query.get_or_404(id)
    
    # Validações de integridade antes de tentar excluir
    dependencias = []
    try:
        temas_count = role.temas_interesse.count() if hasattr(role, 'temas_interesse') and role.temas_interesse else 0
        if temas_count > 0:
            dependencias.append(f"{temas_count} Tema(s) de Interesse")
    except Exception:
        pass
        
    if role.cursos and len(role.cursos) > 0:
        dependencias.append(f"{len(role.cursos)} Curso(s)")
        
    if role.ucs and len(role.ucs) > 0:
        dependencias.append(f"{len(role.ucs)} Unidade(s) Curricular(es)")
        
    if dependencias:
        deps_str = ", ".join(dependencias)
        flash(f"Não é possível excluir o cargo '{role.role_descricao}' ({role.role_id}) pois ele está vinculado a: {deps_str}. Remova essas vinculações ou desative o cargo.", "warning")
        return redirect(request.referrer or url_for('discord_role_ui.list_roles'))

    try:
        nome = role.role_descricao
        rid = role.role_id
        db.session.delete(role)
        db.session.commit()
        flash(f"Cargo '{nome}' ({rid}) excluído com sucesso!", 'success')
    except Exception as e:
        db.session.rollback()
        logger.error(f"Erro ao excluir cargo {id}: {e}")
        flash(f"Erro ao excluir cargo: {str(e)}", 'danger')
        
    return redirect(url_for('discord_role_ui.list_roles'))


@discord_role_ui_bp.route('/sincronizar', methods=['POST'])
def sync_roles():
    """
    Sincroniza todas as roles da API do Discord.
    Se um cargo sumir do servidor Discord, apenas atualiza role_ativo = False (não apaga do banco).
    """
    _garantir_schema_db()
    token = os.getenv("DISCORD_BOT_TOKEN")
    if not token:
        flash("Token do bot (DISCORD_BOT_TOKEN) não configurado nas variáveis de ambiente.", "danger")
        return redirect(url_for('discord_role_ui.list_roles'))

    headers = {"Authorization": f"Bot {token}"}
    try:
        res_guilds = requests.get("https://discord.com/api/v10/users/@me/guilds", headers=headers, timeout=10)
        if res_guilds.status_code != 200:
            flash(f"Erro ao consultar servidores do bot no Discord: {res_guilds.status_code} - {res_guilds.text}", "danger")
            return redirect(url_for('discord_role_ui.list_roles'))

        guilds = res_guilds.json()
        active_discord_role_ids = set()
        total_roles_synced = 0

        for g in guilds:
            g_id = g['id']
            res_roles = requests.get(f"https://discord.com/api/v10/guilds/{g_id}/roles", headers=headers, timeout=10)
            if res_roles.status_code == 200:
                roles = res_roles.json()
                for r in roles:
                    if r.get('name') != '@everyone':
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

        msg = f"Sucesso! {total_roles_synced} cargo(s) sincronizados com o Discord."
        if total_deactivated > 0:
            msg += f" {total_deactivated} cargo(s) inativos no servidor foram marcados como inativos."
        flash(msg, "success")

    except Exception as e:
        db.session.rollback()
        logger.error(f"Erro ao sincronizar roles do Discord: {e}")
        flash(f"Erro na sincronização: {str(e)}", "danger")

    return redirect(url_for('discord_role_ui.list_roles'))

