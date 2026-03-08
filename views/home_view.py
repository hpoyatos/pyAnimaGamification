from flask import Blueprint, render_template

home_ui_bp = Blueprint('home_ui', __name__, url_prefix='/ui')

@home_ui_bp.route('/')
def index():
    return render_template('home.html')
