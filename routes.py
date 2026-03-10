from flask import Blueprint, request, jsonify
from daos import UsuarioDAO, UcDAO, UsuarioKahootDAO, PontoDAO, CursoDAO, UsuarioCursoDAO

# ----------- Blueprint: Usuario -----------
usuario_bp = Blueprint('usuario', __name__, url_prefix='/api/usuarios')

@usuario_bp.route('/', methods=['GET'])
def get_usuarios():
    records = UsuarioDAO.get_all()
    return jsonify([r.to_dict() for r in records]), 200

@usuario_bp.route('/<int:id>', methods=['GET'])
def get_usuario(id):
    record = UsuarioDAO.get_by_id(id)
    if not record:
        return jsonify({'error': 'Not found'}), 404
    return jsonify(record.to_dict()), 200

@usuario_bp.route('/', methods=['POST'])
def create_usuario():
    data = request.json
    try:
        record = UsuarioDAO.create(data)
        return jsonify(record.to_dict()), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@usuario_bp.route('/<int:id>', methods=['PUT'])
def update_usuario(id):
    data = request.json
    try:
        record = UsuarioDAO.update(id, data)
        if not record:
            return jsonify({'error': 'Not found'}), 404
        return jsonify(record.to_dict()), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@usuario_bp.route('/<int:id>', methods=['DELETE'])
def delete_usuario(id):
    success = UsuarioDAO.delete(id)
    if not success:
        return jsonify({'error': 'Not found'}), 404
    return jsonify({'message': 'Deleted successfully'}), 200

# ----------- Blueprint: Uc -----------
uc_bp = Blueprint('uc', __name__, url_prefix='/api/ucs')

@uc_bp.route('/', methods=['GET'])
def get_ucs():
    records = UcDAO.get_all()
    return jsonify([r.to_dict() for r in records]), 200

@uc_bp.route('/<int:id>', methods=['GET'])
def get_uc(id):
    record = UcDAO.get_by_id(id)
    if not record:
        return jsonify({'error': 'Not found'}), 404
    return jsonify(record.to_dict()), 200

@uc_bp.route('/', methods=['POST'])
def create_uc():
    data = request.json
    try:
        record = UcDAO.create(data)
        return jsonify(record.to_dict()), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@uc_bp.route('/<int:id>', methods=['PUT'])
def update_uc(id):
    data = request.json
    try:
        record = UcDAO.update(id, data)
        if not record:
            return jsonify({'error': 'Not found'}), 404
        return jsonify(record.to_dict()), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@uc_bp.route('/<int:id>', methods=['DELETE'])
def delete_uc(id):
    success = UcDAO.delete(id)
    if not success:
        return jsonify({'error': 'Not found'}), 404
    return jsonify({'message': 'Deleted successfully'}), 200

# ----------- Blueprint: UsuarioKahoot -----------
usuario_kahoot_bp = Blueprint('usuario_kahoot', __name__, url_prefix='/api/kahoots')

@usuario_kahoot_bp.route('/', methods=['GET'])
def get_kahoots():
    records = UsuarioKahootDAO.get_all()
    return jsonify([r.to_dict() for r in records]), 200

@usuario_kahoot_bp.route('/<int:id>', methods=['GET'])
def get_kahoot(id):
    record = UsuarioKahootDAO.get_by_id(id)
    if not record:
        return jsonify({'error': 'Not found'}), 404
    return jsonify(record.to_dict()), 200

@usuario_kahoot_bp.route('/', methods=['POST'])
def create_kahoot():
    data = request.json
    try:
        record = UsuarioKahootDAO.create(data)
        return jsonify(record.to_dict()), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@usuario_kahoot_bp.route('/<int:id>', methods=['PUT'])
def update_kahoot(id):
    data = request.json
    try:
        record = UsuarioKahootDAO.update(id, data)
        if not record:
            return jsonify({'error': 'Not found'}), 404
        return jsonify(record.to_dict()), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@usuario_kahoot_bp.route('/<int:id>', methods=['DELETE'])
