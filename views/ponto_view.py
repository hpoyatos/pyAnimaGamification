from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from extensions import db
from models.ponto import Ponto
from models.usuario import Usuario
from models.uc import Uc
from forms.ponto_form import PontoForm
from forms.kahoot_form import KahootLoteForm
from forms.presenca_csv_form import PresencaCsvForm
import pandas as pd
import io

ponto_ui_bp = Blueprint('ponto_ui', __name__, url_prefix='/ui/pontos')

@ponto_ui_bp.route('/api/usuarios-por-uc/<int:uc_id>')
def api_usuarios_por_uc(uc_id):
    # Retorna usuários que têm registros de ponto para a UC especificada
    usuarios = Usuario.query.join(Ponto).filter(Ponto.uc_id == uc_id).distinct().order_by(Usuario.usuario_nome).all()
    dados = [{'id': u.usuario_id, 'nome': u.usuario_nome} for u in usuarios]
    return jsonify(dados)

@ponto_ui_bp.route('/api/usuarios-todos')
def api_usuarios_todos():
    usuarios = Usuario.query.order_by(Usuario.usuario_nome).all()
    dados = [{'id': u.usuario_id, 'nome': u.usuario_nome} for u in usuarios]
    return jsonify(dados)

@ponto_ui_bp.route('/kahoot-lote', methods=['GET', 'POST'])
def create_kahoot_lote():
    form = KahootLoteForm()
    if form.validate_on_submit():
        uc_id = form.uc_id.data.uc_id
        dt_ponto = form.data_kahoot.data
        nome_jogo = form.nome_jogo.data
        
        # Pontuações segundo a regra:
        # 1-3: 1.0, 4-6: 0.8, 7-10: 0.5
        pontuacoes = [1.0, 1.0, 1.0, 0.8, 0.8, 0.8, 0.5, 0.5, 0.5, 0.5]
        
        usuarios_campos = [
            form.usuario_1, form.usuario_2, form.usuario_3,
            form.usuario_4, form.usuario_5, form.usuario_6,
            form.usuario_7, form.usuario_8, form.usuario_9,
            form.usuario_10
        ]
        
        inseridos = 0
        for i, campo in enumerate(usuarios_campos):
            lugar = i + 1
            pontos = pontuacoes[i]
            
            usuario = campo.data
            if usuario:  # If a user is selected
                comentario = f"{usuario.usuario_nome} ficou em {lugar}º lugar no Kahoot de {nome_jogo}"
                
                novo_ponto = Ponto(
                    usuario_id=usuario.usuario_id,
                    uc_id=uc_id,
                    tipo_ponto='Kahoot',
                    num_ponto=pontos,
                    comentario_ponto=comentario,
                    dt_ponto=dt_ponto
                )
                db.session.add(novo_ponto)
                inseridos += 1
                
        if inseridos > 0:
            db.session.commit()
            flash(f'{inseridos} pontos de Kahoot lançados com sucesso!', 'success')
        else:
            flash('Nenhum usuário foi selecionado.', 'danger')
            
        return redirect(url_for('ponto_ui.list_pontos'))
        
    return render_template('ponto/kahoot_lote.html', form=form, title="Lançar Kahoot em Lote")

@ponto_ui_bp.route('/')
def list_pontos():
    # Use join to eagerly load related records if needed, or rely on relationship
    pontos = Ponto.query.join(Usuario).join(Uc).all()
    return render_template('ponto/list.html', pontos=pontos)

@ponto_ui_bp.route('/novo', methods=['GET', 'POST'])
def create_ponto():
    form = PontoForm()
    
    if request.method == 'POST':
        usuarios = Usuario.query.order_by(Usuario.usuario_nome).all()
        form.usuario_id.choices = [(u.usuario_id, u.usuario_nome) for u in usuarios]

    if form.validate_on_submit():
        novo_ponto = Ponto(
            usuario_id=form.usuario_id.data,
            uc_id=form.uc_id.data.uc_id,
            tipo_ponto=form.tipo_ponto.data,
            dt_ponto=form.dt_ponto.data,
            num_ponto=form.num_ponto.data,
            comentario_ponto=form.comentario_ponto.data
        )
        db.session.add(novo_ponto)
        db.session.commit()
        flash('Ponto criado com sucesso!', 'success')
        return redirect(url_for('ponto_ui.list_pontos'))
    return render_template('ponto/form.html', form=form, title="Novo Ponto")

