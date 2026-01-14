# -*- coding: utf-8 -*-
from flask import Flask, jsonify, request, send_file
from flask_cors import CORS
import pandas as pd
import os
import io
from datetime import datetime, timezone
from supabase import create_client

app = Flask(__name__)
CORS(app)

base_path = os.path.dirname(__file__)
csv_path = os.path.join(base_path, 'dados.csv')

url = os.environ.get("SUPABASE_URL") or os.environ.get("NEXT_PUBLIC_SUPABASE_URL")
key = os.environ.get("SUPABASE_SECRET_KEY") or os.environ.get("SUPABASE_ANON_KEY")
supabase = create_client(url, key)

df = None
load_error = None

try:
    cols = ['UF', 'POSTO', 'IP', 'UC', 'MEDIDOR']
    df = pd.read_csv(csv_path, sep=';', dtype=str, low_memory=False, usecols=cols)
    df['UC'] = df['UC'].str.strip()
except Exception as e:
    load_error = str(e)
    print(f"Erro ao carregar CSV principal: {load_error}")


def validar_equipe(equipe_raw: str | None) -> str:
    equipe = (equipe_raw or "").strip()
    if not equipe:
        raise ValueError("Parâmetro equipe obrigatório")
    return equipe


def validar_uc_para_int8(uc_raw: str | None) -> int:
    uc = (uc_raw or "").strip()
    if not uc:
        raise ValueError("Parâmetro UC obrigatório")

    if not uc.isdigit():
        raise ValueError("Parâmetro UC inválido (deve conter apenas números)")

    uc_int = int(uc)

    if uc_int > 9223372036854775807:
        raise ValueError("Parâmetro UC inválido (fora do limite do int8)")

    return uc_int


def registrar_uc_nao_encontrada(uc_int: int, equipe: str):
    try:
        data = {
            "equipe": equipe,  
            "uc_pesquisada": uc_int,  
            "data_pesquisa": datetime.now(timezone.utc).isoformat()  
        }
        supabase.table("ucs_nao_encontradas").insert(data).execute()
    except Exception as e:
        print(f"Erro ao salvar no Supabase: {e}")


@app.route('/api/download-logs', methods=['GET'])
def download_logs():
    try:
        response = supabase.table("ucs_nao_encontradas").select("*").execute()

        if not response.data:
            return jsonify({"erro": "Nenhum log encontrado no banco."}), 404

        log_df = pd.DataFrame(response.data)

        proxy = io.StringIO()
        log_df.to_csv(proxy, index=False, sep=';', encoding='utf-8')

        mem = io.BytesIO()
        mem.write(proxy.getvalue().encode('utf-8'))
        mem.seek(0)
        proxy.close()

        return send_file(
            mem,
            mimetype='text/csv',
            as_attachment=True,
            download_name='ucs_nao_encontradas.csv'
        )
    except Exception as e:
        return jsonify({"erro": f"Erro ao gerar CSV: {str(e)}"}), 500


@app.route('/api/consulta', methods=['GET'])
def consultar():
    if df is None:
        return jsonify({"erro": f"Erro interno no banco de dados: {load_error}"}), 500

    equipe_raw = request.args.get('equipe')
    uc_raw = request.args.get('uc')

    try:
        equipe = validar_equipe(equipe_raw)

        uc_query_str = (uc_raw or "").strip()
        if not uc_query_str:
            return jsonify({"erro": "Parâmetro UC obrigatório"}), 400

        resultado = df[df['UC'] == uc_query_str]

        if not resultado.empty:
            data = resultado.iloc[0].where(pd.notnull(resultado.iloc[0]), None).to_dict()
            return jsonify(data)

        uc_int = validar_uc_para_int8(uc_raw)
        registrar_uc_nao_encontrada(uc_int, equipe)

        return jsonify({"erro": "UC não encontrada."}), 404

    except ValueError as ve:
        return jsonify({"erro": str(ve)}), 400
    except Exception as e:
        return jsonify({"erro": f"Erro durante a busca: {str(e)}"}), 500


if __name__ == '__main__':
    app.run(debug=True, port=5000)