def delete_kahoot(id):
    success = UsuarioKahootDAO.delete(id)
    if not success:
        return jsonify({'error': 'Not found'}), 404
    return jsonify({'message': 'Deleted successfully'}), 200

# ----------- Blueprint: Ponto -----------
ponto_bp = Blueprint('ponto', __name__, url_prefix='/api/pontos')

@ponto_bp.route('/', methods=['GET'])
def get_pontos():
    records = PontoDAO.get_all()
    return jsonify([r.to_dict() for r in records]), 200

@ponto_bp.route('/<int:id>', methods=['GET'])
def get_ponto(id):
    record = PontoDAO.get_by_id(id)
    if not record:
        return jsonify({'error': 'Not found'}), 404
    return jsonify(record.to_dict()), 200

@ponto_bp.route('/', methods=['POST'])
def create_ponto():
    data = request.json
    try:
        record = PontoDAO.create(data)
        return jsonify(record.to_dict()), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@ponto_bp.route('/<int:id>', methods=['PUT'])
def update_ponto(id):
    data = request.json
    try:
        record = PontoDAO.update(id, data)
        if not record:
            return jsonify({'error': 'Not found'}), 404
        return jsonify(record.to_dict()), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@ponto_bp.route('/<int:id>', methods=['DELETE'])
def delete_ponto(id):
    success = PontoDAO.delete(id)
    if not success:
        return jsonify({'error': 'Not found'}), 404
    return jsonify({'message': 'Deleted successfully'}), 200

# ----------- Blueprint: Curso -----------
curso_bp = Blueprint('curso', __name__, url_prefix='/api/cursos')

@curso_bp.route('/', methods=['GET'])
def get_cursos():
    records = CursoDAO.get_all()
    return jsonify([r.to_dict() for r in records]), 200

@curso_bp.route('/<int:id>', methods=['GET'])
def get_curso(id):
    record = CursoDAO.get_by_id(id)
    if not record:
        return jsonify({'error': 'Not found'}), 404
    return jsonify(record.to_dict()), 200

@curso_bp.route('/', methods=['POST'])
def create_curso():
    data = request.json
    try:
        record = CursoDAO.create(data)
        return jsonify(record.to_dict()), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@curso_bp.route('/<int:id>', methods=['PUT'])
def update_curso(id):
    data = request.json
    try:
        record = CursoDAO.update(id, data)
        if not record:
            return jsonify({'error': 'Not found'}), 404
        return jsonify(record.to_dict()), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@curso_bp.route('/<int:id>', methods=['DELETE'])
def delete_curso(id):
    success = CursoDAO.delete(id)
    if not success:
        return jsonify({'error': 'Not found'}), 404
    return jsonify({'message': 'Deleted successfully'}), 200

# ----------- Blueprint: UsuarioCurso -----------
usuario_curso_bp = Blueprint('usuario_curso', __name__, url_prefix='/api/matriculas')

@usuario_curso_bp.route('/', methods=['GET'])
def get_matriculas():
    records = UsuarioCursoDAO.get_all()
    return jsonify([r.to_dict() for r in records]), 200

@usuario_curso_bp.route('/<int:id>', methods=['GET'])
def get_matricula(id):
    record = UsuarioCursoDAO.get_by_id(id)
    if not record:
        return jsonify({'error': 'Not found'}), 404
    return jsonify(record.to_dict()), 200

@usuario_curso_bp.route('/', methods=['POST'])
def create_matricula():
    data = request.json
    try:
        record = UsuarioCursoDAO.create(data)
        return jsonify(record.to_dict()), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@usuario_curso_bp.route('/<int:id>', methods=['PUT'])
def update_matricula(id):
    data = request.json
    try:
        record = UsuarioCursoDAO.update(id, data)
        if not record:
            return jsonify({'error': 'Not found'}), 404
        return jsonify(record.to_dict()), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@usuario_curso_bp.route('/<int:id>', methods=['DELETE'])
def delete_matricula(id):
    success = UsuarioCursoDAO.delete(id)
    if not success:
        return jsonify({'error': 'Not found'}), 404
    return jsonify({'message': 'Deleted successfully'}), 200
