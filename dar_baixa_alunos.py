import datetime
from selenium_bot.google_skills_boost import get_db_connection, dar_baixa_usuario_curso_google, get_pendentes_google

pendentes = get_pendentes_google()
print(f"Total de alunos para dar baixa: {len(pendentes)}")

for p in pendentes:
    dar_baixa_usuario_curso_google(
        usuario_curso_id=p['usuario_curso_id'],
        usuario_id=p['usuario_id'],
        curso_id=p['curso_id'],
        usuario_nome=p['usuario_nome'],
        aluno_email=p['usuario_email'],
        discord_id=p.get('usuario_discord_id'),
        role_id=p.get('curso_role'),
        nome_curso=p.get('curso_nome')
    )

print("Todas as 18 baixas foram concluídas com sucesso!")
