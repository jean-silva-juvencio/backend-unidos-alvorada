from flask import Flask, request, jsonify
from flask_cors import CORS
import mysql.connector
from datetime import datetime, timedelta
import bcrypt
import secrets
import requests
from bs4 import BeautifulSoup

app = Flask(__name__)
CORS(app)

# ========== CONEXÃO COM BANCO ==========
def conectar_banco():
    return mysql.connector.connect(
        host='gateway01.us-east-1.prod.aws.tidbcloud.com',
        port=4000,
        user='qnJBUPjz1FvMcd5.root',
        password='Kj3B96xmJxpWhc0F',
        database='alvorada'
    )

# ========== SESSÕES ==========
sessoes = {}

def criar_token():
    return secrets.token_urlsafe(32)

def verificar_sessao(token):
    if not token:
        return None
    sessao = sessoes.get(token)
    if sessao and sessao.get('expiracao') > datetime.now():
        return sessao.get('usuario')
    if token in sessoes:
        del sessoes[token]
    return None

# ========== LOGIN ==========
@app.route('/login', methods=['POST'])
def login():
    try:
        dados = request.json
        email = dados.get('email')
        senha = dados.get('senha')
        
        if not email or not senha:
            return jsonify({'success': False, 'error': 'E-mail e senha são obrigatórios'})
        
        conn = conectar_banco()
        cursor = conn.cursor()
        cursor.execute("SELECT id, email, senha_hash, nome, nivel FROM usuarios WHERE email = %s", (email,))
        usuario = cursor.fetchone()
        conn.close()
        
        if not usuario:
            return jsonify({'success': False, 'error': 'E-mail ou senha inválidos'})
        
        if not bcrypt.checkpw(senha.encode(), usuario[2].encode()):
            return jsonify({'success': False, 'error': 'E-mail ou senha inválidos'})
        
        token = criar_token()
        sessoes[token] = {
            'usuario': {
                'id': usuario[0],
                'email': usuario[1],
                'nome': usuario[3],
                'nivel': usuario[4]
            },
            'expiracao': datetime.now() + timedelta(days=7)
        }
        
        return jsonify({'success': True, 'token': token, 'usuario': {'id': usuario[0], 'email': usuario[1], 'nome': usuario[3], 'nivel': usuario[4]}})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/verificar_sessao', methods=['POST'])
