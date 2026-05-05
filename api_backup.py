from flask import Flask, request, jsonify
from flask_cors import CORS
import mysql.connector
from datetime import datetime, timedelta
import bcrypt
import secrets

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
            cursor.execute("SELECT id, nome, instrumento, nivel, telefone, email, cep, endereco, numero, bairro, cidade, estado, blusa, status, data_nasc, data_cadastro FROM ritmistas")
            resultados = cursor.fetchall()
            conn.close()
            
            ritmistas = []
            for r in resultados:
                ritmistas.append({
                    'id': r[0],
                    'nome': r[1],
                    'instrumento': r[2],
                    'nivel': r[3],
                    'telefone': r[4],
                    'email': r[5],
                    'cep': r[6],
                    'endereco': r[7],
                    'numero': r[8],
                    'bairro': r[9],
                    'cidade': r[10],
                    'estado': r[11],
                    'blusa': r[12],
                    'status': r[13],
                    'dataNasc': r[14].strftime("%Y-%m-%d") if r[14] else '',
                    'dataCadastro': r[15].strftime("%d/%m/%Y, %H:%M:%S") if r[15] else ''
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
        
        return jsonify({'success': True, 'message': f'Status atualizado'})
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
        
        return jsonify({'success': True, 'message': f'Ritmista excluído!'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# ========== INSCRIÇÃO DE NOVO RITMISTA ==========
@app.route('/inscricao', methods=['POST'])
def inscricao():
    try:
        dados = request.json
        
        conn = conectar_banco()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO ritmistas 
            (nome, data_nasc, telefone, email, cep, endereco, numero, bairro, cidade, estado, instrumento, nivel, blusa, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'PENDENTE')
        """, (
            dados.get('nome'), dados.get('dataNasc'), dados.get('telefone'),
            dados.get('email'), dados.get('cep'), dados.get('endereco'),
            dados.get('numero'), dados.get('bairro'), dados.get('cidade'),
            dados.get('estado'), dados.get('instrumento'), dados.get('nivel'),
            dados.get('blusa')
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
        total_chamadas = cursor.fetchone()[0]
        if not total_chamadas:
            total_chamadas = 1
        
        cursor.execute("""
            SELECT r.id, r.nome, r.instrumento, r.nivel,
                   COUNT(CASE WHEN c.status = 'PRESENTE' THEN 1 END) as presentes,
                   COUNT(CASE WHEN c.status = 'AUSENTE' THEN 1 END) as ausentes
            FROM ritmistas r
            LEFT JOIN chamadas c ON c.ritmista_id = r.id
            WHERE LOWER(r.status) = 'ativo'
            GROUP BY r.id
            ORDER BY (presentes * 100.0 / NULLIF(presentes + ausentes, 0)) DESC
        """)
        
        resultados = cursor.fetchall()
        conn.close()
        
        ranking = []
        for r in resultados:
            id_r, nome, instrumento, nivel, presentes, ausentes = r
            percentual = round((presentes / total_chamadas) * 100, 1) if total_chamadas > 0 else 0
            ranking.append({
                'id': id_r,
                'nome': nome,
                'instrumento': instrumento or '-',
                'nivel': nivel or '-',
                'presentes': presentes,
                'ausentes': ausentes,
                'percentual': percentual
            })
        
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
        
        query = """
            SELECT 
                COUNT(CASE WHEN status = 'PRESENTE' THEN 1 END) as presentes,
                COUNT(CASE WHEN status = 'AUSENTE' THEN 1 END) as ausentes
            FROM chamadas
            WHERE data BETWEEN %s AND %s
        """
        cursor.execute(query, (inicio, fim))
        resultado = cursor.fetchone()
        conn.close()
        
        presentes = resultado[0] if resultado[0] else 0
        ausentes = resultado[1] if resultado[1] else 0
        
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
            cursor.execute("""
                INSERT INTO chamadas (data, ritmista_id, status)
                VALUES (%s, %s, %s)
            """, (data, ritmista_id, status))
        
        conn.commit()
        conn.close()
        
        return jsonify({'success': True, 'message': 'Chamada salva com sucesso!'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# ========== LISTAR CHAMADAS ==========
@app.route('/listar_chamadas', methods=['GET'])
def listar_chamadas():
    try:
        conn = conectar_banco()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT DISTINCT data, 
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

# ========== LIMPAR CHAMADAS ==========
@app.route('/limpar_chamadas', methods=['POST'])
def limpar_chamadas():
    try:
        dados = request.json
        tipo = dados.get('tipo')
        valor = dados.get('valor')
        
        if not tipo:
            return jsonify({'success': False, 'error': 'Tipo de limpeza é obrigatório'})
        
        conn = conectar_banco()
        cursor = conn.cursor()
        
        if tipo == 'tudo':
            cursor.execute("DELETE FROM chamadas")
            mensagem = "Todas as chamadas foram excluídas!"
            excluidas = cursor.rowcount
            
        elif tipo == 'mes':
            if not valor:
                return jsonify({'success': False, 'error': 'Mês é obrigatório (formato: YYYY-MM)'})
            cursor.execute("DELETE FROM chamadas WHERE DATE_FORMAT(data, '%Y-%m') = %s", (valor,))
            mensagem = f"Chamadas do mês {valor} excluídas!"
            excluidas = cursor.rowcount
            
        elif tipo == 'ano':
            if not valor:
                return jsonify({'success': False, 'error': 'Ano é obrigatório (formato: YYYY)'})
            cursor.execute("DELETE FROM chamadas WHERE YEAR(data) = %s", (valor,))
            mensagem = f"Chamadas do ano {valor} excluídas!"
            excluidas = cursor.rowcount
            
        elif tipo == 'semana':
            cursor.execute("DELETE FROM chamadas WHERE data >= DATE_SUB(CURDATE(), INTERVAL 7 DAY)")
            mensagem = "Chamadas da última semana excluídas!"
            excluidas = cursor.rowcount
            
        else:
            conn.close()
            return jsonify({'success': False, 'error': 'Tipo inválido'})
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True, 
            'message': mensagem,
            'excluidas': excluidas
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# ========== INÍCIO DA API ==========
if __name__ == '__main__':
    print("=" * 50)
    print("🚀 API Unidos do Alvorada rodando!")
    print("📍 Endpoints disponíveis:")
    print("   - http://localhost:5000/exec?acao=buscarTodosRitmistas")
    print("   - http://localhost:5000/login")
    print("   - http://localhost:5000/atualizar_status")
    print("   - http://localhost:5000/editar_ritmista")
    print("   - http://localhost:5000/inscricao")
    print("   - http://localhost:5000/ranking_presenca")
    print("   - http://localhost:5000/presenca_periodo")
    print("   - http://localhost:5000/salvar_chamada")
    print("   - http://localhost:5000/listar_chamadas")
    print("   - http://localhost:5000/limpar_chamadas")
    print("=" * 50)
    app.run(host='0.0.0.0', port=5000, debug=True)
