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
                "hint": row[9].strip() if len(row) > 9 else "",
                "questionImageUrl": row[10].strip() if len(row) > 10 else "",
                # 選択肢データ（M列以降）
                "choice1": row[12].strip() if len(row) > 12 else "",
                "choice2": row[13].strip() if len(row) > 13 else "",
                "choice3": row[14].strip() if len(row) > 14 else "",
                "choice4": row[15].strip() if len(row) > 15 else "",
                "choice5": row[16].strip() if len(row) > 16 else "",
                "choice6": row[17].strip() if len(row) > 17 else "",
                "choice7": row[18].strip() if len(row) > 18 else ""
            })
    return questions

@app.route('/api/questions')
def get_questions():
    try:
        questions = get_questions_from_sheet()
        
        # デバッグ用: 選択肢問題の確認
        choice_questions = [q for q in questions if q.get('type') == '選択肢']
        print(f"選択肢問題の数: {len(choice_questions)}")
        if choice_questions:
            print(f"最初の選択肢問題: {choice_questions[0]}")
            print(f"選択肢1: '{choice_questions[0].get('choice1')}'")
            print(f"選択肢2: '{choice_questions[0].get('choice2')}'")
            print(f"選択肢3: '{choice_questions[0].get('choice3')}'")
            print(f"選択肢4: '{choice_questions[0].get('choice4')}'")
        
        return jsonify(questions)
    except Exception as e:
        print(f"API エラー: {e}")
        import traceback
        traceback.print_exc()
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

@app.route('/api/get_image/<file_id>')
def get_image(file_id):
    try:
        # Google Driveの画像を直接取得して返す（Discordボットと同じ方法）
        import requests
        from io import BytesIO
        
        # Google Driveの直接ダウンロードURL
        direct_url = f'https://drive.google.com/uc?export=download&id={file_id}'
        
        # 画像を取得
        response = requests.get(direct_url, timeout=10)
        if response.status_code == 200:
            # Content-Typeを確認して適切なMIMEタイプを設定
            ctype = response.headers.get("Content-Type", "")
            if 'gif' in ctype:
                mimetype = 'image/gif'
            elif 'png' in ctype:
                mimetype = 'image/png'
            elif 'jpeg' in ctype or 'jpg' in ctype:
                mimetype = 'image/jpeg'
            else:
                mimetype = 'image/jpeg'  # デフォルト
            
            # 画像データをそのまま返す
            from flask import Response
            return Response(response.content, mimetype=mimetype)
        else:
            print(f"Failed to fetch image: {response.status_code}")
            return jsonify({"error": "Failed to fetch image"}), 404
            
    except Exception as e:
        print(f"Image fetch error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/record_answer', methods=['POST'])
def record_answer():
    try:
        data = request.json
        user_id = data.get('userId')
        user_name = data.get('userName')
        question_id = data.get('questionId')
        is_correct = data.get('isCorrect')
        
        print(f"Record answer request: userId={user_id}, userName={user_name}, questionId={question_id}, isCorrect={is_correct}")
        
        # スプレッドシートの「user集計」タブを取得
        sh = gc.open_by_key(SPREADSHEET_ID)
        
        # ワークシートの存在確認
        try:
            worksheet = sh.worksheet('user集計')
            print("user集計タブにアクセス成功")
        except Exception as e:
            print(f"user集計タブへのアクセスエラー: {e}")
            # タブが存在しない場合は作成を試行
            try:
                worksheet = sh.add_worksheet(title='user集計', rows=1000, cols=10)
                # ヘッダー行を追加
                worksheet.append_row(['ユーザーID', 'ユーザー名', '問題ID', '回答回数', '正解回数'])
                print("user集計タブを作成しました")
            except Exception as create_error:
                print(f"user集計タブの作成エラー: {create_error}")
                return jsonify({"error": f"Failed to create user集計 tab: {create_error}"}), 500
        
        # 既存データを取得
        try:
            existing_data = worksheet.get_all_values()
            print(f"既存データ行数: {len(existing_data)}")
        except Exception as e:
            print(f"既存データ取得エラー: {e}")
            return jsonify({"error": f"Failed to get existing data: {e}"}), 500
        
        # 既存のユーザー・問題の組み合わせを探す
        found = False
        for i, row in enumerate(existing_data[1:], start=2):  # ヘッダーをスキップ
            if len(row) >= 3 and row[0] == user_id and row[2] == question_id:
                # 既存データを更新
                current_answers = int(row[3]) if len(row) > 3 and row[3] else 0
                current_correct = int(row[4]) if len(row) > 4 and row[4] else 0
                
                new_answers = current_answers + 1
                new_correct = current_correct + (1 if is_correct else 0)
                
                try:
                    worksheet.update(f'D{i}', [[new_answers]])
                    worksheet.update(f'E{i}', [[new_correct]])
                    print(f"既存データ更新: 行{i}, 回答回数={new_answers}, 正解回数={new_correct}")
                except Exception as e:
                    print(f"データ更新エラー: {e}")
                    return jsonify({"error": f"Failed to update data: {e}"}), 500
                
                found = True
                break
        
        if not found:
            # 新規データを追加
            new_row = [user_id, user_name, question_id, 1, 1 if is_correct else 0]
            try:
                worksheet.append_row(new_row)
                print(f"新規データ追加: {new_row}")
            except Exception as e:
                print(f"新規データ追加エラー: {e}")
                return jsonify({"error": f"Failed to append new data: {e}"}), 500
        
        return jsonify({"success": True})
        
    except Exception as e:
        print(f"record_answer API エラー: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001) 
