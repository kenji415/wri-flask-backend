import os
import json
import base64
from flask import Flask, request, jsonify
from flask_cors import CORS
import gspread
from google.oauth2.service_account import Credentials
from google.cloud import vision

app = Flask(__name__)
CORS(app)

SPREADSHEET_ID = '1CZSXkDPMPCgVawL74UQyXFHP_psmR7HmWYz25eacT6M'
SHEET_NAME = 'data'

# 認証情報の取得
if 'GOOGLE_CREDENTIALS' in os.environ:
    credentials_info = json.loads(os.environ['GOOGLE_CREDENTIALS'])
    creds = Credentials.from_service_account_info(
        credentials_info,
        scopes=[
            'https://www.googleapis.com/auth/spreadsheets.readonly',
            'https://www.googleapis.com/auth/drive.readonly'
        ]
    )
else:
    creds = Credentials.from_service_account_file(
        'config/credentials.json',
        scopes=[
            'https://www.googleapis.com/auth/spreadsheets.readonly',
            'https://www.googleapis.com/auth/drive.readonly'
        ]
    )

gc = gspread.authorize(creds)

def get_questions_from_sheet():
    sh = gc.open_by_key(SPREADSHEET_ID)
    worksheet = sh.worksheet(SHEET_NAME)
    rows = worksheet.get_all_values()
    questions = []
    for row in rows[1:]:
        if len(row) >= 6 and row[4].strip() and row[5].strip():
            questions.append({
                "question": row[4].strip(),
                "answer": row[5].strip(),
                "category": row[1].strip()
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
    app.run(host='0.0.0.0', port=5001, debug=True)