@ponto_ui_bp.route('/editar/<int:id>', methods=['GET', 'POST'])
def update_ponto(id):
    ponto = Ponto.query.get_or_404(id)
    form = PontoForm(obj=ponto)
    
    if request.method == 'POST':
        usuarios = Usuario.query.order_by(Usuario.usuario_nome).all()
        form.usuario_id.choices = [(u.usuario_id, u.usuario_nome) for u in usuarios]
    else:
        if ponto.uc_id and str(ponto.uc_id) != '__None':
            usuarios = Usuario.query.join(Ponto).filter(Ponto.uc_id == ponto.uc_id).distinct().order_by(Usuario.usuario_nome).all()
            # Certificar que o usuário atual está na lista, se não, buscar todos
            if not any(u.usuario_id == ponto.usuario_id for u in usuarios):
                usuarios = Usuario.query.order_by(Usuario.usuario_nome).all()
        else:
            usuarios = Usuario.query.order_by(Usuario.usuario_nome).all()
        form.usuario_id.choices = [(u.usuario_id, u.usuario_nome) for u in usuarios]

    if request.method == 'GET':
        form.usuario_id.data = ponto.usuario_id
        form.uc_id.data = Uc.query.get(ponto.uc_id)
        
    if form.validate_on_submit():
        ponto.usuario_id = form.usuario_id.data
        ponto.uc_id = form.uc_id.data.uc_id
        ponto.tipo_ponto = form.tipo_ponto.data
        ponto.dt_ponto = form.dt_ponto.data
        ponto.num_ponto = form.num_ponto.data
        ponto.comentario_ponto = form.comentario_ponto.data
        db.session.commit()
        flash('Ponto atualizado com sucesso!', 'success')
        return redirect(url_for('ponto_ui.list_pontos'))
    return render_template('ponto/form.html', form=form, title="Editar Ponto")

@ponto_ui_bp.route('/excluir/<int:id>', methods=['POST'])
def delete_ponto(id):
    ponto = Ponto.query.get_or_404(id)
    db.session.delete(ponto)
    db.session.commit()
    flash('Ponto excluído com sucesso!', 'success')
    return redirect(url_for('ponto_ui.list_pontos'))

@ponto_ui_bp.route('/presenca-csv', methods=['GET', 'POST'])
def create_presenca_csv():
    form = PresencaCsvForm()
    if form.validate_on_submit():
        uc_id = form.uc_id.data.uc_id
        dt_ponto = form.data_aula.data
        pontos = float(form.pontos.data)
        arquivo = request.files[form.arquivo.name]

        try:
            content = arquivo.read()
            df = None
            detected_encoding = None

            # Teams CSV reports usually have a BOM and are utf-16-le. 
            # Tentamos ler do pandas pulando de 0 a 15 linhas no cabeçalho
            for enc in ['utf-16', 'utf-16-le', 'utf-8', 'utf-8-sig', 'latin1', 'cp1252']:
                for sep in ['\t', ',', ';']:
                    for skip in range(15):
                        try:
                            temp_df = pd.read_csv(io.BytesIO(content), encoding=enc, sep=sep, skiprows=skip, dtype=str, on_bad_lines='skip')
                            
                            # Limpa os nomes das colunas de caracteres invisiveis
                            temp_df.columns = temp_df.columns.astype(str).str.strip().str.replace('\ufeff', '', regex=False).str.lower()
                            
                            cols = temp_df.columns.tolist()
                            if any('nome' in c for c in cols) and any('email' in c for c in cols):
                                df = temp_df
                                detected_encoding = enc
                                break
                        except Exception:
                            continue
                    
                    if df is not None:
                        break
                if df is not None:
                    break

            if df is None or df.empty:
                flash("Erro ao ler o arquivo CSV. O formato ou a codificação são inválidos. (Cabeçalhos 'Nome' e 'Email' não encontrados)", "danger")
                return render_template('ponto/presenca_csv.html', form=form, title="Lançar Presença em Lote (CSV)")

            col_nome = None
            col_email = None

            for col in df.columns:
                if 'nome' in col: col_nome = col
                if 'email' in col: col_email = col

            if not col_nome or not col_email:
                cols_str = ", ".join(df.columns.tolist())
                flash(f"Colunas 'Nome' e 'Email' não foram identificadas. Colunas lidas: {cols_str}", "danger")
                return render_template('ponto/presenca_csv.html', form=form, title="Lançar Presença em Lote (CSV)")

            # Filtrar apenas Participantes
            # Ignorar qualquer linha contendo "organizador" ou os emails administrativos específicos
            mascara_ignorar = df.astype(str).apply(
                lambda col: col.str.lower().str.contains('organizador|adm.ulife.links|henrique.poyatos')
            ).any(axis=1)
            
            df = df[~mascara_ignorar]

            # Ignorar linhas de cabeçalho perdidas no meio do arquivo (ex: "Nome", "Email" repetidos)
            if col_nome and col_email:
                df = df[~( (df[col_nome].astype(str).str.lower() == 'nome') | (df[col_email].astype(str).str.lower() == 'email') )]

            # Limpar valores vazios - RIGOROSO para email: Não insere se não houver um E-mail
            df = df.dropna(subset=[col_email])
            # E garantir que o e-mail não é string vazia
            df = df[df[col_email].astype(str).str.strip() != '']

            # Remover duplicatas mantendo apenas o primeiro registro encontrado do usuário
            df = df.drop_duplicates(subset=[col_email], keep='first')

            sucessos = 0
            pulados = 0
            novos_usuarios = 0

            dt_ponto_formatada = dt_ponto.strftime('%d/%m/%Y')
            
            # Conjunto para rastrear emails/nomes processados NESTA mesma submissão (evitar dupla inserção no mesmo loop)
            processados_nesta_leva = set()

            for index, row in df.iterrows():
                email_csv = str(row[col_email]).strip() if pd.notna(row[col_email]) else ''
                nome_csv = str(row[col_nome]).strip() if pd.notna(row[col_nome]) else ''

                if not email_csv and not nome_csv:
                    continue
                    
                identificador_unico = (email_csv.lower() if email_csv else "") + "|" + (nome_csv.lower() if nome_csv else "")
                if identificador_unico in processados_nesta_leva:
                    continue # Já processamos esse cara na mesma planilha
                processados_nesta_leva.add(identificador_unico)

                usuario = None
                if email_csv:
                    usuario = Usuario.query.filter(Usuario.usuario_email.ilike(f"%{email_csv}%")).first()
                if not usuario and nome_csv:
                    usuario = Usuario.query.filter(Usuario.usuario_nome.ilike(f"%{nome_csv}%")).first()
                
                # Auto-criação de usuário
                if not usuario:
                    ra = None
                    if email_csv and '@' in email_csv:
                        ra = email_csv.split('@')[0][:12] # Truncate to maximum 12 characters as defined in DB model
                    
                    nome_inserir = nome_csv if nome_csv else email_csv
                    
                    usuario = Usuario(
                        usuario_nome=nome_inserir,
                        usuario_email=email_csv,
                        usuario_ra=ra,
                        usuario_discord_id=None,
                        usuario_discord_name=None,
                        usuario_validado=False,
                        usuario_validado_data=None
                    )
                    db.session.add(usuario)
                    db.session.flush() 
                    novos_usuarios += 1

                ponto_existente = Ponto.query.filter_by(
                    usuario_id=usuario.usuario_id, 
                    uc_id=uc_id, 
                    tipo_ponto='Presença',
                    dt_ponto=dt_ponto
                ).first()

                if ponto_existente:
                    pulados += 1
                    continue

                comentario = f"{usuario.usuario_nome} presente na aula de {dt_ponto_formatada}"
                novo_ponto = Ponto(
                    usuario_id=usuario.usuario_id,
                    uc_id=uc_id,
                    tipo_ponto='Presença',
                    dt_ponto=dt_ponto,
                    num_ponto=pontos,
                    comentario_ponto=comentario
                )
                db.session.add(novo_ponto)
                sucessos += 1

            db.session.commit()
            
            msg = f'Concluído: {sucessos} presenças aplicadas, {pulados} puladas (já existiam).'
            if novos_usuarios > 0:
                msg += f' {novos_usuarios} novos usuários foram criados automaticamente.'
            
            flash(msg, 'success')
                
            return redirect(url_for('ponto_ui.list_pontos'))

        except Exception as e:
            flash(f'Erro ao processar o arquivo: {str(e)}', 'danger')

    return render_template('ponto/presenca_csv.html', form=form, title="Lançar Presença em Lote (CSV)")

