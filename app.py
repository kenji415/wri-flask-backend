import gspread
from google.oauth2.service_account import Credentials
from flask import Flask, jsonify, request
from flask_cors import CORS
import os
import base64
from google.cloud import vision
import json

app = Flask(__name__)
CORS(app)  # Reactからのリクエストを許可

# 環境変数から認証情報を読み込む
if 'GOOGLE_CREDENTIALS' in os.environ:
    credentials_info = json.loads(os.environ['GOOGLE_CREDENTIALS'])
else:
    # ローカル環境ではcredentials.jsonから読み込む
    with open('credentials.json', 'r') as f:
        credentials_info = json.load(f)

# 環境変数からスプレッドシートIDを読み込む
SHEET_ID = '1CZSXkDPMPCgVawL74UQyXFHP_psmR7HmWYz25eacT6M'

# Google Sheets APIの設定
scopes = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive'
]

credentials = Credentials.from_service_account_info(credentials_info, scopes=scopes)
client = gspread.authorize(credentials)
sheet = client.open_by_key(SHEET_ID).sheet1

# Vision APIの設定
vision_client = vision.ImageAnnotatorClient(credentials=credentials)

def get_questions_from_sheet():
    rows = sheet.get_all_values()
    questions = []
    # 1行目はヘッダーなので2行目から
    for row in rows[1:]:
        # E列: 問題文, F列: 答え, B列: 大分類
        if len(row) >= 6 and row[4].strip() and row[5].strip():
            questions.append({
                "question": row[4].strip(),
                "answer": row[5].strip(),
                "category": row[1].strip()  # B列: 大分類
            })
    return questions

@app.route('/api/questions')
def get_questions():
    try:
        questions = get_questions_from_sheet()
        return jsonify(questions)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/vision_ocr', methods=['POST'])
def vision_ocr():
    data = request.json
    image_base64 = data.get('image')
    if not image_base64:
        return jsonify({'error': 'No image provided'}), 400

    # base64データからバイナリに変換
    image_bytes = base64.b64decode(image_base64.split(',')[-1])
    image = vision.Image(content=image_bytes)
    response = vision_client.text_detection(image=image)
    texts = response.text_annotations
    if texts:
        return jsonify({'text': texts[0].description.strip()})
    else:
        return jsonify({'text': ''})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001))
    app.run(host='0.0.0.0', port=port)