def verificar_sessao_route():
    try:
        dados = request.json
        token = dados.get('token')
        usuario = verificar_sessao(token)
        if usuario:
            return jsonify({'success': True, 'usuario': usuario})
        return jsonify({'success': False, 'error': 'Sessão expirada'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# ========== BUSCAR RITMISTAS ==========
@app.route('/exec', methods=['GET'])
def exec_google_sheets():
    acao = request.args.get('acao')
    
    if acao == 'buscarTodosRitmistas':
        try:
            conn = conectar_banco()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, nome, instrumento, nivel, telefone, email, cep, endereco, 
                       numero, bairro, cidade, estado, blusa, status, data_nasc, data_cadastro,
                       avaliacao_tipo, avaliacao_nota, avaliacao_comentario,
                       como_conheceu, como_conheceu_outro
                FROM ritmistas
            """)
            resultados = cursor.fetchall()
            conn.close()
            
            ritmistas = []
            for r in resultados:
                ritmistas.append({
                    'id': r[0], 'nome': r[1], 'instrumento': r[2], 'nivel': r[3],
                    'telefone': r[4], 'email': r[5], 'cep': r[6], 'endereco': r[7],
                    'numero': r[8], 'bairro': r[9], 'cidade': r[10], 'estado': r[11],
                    'blusa': r[12], 'status': r[13],
                    'dataNasc': r[14].strftime("%Y-%m-%d") if r[14] else '',
                    'dataCadastro': r[15].strftime("%d/%m/%Y, %H:%M:%S") if r[15] else '',
                    'avaliacao_tipo': r[16] if len(r) > 16 else None,
                    'avaliacao_nota': r[17] if len(r) > 17 else None,
                    'avaliacao_comentario': r[18] if len(r) > 18 else None,
                    'como_conheceu': r[19] if len(r) > 19 else None,
                    'como_conheceu_outro': r[20] if len(r) > 20 else None
                })
            
            return jsonify({'success': True, 'ritmistas': ritmistas})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)})
    
    return jsonify({'success': False, 'error': 'Ação não encontrada'})

# ========== ATUALIZAR STATUS ==========
@app.route('/atualizar_status', methods=['POST'])
def atualizar_status():
    try:
        dados = request.json
        nome = dados.get('nome')
        novo_status = dados.get('status')
        
        if not nome or not novo_status:
            return jsonify({'success': False, 'error': 'Nome e status são obrigatórios'})
        
        conn = conectar_banco()
        cursor = conn.cursor()
        status_banco = 'ATIVO' if novo_status == 'Ativo' else 'DESATIVADO'
        cursor.execute("UPDATE ritmistas SET status = %s WHERE nome = %s", (status_banco, nome))
        conn.commit()
        conn.close()
        
        return jsonify({'success': True, 'message': 'Status atualizado'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# ========== EDITAR RITMISTA ==========
@app.route('/editar_ritmista', methods=['POST'])
def editar_ritmista():
    try:
        dados = request.json.get('dados', {})
        ritmista_id = dados.get('id')
        
        if not ritmista_id:
            return jsonify({'success': False, 'error': 'ID do ritmista é obrigatório'})
        
        conn = conectar_banco()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE ritmistas 
            SET nome = %s, data_nasc = %s, telefone = %s, email = %s,
                cep = %s, endereco = %s, numero = %s, bairro = %s,
                cidade = %s, estado = %s, instrumento = %s, nivel = %s,
                blusa = %s, status = %s
            WHERE id = %s
        """, (
            dados.get('nome'), dados.get('dataNasc'), dados.get('telefone'),
            dados.get('email'), dados.get('cep'), dados.get('endereco'),
            dados.get('numero'), dados.get('bairro'), dados.get('cidade'),
            dados.get('estado'), dados.get('instrumento'), dados.get('nivel'),
            dados.get('blusa'), dados.get('status'), ritmista_id
        ))
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'message': 'Ritmista atualizado!'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# ========== EXCLUIR RITMISTA ==========
@app.route('/excluir_ritmista', methods=['DELETE'])
def excluir_ritmista():
    try:
        dados = request.json
        nome = dados.get('nome')
        
        if not nome:
            return jsonify({'success': False, 'error': 'Nome é obrigatório'})
        
        conn = conectar_banco()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM ritmistas WHERE nome = %s", (nome,))
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'message': 'Ritmista excluído!'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# ========== INSCRIÇÃO DE NOVO RITMISTA ==========
@app.route('/inscricao', methods=['POST'])
def inscricao():
    try:
        dados = request.json
        conn = conectar_banco()
        cursor = conn.cursor()
        
        email = dados.get('email')
        cursor.execute("SELECT id FROM ritmistas WHERE email = %s", (email,))
        if cursor.fetchone():
            conn.close()
            return jsonify({'success': False, 'error': 'E-mail já cadastrado!'})
        
        cursor.execute("""
            INSERT INTO ritmistas 
            (nome, data_nasc, telefone, email, cep, endereco, numero, bairro, 
             cidade, estado, instrumento, nivel, blusa, status, 
             avaliacao_tipo, avaliacao_nota, avaliacao_comentario,
             como_conheceu, como_conheceu_outro)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'PENDENTE', %s, %s, %s, %s, %s)
        """, (
            dados.get('nome'), dados.get('dataNasc'), dados.get('telefone'),
            dados.get('email'), dados.get('cep'), dados.get('endereco'),
            dados.get('numero'), dados.get('bairro'), dados.get('cidade'),
            dados.get('estado'), dados.get('instrumento'), dados.get('nivel'),
            dados.get('blusa'),
            dados.get('avaliacao_tipo'),
            dados.get('avaliacao_nota'),
            dados.get('avaliacao_comentario'),
            dados.get('como_conheceu'),
            dados.get('como_conheceu_outro')
        ))
        conn.commit()
        conn.close()
        
        return jsonify({'success': True, 'message': 'Inscrição enviada com sucesso!'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# ========== RANKING DE PRESENÇA ==========
@app.route('/ranking_presenca', methods=['GET'])
def ranking_presenca():
    try:
        conn = conectar_banco()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(DISTINCT data) FROM chamadas")
        total_chamadas = cursor.fetchone()[0] or 1
        cursor.execute("""
            SELECT r.id, r.nome, r.instrumento, r.nivel,
                   COUNT(CASE WHEN c.status = 'PRESENTE' THEN 1 END) as presentes,
                   COUNT(CASE WHEN c.status = 'AUSENTE' THEN 1 END) as ausentes
            FROM ritmistas r
            LEFT JOIN chamadas c ON c.ritmista_id = r.id
            WHERE LOWER(r.status) = 'ativo'
            GROUP BY r.id
            ORDER BY (presentes * 100.0 / NULLIF(presentes + ausentes, 0)) DESC, presentes DESC
        """)
        resultados = cursor.fetchall()
        conn.close()
        ranking = []
        for r in resultados:
            id_r, nome, instrumento, nivel, presentes, ausentes = r
            percentual = round((presentes / total_chamadas) * 100, 1) if total_chamadas > 0 else 0
            ranking.append({'id': id_r, 'nome': nome, 'instrumento': instrumento or '-', 'nivel': nivel or '-', 'presentes': presentes, 'ausentes': ausentes, 'percentual': percentual})
        return jsonify({'success': True, 'ranking': ranking, 'total_chamadas': total_chamadas})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# ========== PRESENÇA POR PERÍODO ==========
@app.route('/presenca_periodo', methods=['GET'])
def presenca_periodo():
    try:
        inicio = request.args.get('inicio')
        fim = request.args.get('fim')
        if not inicio or not fim:
            return jsonify({'success': False, 'error': 'Datas de início e fim são obrigatórias'})
        conn = conectar_banco()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT COUNT(CASE WHEN status = 'PRESENTE' THEN 1 END) as presentes,
                   COUNT(CASE WHEN status = 'AUSENTE' THEN 1 END) as ausentes
            FROM chamadas WHERE data BETWEEN %s AND %s
        """, (inicio, fim))
        resultado = cursor.fetchone()
        conn.close()
        return jsonify({'success': True, 'presentes': resultado[0] or 0, 'ausentes': resultado[1] or 0})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# ========== LISTAR CHAMADAS ==========
@app.route('/listar_chamadas', methods=['GET'])
def listar_chamadas():
    try:
        conn = conectar_banco()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT data, 
                   COUNT(CASE WHEN status = 'PRESENTE' THEN 1 END) as presentes,
                   COUNT(CASE WHEN status = 'AUSENTE' THEN 1 END) as ausentes
            FROM chamadas
            GROUP BY data
            ORDER BY data DESC
        """)
        resultados = cursor.fetchall()
        conn.close()
        
        chamadas = []
        for r in resultados:
            chamadas.append({
                'data': r[0].strftime("%Y-%m-%d"),
                'presentes': r[1],
                'ausentes': r[2]
            })
        
        return jsonify({'success': True, 'chamadas': chamadas})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# ========== DETALHES DE UMA CHAMADA ==========
@app.route('/chamada', methods=['GET'])
def detalhes_chamada():
    try:
        data = request.args.get('data')
        if not data:
            return jsonify({'success': False, 'error': 'Data é obrigatória'})
        
        conn = conectar_banco()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT r.nome, c.status
            FROM chamadas c
            JOIN ritmistas r ON c.ritmista_id = r.id
            WHERE c.data = %s
        """, (data,))
        resultados = cursor.fetchall()
        conn.close()
        
        presentes = [r[0] for r in resultados if r[1] == 'PRESENTE']
        ausentes = [r[0] for r in resultados if r[1] == 'AUSENTE']
        
        return jsonify({'success': True, 'presentes': presentes, 'ausentes': ausentes})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# ========== SALVAR CHAMADA ==========
@app.route('/salvar_chamada', methods=['POST'])
def salvar_chamada():
    try:
        dados = request.json
        data = dados.get('data')
        presencas = dados.get('presencas')
        if not data or not presencas:
            return jsonify({'success': False, 'error': 'Data e presenças são obrigatórios'})
        
        conn = conectar_banco()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM chamadas WHERE data = %s LIMIT 1", (data,))
        if cursor.fetchone():
            conn.close()
            return jsonify({'success': False, 'error': 'Chamada já registrada para esta data'})
        
        for ritmista_id, status in presencas.items():
            cursor.execute("INSERT INTO chamadas (data, ritmista_id, status) VALUES (%s, %s, %s)", (data, ritmista_id, status))
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'message': 'Chamada salva com sucesso!'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# ==========================================
# ========== NOTÍCIAS ======================
# ==========================================

@app.route('/noticias', methods=['GET'])
def listar_noticias():
    try:
        conn = conectar_banco()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, titulo, resumo, conteudo, imagem_url, autor, data_publicacao, destaque
            FROM noticias
            WHERE status = 'PUBLICADA'
            ORDER BY destaque DESC, data_publicacao DESC
        """)
        resultados = cursor.fetchall()
        conn.close()

        noticias = []
        for n in resultados:
            noticias.append({
                'id': n[0], 'titulo': n[1], 'resumo': n[2], 'conteudo': n[3],
                'imagem_url': n[4], 'autor': n[5],
                'data_publicacao': n[6].strftime("%d/%m/%Y às %H:%M") if n[6] else '',
                'destaque': bool(n[7])
            })

        return jsonify({'success': True, 'noticias': noticias})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/noticias/<int:id>', methods=['GET'])
def buscar_noticia(id):
    try:
        conn = conectar_banco()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, titulo, resumo, conteudo, imagem_url, autor, data_publicacao, destaque
            FROM noticias WHERE id = %s AND status = 'PUBLICADA'
        """, (id,))
        n = cursor.fetchone()
        conn.close()

        if not n:
            return jsonify({'success': False, 'error': 'Notícia não encontrada'})

        return jsonify({'success': True, 'noticia': {
            'id': n[0], 'titulo': n[1], 'resumo': n[2], 'conteudo': n[3],
            'imagem_url': n[4], 'autor': n[5],
            'data_publicacao': n[6].strftime("%d/%m/%Y às %H:%M") if n[6] else '',
            'destaque': bool(n[7])
        }})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/noticias/admin/listar', methods=['POST'])
def listar_noticias_admin():
    try:
        dados = request.json
        token = dados.get('token')
        usuario = verificar_sessao(token)
        if not usuario:
            return jsonify({'success': False, 'error': 'Acesso negado'})

        conn = conectar_banco()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, titulo, resumo, autor, data_publicacao, status, destaque
            FROM noticias ORDER BY data_publicacao DESC
        """)
        resultados = cursor.fetchall()
        conn.close()

        noticias = []
        for n in resultados:
            noticias.append({
                'id': n[0], 'titulo': n[1], 'resumo': n[2], 'autor': n[3],
                'data_publicacao': n[4].strftime("%d/%m/%Y às %H:%M") if n[4] else '',
                'status': n[5], 'destaque': bool(n[6])
            })

        return jsonify({'success': True, 'noticias': noticias})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/noticias/criar', methods=['POST'])
