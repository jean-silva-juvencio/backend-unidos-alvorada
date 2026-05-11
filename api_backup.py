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
        return jsonify({'success': True, 'message': 'Tabela noticias criada!'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})
