from flask import Flask, request, jsonify, render_template
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from docx import Document
from flask_cors import CORS
import google.generativeai as genai
import io
from google.oauth2 import service_account

app = Flask(__name__)
CORS(app)

# Cấu hình Gemini API
GOOGLE_API_KEY = "AIzaSyBrmODQUAJePrr4AmSRjsmYk2fhRjfaYW4"  # **Quan trọng:** Thay thế bằng API key Gemini của bạn
genai.configure(api_key=GOOGLE_API_KEY)
MODEL_NAME = "gemini-2.0-flash"
generation_config = {
    "max_output_tokens": 1000,
    "temperature": 0.9,
    "top_p": 1.0
}
safety_settings = [
    {
        "category": "HARM_CATEGORY_HARASSMENT",
        "threshold": "BLOCK_MEDIUM_AND_ABOVE"
    },
    {
        "category": "HARM_CATEGORY_HATE_SPEECH",
        "threshold": "BLOCK_MEDIUM_AND_ABOVE"
    },
    {
        "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
        "threshold": "BLOCK_MEDIUM_AND_ABOVE"
    },
    {
        "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
        "threshold": "BLOCK_MEDIUM_AND_ABOVE"
    },
]

# Cấu hình Google Drive API
DRIVE_SERVICE = None
SCOPES = ['https://www.googleapis.com/auth/drive.readonly']
SERVICE_ACCOUNT_FILE = 'tandanbhd-03c609a8a6a4.json'  # **Quan trọng:** Thay thế bằng đường dẫn đến file JSON của bạn
DRIVE_FOLDER_ID = '181QVNc4pby0TuRUzBbFoIm9u0DZ22GCM'  # **Quan trọng:** Thay thế bằng ID của thư mục chứa các file Word


def setup_drive_service():
    global DRIVE_SERVICE
    try:
        creds = service_account.Credentials.from_service_account_file(
            SERVICE_ACCOUNT_FILE, scopes=SCOPES)
        DRIVE_SERVICE = build('drive', 'v3', credentials=creds)
    except Exception as e:
        print(f"Lỗi khi thiết lập kết nối đến Google Drive: {e}")


def get_all_word_files(folder_id):
    """Lấy danh sách tất cả các file Word trong thư mục Drive."""
    global DRIVE_SERVICE
    if not DRIVE_SERVICE:
        setup_drive_service()

    try:
        results = DRIVE_SERVICE.files().list(
            q=f"'{folder_id}' in parents and mimeType='application/vnd.openxmlformats-officedocument.wordprocessingml.document'",
            fields="files(id, name)"
        ).execute()
        files = results.get('files', [])
        return {f['name']: f['id'] for f in files}  # Trả về dictionary {tên file: id file}
    except HttpError as error:
        print(f'Lỗi khi lấy danh sách file từ Drive: {error}')
        return {}


def load_word_file_contents(file_ids):
    """Tải nội dung của các file Word từ Drive và lưu vào dictionary."""
    global DRIVE_SERVICE
    if not DRIVE_SERVICE:
        setup_drive_service()

    file_contents = {}
    for file_name, file_id in file_ids.items():
        try:
            request = DRIVE_SERVICE.files().get_media(fileId=file_id)
            file_content = request.execute()
            with io.BytesIO(file_content) as f:
                document = Document(f)
                full_text = []
                for para in document.paragraphs:
                    full_text.append(para.text)
                file_contents[file_name] = '\n'.join(full_text)
        except HttpError as error:
            print(f'Lỗi khi tải nội dung file {file_name}: {error}')
        except Exception as e:
            print(f'Lỗi không xác định khi tải nội dung file {file_name}: {e}')
    return file_contents


# Khởi tạo dữ liệu khi ứng dụng chạy
WORD_FILES = {}
WORD_CONTENTS = {}  # Thay đổi: Lưu trữ nội dung của TẤT CẢ các file
if __name__ == '__main__':
    setup_drive_service()
    WORD_FILES = get_all_word_files(DRIVE_FOLDER_ID)
    WORD_CONTENTS = load_word_file_contents(WORD_FILES)



@app.route('/')
def index():
    print("Route / được gọi")
    return render_template('index.html')

@app.route('/ask', methods=['POST'])
def ask():
    data = request.get_json()
    question = data.get('question')

    if not question:
        return jsonify({'error': 'Missing question'}), 400

    # Tổng hợp nội dung từ tất cả các file
    all_context = "\n\n".join(WORD_CONTENTS.values())  # Nối nội dung các file

    try:
        model = genai.GenerativeModel(model_name=MODEL_NAME,
                                    generation_config=generation_config,
                                    safety_settings=safety_settings)
        prompt = f"Dựa vào các văn bản sau đây, trả lời câu hỏi: {question}\n\n{all_context}"  # Sử dụng all_context
        response = model.generate_content(prompt)
        answer = response.text
        return jsonify({'answer': answer})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

import os

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