def criar_noticia():
    try:
        dados = request.json
        token = dados.get('token')
        usuario = verificar_sessao(token)
        if not usuario:
            return jsonify({'success': False, 'error': 'Acesso negado'})

        titulo = dados.get('titulo', '').strip()
        conteudo = dados.get('conteudo', '').strip()
        if not titulo or not conteudo:
            return jsonify({'success': False, 'error': 'Título e conteúdo são obrigatórios'})

        conn = conectar_banco()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO noticias (titulo, resumo, conteudo, imagem_url, autor, status, destaque, data_publicacao)
            VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
        """, (
            titulo, dados.get('resumo', ''), conteudo, dados.get('imagem_url', ''),
            usuario.get('nome', 'Admin'), dados.get('status', 'PUBLICADA'),
            1 if dados.get('destaque') else 0
        ))
        conn.commit()
        novo_id = cursor.lastrowid
        conn.close()

        return jsonify({'success': True, 'message': 'Notícia criada com sucesso!', 'id': novo_id})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/noticias/editar/<int:id>', methods=['POST'])
def editar_noticia(id):
    try:
        dados = request.json
        token = dados.get('token')
        usuario = verificar_sessao(token)
        if not usuario:
            return jsonify({'success': False, 'error': 'Acesso negado'})

        titulo = dados.get('titulo', '').strip()
        conteudo = dados.get('conteudo', '').strip()
        if not titulo or not conteudo:
            return jsonify({'success': False, 'error': 'Título e conteúdo são obrigatórios'})

        conn = conectar_banco()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE noticias
            SET titulo = %s, resumo = %s, conteudo = %s, imagem_url = %s,
                status = %s, destaque = %s
            WHERE id = %s
        """, (
            titulo, dados.get('resumo', ''), conteudo, dados.get('imagem_url', ''),
            dados.get('status', 'PUBLICADA'), 1 if dados.get('destaque') else 0, id
        ))
        conn.commit()
        conn.close()

        return jsonify({'success': True, 'message': 'Notícia atualizada!'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/noticias/excluir/<int:id>', methods=['DELETE'])
def excluir_noticia(id):
    try:
        dados = request.json
        token = dados.get('token')
        usuario = verificar_sessao(token)
        if not usuario:
            return jsonify({'success': False, 'error': 'Acesso negado'})

        conn = conectar_banco()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM noticias WHERE id = %s", (id,))
        conn.commit()
        conn.close()

        return jsonify({'success': True, 'message': 'Notícia excluída!'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# ==========================================
# ========== BANNERS =======================
# ==========================================

@app.route('/banners', methods=['GET'])
def listar_banners():
    try:
        conn = conectar_banco()
        cursor = conn.cursor()
        cursor.execute("SELECT id, imagem_base64, ordem FROM banners ORDER BY ordem ASC")
        resultados = cursor.fetchall()
        conn.close()
        
        banners = []
        for b in resultados:
            banners.append({
                'id': b[0],
                'imagem_base64': b[1],
                'ordem': b[2]
            })
        
        return jsonify({'success': True, 'banners': banners})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/banners/criar', methods=['POST'])
def criar_banner():
    try:
        dados = request.json
        imagem_base64 = dados.get('imagem_base64')
        ordem = dados.get('ordem', 0)
        
        if not imagem_base64:
            return jsonify({'success': False, 'error': 'Imagem é obrigatória'})
        
        conn = conectar_banco()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO banners (imagem_base64, ordem)
            VALUES (%s, %s)
        """, (imagem_base64, ordem))
        conn.commit()
        conn.close()
        
        return jsonify({'success': True, 'message': 'Banner adicionado!'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/banners/excluir/<int:id>', methods=['DELETE'])
def excluir_banner(id):
    try:
        conn = conectar_banco()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM banners WHERE id = %s", (id,))
        conn.commit()
        conn.close()
        
        return jsonify({'success': True, 'message': 'Banner excluído!'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# ==========================================
# ========== BUSCA NA WEB ==================
# ==========================================

def buscar_duckduckgo(query):
    try:
        url = f"https://html.duckduckgo.com/html/?q={query.replace(' ', '+')}"
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        response = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        resultados = []
        for result in soup.select('.result')[:5]:
            titulo = result.select_one('.result__a')
            snippet = result.select_one('.result__snippet')
            link = result.select_one('.result__url')
            
            if titulo and snippet:
                resultados.append({
                    'titulo': titulo.get_text(strip=True),
                    'resumo': snippet.get_text(strip=True),
                    'link': link.get_text(strip=True) if link else ''
                })
        
        if resultados:
            texto = "\n\n".join([f"🔍 {r['titulo']}\n📄 {r['resumo'][:300]}\n🔗 {r['link']}" for r in resultados])
            return texto
        return "Nenhum resultado encontrado para esta busca."
    except Exception as e:
        print(f"Erro na busca: {e}")
        return "Erro ao buscar informações. Tente novamente mais tarde."

@app.route('/buscar', methods=['POST'])
def buscar_web():
    try:
        dados = request.json
        query = dados.get('query', '')
        if not query or not query.strip():
            return jsonify({'success': False, 'error': 'Digite o que você quer buscar'})
        resultado = buscar_duckduckgo(query)
        return jsonify({'success': True, 'query': query, 'resultado': resultado, 'fonte': 'DuckDuckGo'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# ==========================================
# ========== EXCLUIR COMENTÁRIO ==========
# ==========================================

@app.route('/excluir_comentario', methods=['DELETE'])
def excluir_comentario():
    try:
        dados = request.json
        id_ritmista = dados.get('id')
        
        if not id_ritmista:
            return jsonify({'success': False, 'error': 'ID é obrigatório'})
        
        conn = conectar_banco()
        cursor = conn.cursor()
        
        cursor.execute("SELECT id, nome FROM ritmistas WHERE id = %s", (id_ritmista,))
        ritmista = cursor.fetchone()
        
        if not ritmista:
            conn.close()
            return jsonify({'success': False, 'error': 'Ritmista não encontrado'})
        
        cursor.execute("""
            UPDATE ritmistas 
            SET avaliacao_tipo = NULL, 
                avaliacao_nota = NULL, 
                avaliacao_comentario = NULL
            WHERE id = %s
        """, (id_ritmista,))
        
        conn.commit()
        conn.close()
        
        return jsonify({'success': True, 'message': f'Comentário de {ritmista[1]} excluído com sucesso!'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# ==========================================
# ========== APAGAR CHAMADAS ==============
# ==========================================

@app.route('/apagar_chamadas', methods=['DELETE'])
def apagar_chamadas():
    try:
        dados = request.json
        tipo = dados.get('tipo')
        
        if not tipo:
            return jsonify({'success': False, 'error': 'Tipo é obrigatório'})
        
        conn = conectar_banco()
        cursor = conn.cursor()
        
        if tipo == 'mes':
            agora = datetime.now()
            mes_atual = agora.strftime('%Y-%m')
            cursor.execute("DELETE FROM chamadas WHERE data LIKE %s", (f'{mes_atual}%',))
            meses = ['Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho', 
                     'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro']
            mes_nome = meses[agora.month - 1]
            mensagem = f'Chamadas do mês de {mes_nome}/{agora.year} apagadas com sucesso!'
        elif tipo == 'ano':
            ano_atual = datetime.now().year
            cursor.execute("DELETE FROM chamadas WHERE YEAR(data) = %s", (ano_atual,))
            mensagem = f'Chamadas do ano {ano_atual} apagadas com sucesso!'
        else:
            cursor.execute("DELETE FROM chamadas")
            mensagem = 'Todas as chamadas foram apagadas com sucesso!'
        
        conn.commit()
        conn.close()
        
        return jsonify({'success': True, 'message': mensagem})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# ==========================================
# ========== SETUP =======================
# ==========================================

@app.route('/setup_noticias', methods=['GET'])
def setup_noticias():
    try:
        conn = conectar_banco()
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS noticias (
                id INT AUTO_INCREMENT PRIMARY KEY,
                titulo VARCHAR(255) NOT NULL,
                resumo TEXT,
                conteudo LONGTEXT NOT NULL,
                imagem_url VARCHAR(500),
                autor VARCHAR(100),
                status ENUM('PUBLICADA', 'RASCUNHO') DEFAULT 'PUBLICADA',
                destaque TINYINT(1) DEFAULT 0,
                data_publicacao DATETIME DEFAULT NOW()
            )
        """)
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'message': 'Tabela noticias criada/verificada com sucesso!'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/setup_banners', methods=['GET'])
def setup_banners():
    try:
        conn = conectar_banco()
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS banners (
                id INT AUTO_INCREMENT PRIMARY KEY,
                imagem_base64 LONGTEXT NOT NULL,
                ordem INT DEFAULT 0,
                data_criacao DATETIME DEFAULT NOW()
            )
        """)
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'message': 'Tabela banners criada/verificada com sucesso!'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/setup_avaliacao', methods=['GET'])
def setup_avaliacao():
    try:
        conn = conectar_banco()
        cursor = conn.cursor()
        cursor.execute("ALTER TABLE ritmistas ADD COLUMN IF NOT EXISTS avaliacao_tipo VARCHAR(20) DEFAULT NULL")
        cursor.execute("ALTER TABLE ritmistas ADD COLUMN IF NOT EXISTS avaliacao_nota INT DEFAULT NULL")
        cursor.execute("ALTER TABLE ritmistas ADD COLUMN IF NOT EXISTS avaliacao_comentario TEXT DEFAULT NULL")
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'message': 'Colunas de avaliação adicionadas com sucesso!'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/setup_como_conheceu', methods=['GET'])
def setup_como_conheceu():
    try:
        conn = conectar_banco()
        cursor = conn.cursor()
        cursor.execute("ALTER TABLE ritmistas ADD COLUMN IF NOT EXISTS como_conheceu VARCHAR(50) DEFAULT NULL")
        cursor.execute("ALTER TABLE ritmistas ADD COLUMN IF NOT EXISTS como_conheceu_outro VARCHAR(255) DEFAULT NULL")
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'message': 'Colunas como_conheceu adicionadas com sucesso!'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/setup_all', methods=['GET'])
def setup_all():
    try:
        conn = conectar_banco()
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS noticias (
                id INT AUTO_INCREMENT PRIMARY KEY,
                titulo VARCHAR(255) NOT NULL,
                resumo TEXT,
                conteudo LONGTEXT NOT NULL,
                imagem_url VARCHAR(500),
                autor VARCHAR(100),
                status ENUM('PUBLICADA', 'RASCUNHO') DEFAULT 'PUBLICADA',
                destaque TINYINT(1) DEFAULT 0,
                data_publicacao DATETIME DEFAULT NOW()
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS banners (
                id INT AUTO_INCREMENT PRIMARY KEY,
                imagem_base64 LONGTEXT NOT NULL,
                ordem INT DEFAULT 0,
                data_criacao DATETIME DEFAULT NOW()
            )
        """)
        
        try:
            cursor.execute("ALTER TABLE ritmistas ADD COLUMN IF NOT EXISTS avaliacao_tipo VARCHAR(20) DEFAULT NULL")
            cursor.execute("ALTER TABLE ritmistas ADD COLUMN IF NOT EXISTS avaliacao_nota INT DEFAULT NULL")
            cursor.execute("ALTER TABLE ritmistas ADD COLUMN IF NOT EXISTS avaliacao_comentario TEXT DEFAULT NULL")
            cursor.execute("ALTER TABLE ritmistas ADD COLUMN IF NOT EXISTS como_conheceu VARCHAR(50) DEFAULT NULL")
            cursor.execute("ALTER TABLE ritmistas ADD COLUMN IF NOT EXISTS como_conheceu_outro VARCHAR(255) DEFAULT NULL")
        except:
            pass
        
        conn.commit()
        conn.close()
        
        return jsonify({'success': True, 'message': 'Todas as tabelas e colunas foram configuradas!'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# ========== INÍCIO DA API ==========
if __name__ == '__main__':
    print("=" * 50)
    print("🚀 API Unidos do Alvorada rodando!")
    print("📍 Endpoints disponíveis:")
    print("   - GET  /exec?acao=buscarTodosRitmistas")
    print("   - POST /login")
    print("   - POST /atualizar_status")
    print("   - POST /editar_ritmista")
    print("   - DELETE /excluir_ritmista")
    print("   - POST /inscricao")
    print("   - DELETE /excluir_comentario")
    print("   - DELETE /apagar_chamadas")  # NOVO ENDPOINT
    print("   - GET  /ranking_presenca")
    print("   - GET  /presenca_periodo")
    print("   - GET  /listar_chamadas")
    print("   - GET  /chamada?data=...")
    print("   - POST /salvar_chamada")
    print("   --- NOTÍCIAS ---")
    print("   - GET  /noticias")
    print("   - GET  /noticias/<id>")
    print("   - POST /noticias/admin/listar")
    print("   - POST /noticias/criar")
    print("   - POST /noticias/editar/<id>")
    print("   - DELETE /noticias/excluir/<id>")
    print("   --- BANNERS ---")
    print("   - GET  /banners")
    print("   - POST /banners/criar")
    print("   - DELETE /banners/excluir/<id>")
    print("   --- BUSCA NA WEB ---")
    print("   - POST /buscar")
    print("   --- SETUP ---")
    print("   - GET  /setup_noticias")
    print("   - GET  /setup_banners")
    print("   - GET  /setup_avaliacao")
    print("   - GET  /setup_como_conheceu")
    print("   - GET  /setup_all")
    print("=" * 50)
    app.run(host='0.0.0.0', port=5000, debug=True)
