import os
import sys
import pymysql
import pandas as pd
from dotenv import load_dotenv

def main():
    # Caminho do arquivo .env a partir da raiz do projeto
    script_dir = os.path.dirname(os.path.abspath(__file__))
    root_dir = os.path.abspath(os.path.join(script_dir, ".."))
    dotenv_path = os.path.join(root_dir, ".env")
    
    # Carrega variáveis do arquivo .env se ele existir
    if os.path.exists(dotenv_path):
        load_dotenv(dotenv_path)
    else:
        print(f"Aviso: Arquivo .env não encontrado em: {dotenv_path}")

    # Configuração do banco de dados
    db_user = os.getenv('DB_USER')
    db_password = os.getenv('DB_PASSWORD')
    db_host = os.getenv('DB_HOST')
    db_port_env = os.getenv('DB_PORT', '3306')
    db_name = os.getenv('DB_NAME')

    # Validação do parâmetro de entrada (nome da UC)
    if len(sys.argv) < 2:
        print("Erro: O nome da UC deve ser passado como parâmetro.")
        print("Uso:")
        print("  python scripts/gerar_pontos_uc.py \"<nome_da_uc>\"")
        sys.exit(1)

    uc_nome_busca = sys.argv[1].strip()

    if not db_user or not db_password or not db_host or not db_name:
        print("Erro: Configurações de banco de dados incompletas no arquivo .env.")
        print("Por favor, verifique se as variáveis DB_USER, DB_PASSWORD, DB_HOST e DB_NAME estão definidas.")
        sys.exit(1)

    try:
        db_port = int(db_port_env)
    except ValueError:
        db_port = 3306

    print(f"Conectando ao banco de dados em {db_host}:{db_port}...")
    try:
        connection = pymysql.connect(
            host=db_host,
            port=db_port,
            user=db_user,
            password=db_password,
            database=db_name,
            charset='utf8mb4',
            cursorclass=pymysql.cursors.DictCursor,
            connect_timeout=3
        )
    except Exception as e:
        print(f"Erro ao conectar ao banco de dados: {e}")
        sys.exit(1)

    try:
        with connection.cursor() as cursor:
            # Buscar a UC correspondente (primeiro correspondência exata)
            sql_uc = "SELECT uc_id, uc_nome FROM uc WHERE uc_nome = %s"
            cursor.execute(sql_uc, (uc_nome_busca,))
            uc_record = cursor.fetchone()

            if not uc_record:
                # Caso não encontre exatamente, tenta por aproximação (LIKE)
                sql_uc_like = "SELECT uc_id, uc_nome FROM uc WHERE uc_nome LIKE %s"
                cursor.execute(sql_uc_like, (f"%{uc_nome_busca}%",))
                results = cursor.fetchall()
                
                if len(results) == 1:
                    uc_record = results[0]
                    print(f"UC não encontrada exatamente com o nome '{uc_nome_busca}'. Usando correspondência única encontrada: '{uc_record['uc_nome']}'")
                elif len(results) > 1:
                    print(f"Erro: Múltiplas UCs encontradas por aproximação para '{uc_nome_busca}':")
                    for r in results:
                        print(f" - {r['uc_nome']}")
                    print("Por favor, especifique o nome de forma mais exata.")
                    sys.exit(1)
                else:
                    print(f"Erro: Nenhuma UC encontrada com o nome '{uc_nome_busca}'.")
                    # Listar UCs existentes para auxiliar o usuário
                    cursor.execute("SELECT uc_nome FROM uc ORDER BY uc_nome")
                    all_ucs = cursor.fetchall()
                    if all_ucs:
                        print("\nUCs cadastradas no banco de dados:")
                        for r in all_ucs:
                            print(f" - {r['uc_nome']}")
                    sys.exit(1)

            uc_id = uc_record['uc_id']
            uc_nome = uc_record['uc_nome']

            print(f"Buscando e somando pontos da UC: '{uc_nome}' (ID: {uc_id})...")

            # Query para agrupar por nome do aluno e somar os pontos
            sql_pontos = """
                SELECT u.usuario_nome AS nome, SUM(p.num_ponto) AS pontos_a3
                FROM ponto p
                INNER JOIN usuario u ON p.usuario_id = u.usuario_id
                WHERE p.uc_id = %s
                GROUP BY u.usuario_nome
                ORDER BY u.usuario_nome ASC
            """
            cursor.execute(sql_pontos, (uc_id,))
            rows = cursor.fetchall()

            if not rows:
                print(f"Aviso: Nenhum ponto encontrado para a UC '{uc_nome}'. Gerando planilha vazia.")
                df = pd.DataFrame(columns=['nome', 'pontos_a3'])
            else:
                df = pd.DataFrame(rows)

            # Sanitização do nome do arquivo (removendo caracteres inválidos para sistema de arquivos)
            safe_filename = "".join(c for c in uc_nome if c.isalnum() or c in (' ', '_', '-')).strip()
            excel_name = f"{safe_filename}.xlsx"
            excel_path = os.path.join(os.getcwd(), excel_name)

            try:
                # Salva o DataFrame como Excel usando engine openpyxl (padrão do pandas moderno para xlsx)
                df.to_excel(excel_path, index=False)
                print(f"\nSucesso! Planilha gerada em:")
                print(f"  {excel_path}")
                print(f"Total de registros exportados: {len(df)}")
            except ImportError:
                print("\nErro: A biblioteca 'openpyxl' é necessária para gerar arquivos Excel (.xlsx) pelo Pandas.")
                print("Por favor, instale-a executando:")
                print("  pip install openpyxl")
                sys.exit(1)
            except Exception as e:
                print(f"\nErro ao salvar o arquivo Excel: {e}")
                sys.exit(1)

    finally:
        connection.close()

if __name__ == "__main__":
    main()
