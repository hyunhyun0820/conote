from flask import Flask, render_template, request, redirect, url_for, session
from flask_socketio import SocketIO, emit
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from dotenv import load_dotenv
import os
import uuid
import gevent.monkey

gevent.monkey.patch_all()

# 환경 변수
load_dotenv()
PASSWORD = os.getenv("SECRET_PASSWORD")
DATABASE_URL = os.getenv("DATABASE_URL")
SECRET_KEY = os.getenv("SECRET_KEY", "default_secret_key")

app = Flask(__name__)
app.secret_key = SECRET_KEY
app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# 확장 초기화
db = SQLAlchemy(app)
migrate = Migrate(app, db)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="gevent")

# 박스들
class Box(db.Model):
    __tablename__ = 'boxes'
    id = db.Column(db.String, primary_key=True)
    top = db.Column(db.Integer)
    left = db.Column(db.Integer)
    text = db.Column(db.Text)

# 비번
@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        password = request.form['password']
        if password == PASSWORD:
            session['logged_in'] = True
            return redirect(url_for('home'))
        else:
            return render_template('login.html', error="비밀번호가 틀렸습니다.")
    return render_template('login.html')

# 홈
@app.route('/home')
def home():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    return render_template('home.html')

# 소켓 - 클라이언트 연결 시 박스들 전송
@socketio.on('connect')
def send_initial_data(auth=None):
    if not session.get('logged_in'):
        return
    boxes = Box.query.order_by(Box.id.asc()).all()
    emit('load_boxes', [
        {"id": box.id, "top": box.top, "left": box.left, "text": box.text}
        for box in boxes
    ])

# 소켓 - 박스 생성
@socketio.on("create_box")
def create_box(data):
    if not session.get('logged_in'):
        return

    box_id = data.get("id", str(uuid.uuid4()))
    top = data.get("top", data.get("y", 100))
    left = data.get("left", data.get("x", 100))
    text = data.get("text", "")

    new_box = Box(id=box_id, top=top, left=left, text=text)
    db.session.add(new_box)
    db.session.commit()

    emit("new_box", {
        "id": box_id,
        "top": top,
        "left": left,
        "text": text
    }, broadcast=True)

# 소켓 - 박스 삭제
@socketio.on('delete_box')
def delete_box(data):
    if not session.get('logged_in'):
        return
    box = Box.query.get(data["id"])
    if box:
        db.session.delete(box)
        db.session.commit()
        emit('remove_box', {"id": data["id"]}, broadcast=True)

# 소켓 - 박스 텍스트 수정
@socketio.on('update_box')
def update_box(data):
    if not session.get('logged_in'):
        return
    box = Box.query.get(data["id"])
    if box:
        box.text = data["text"]
        db.session.commit()
        emit('update_box', data, broadcast=True)

# 소켓 - 박스 위치 수정
@socketio.on('move_box')
def move_box(data):
    if not session.get('logged_in'):
        return
    box = Box.query.get(data["id"])
    if box:
        box.top = data["top"]
        box.left = data["left"]
        db.session.commit()
        emit('move_box', data, broadcast=True)

#실행
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    socketio.run(app, host='0.0.0.0', port=port, debug=True)