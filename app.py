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

# スプレッドシート用認証
spreadsheet_info = json.loads(os.environ['GOOGLE_CREDENTIALS'])
spreadsheet_creds = Credentials.from_service_account_info(
    spreadsheet_info,
    scopes=[
        'https://www.googleapis.com/auth/spreadsheets.readonly',
        'https://www.googleapis.com/auth/drive.readonly',
        'https://www.googleapis.com/auth/spreadsheets'
    ]
)
gc = gspread.authorize(spreadsheet_creds)

# Vision API用認証
vision_info = json.loads(os.environ['GOOGLE_VISION'])
vision_creds = Credentials.from_service_account_info(vision_info)
vision_client = vision.ImageAnnotatorClient(credentials=vision_creds)

def get_questions_from_sheet():
    sh = gc.open_by_key(SPREADSHEET_ID)
    worksheet = sh.worksheet(SHEET_NAME)
    rows = worksheet.get_all_values()
    questions = []
    for row in rows[1:]:
        if len(row) >= 6 and row[4].strip() and row[5].strip():
            questions.append({
                "id": row[0].strip() if len(row) > 0 else "",
                "question": row[4].strip(),
                "answer": row[5].strip(),
                "category": row[1].strip(),
                "subCategory": row[2].strip() if len(row) > 2 else "",
                "detailCategory": row[2].strip() if len(row) > 2 else "",
                "type": row[6].strip() if len(row) > 6 else "",
                "level": row[7].strip() if len(row) > 7 else "",
                "imageUrl": row[8].strip() if len(row) > 8 else "",
                "hint": row[9].strip() if len(row) > 9 else ""
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

@app.route('/api/record_answer', methods=['POST'])
def record_answer():
    try:
        data = request.json
        user_id = data.get('userId')
        user_name = data.get('userName')
        question_id = data.get('questionId')
        is_correct = data.get('isCorrect')
        
        # スプレッドシートの「user集計」タブを取得
        sh = gc.open_by_key(SPREADSHEET_ID)
        worksheet = sh.worksheet('user集計')
        
        # 既存データを取得
        existing_data = worksheet.get_all_values()
        
        # 既存のユーザー・問題の組み合わせを探す
        found = False
        for i, row in enumerate(existing_data[1:], start=2):  # ヘッダーをスキップ
            if len(row) >= 3 and row[0] == user_id and row[2] == question_id:
                # 既存データを更新
                current_answers = int(row[3]) if len(row) > 3 and row[3] else 0
                current_correct = int(row[4]) if len(row) > 4 and row[4] else 0
                
                new_answers = current_answers + 1
                new_correct = current_correct + (1 if is_correct else 0)
                
                worksheet.update(f'D{i}', new_answers)
                worksheet.update(f'E{i}', new_correct)
                found = True
                break
        
        if not found:
            # 新規データを追加
            new_row = [user_id, user_name, question_id, 1, 1 if is_correct else 0]
            worksheet.append_row(new_row)
        
        return jsonify({"success": True})
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001)