@ponto_ui_bp.route('/participacao', methods=['GET', 'POST'])
def create_participacao():
    from forms.participacao_form import ParticipacaoForm
    from datetime import datetime, timezone, timedelta
    from utils.discord_api import send_discord_dm

    form = ParticipacaoForm()

    if request.method == 'POST':
        uc_id = request.form.get('uc_id')
        if uc_id and uc_id != '__None':
            usuarios = Usuario.query.join(Ponto).filter(Ponto.uc_id == uc_id).distinct().order_by(Usuario.usuario_nome).all()
            form.usuario_id.choices = [(u.usuario_id, u.usuario_nome) for u in usuarios]

    if form.validate_on_submit():
        uc_id = form.uc_id.data.uc_id
        usuario_id = form.usuario_id.data
        tipo_participacao = form.tipo_participacao.data
        pontos = float(form.pontos.data)
        comentario = form.comentario.data
        
        novo_ponto = Ponto(
            usuario_id=usuario_id,
            uc_id=uc_id,
            tipo_ponto='Participação',
            dt_ponto=datetime.now(timezone(timedelta(hours=-3))),
            num_ponto=pontos,
            comentario_ponto=comentario
        )
        
        try:
            db.session.add(novo_ponto)
            db.session.commit()
            flash('Participação registrada com sucesso!', 'success')
            
            usuario = Usuario.query.get(usuario_id)
            if usuario and usuario.usuario_discord_id:
                send_discord_dm(
                    discord_user_id=usuario.usuario_discord_id,
                    usuario_nome=usuario.usuario_nome,
                    num_pontos=pontos,
                    justificativa=comentario
                )
            
            return redirect(url_for('ponto_ui.list_pontos'))
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao registrar participação: {str(e)}', 'danger')

    return render_template('ponto/participacao_form.html', form=form, title="Registrar Participação em Aula")
