import os.path

import cv2
import pymysql
from flask import Flask, request, session, redirect
from flask import render_template
from flask_bootstrap import Bootstrap
from werkzeug.utils import secure_filename
import shutil
from gevent import pywsgi

# 初始化Flask后端
app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(5)
bootstrap = Bootstrap(app)

# 连接到数据库
cnn = pymysql.connect(host="127.0.0.1", port=3306, user="root", password="oypjyozj", database="test", charset="utf8")
cursor = cnn.cursor()


# 登录页面
@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        return render_template("login/login.html")
    if request.method == 'POST':
        inputId = request.form.get('inputId')
        inputPassword = request.form.get('inputPassword')
        print(inputId, inputPassword)
        cursor.execute("SELECT pwd FROM `user` WHERE id='" + inputId + "'")
        result = cursor.fetchall()
        if result:
            for row in result:
                if row[0] == inputPassword:
                    session['userid'] = inputId
                    return redirect('/index/index')
            else:
                return render_template("login/wrongPWD.html")
        else:
            return render_template("/login/loginFail.html")


# 注册页面
@app.route('/signup', methods=['POST', 'GET'])
def signup():
    if request.method == 'GET':
        return render_template("signup/signup.html")
        # return redirect("https://www.baidu.com")
    if request.method == 'POST':
        inputId = request.form.get("inputId")
        inputEmail = request.form.get("inputEmail")
        inputPassword = request.form.get("inputPassword")
        identity_Flag = request.form.get("identity")
        Identity = ""
        Sir_key = request.form.get("sir_yes_sir")
        if identity_Flag == "0":
            Identity = "doctor"
        elif identity_Flag == "1":
            Identity = "patient"
        print("receive sign up request:" + inputId, inputEmail, inputPassword, Identity)
        cursor.execute("SELECT * FROM USER WHERE id = '%s'" % inputId)
        results = cursor.fetchall()
        if results:
            return render_template("signup/SignupFail.html")
        else:
            sql = "INSERT INTO  `user` VALUES('" + inputId + "','" + inputEmail + "','" \
                  + inputPassword + "','" + Identity + "')"
            if identity_Flag == "0":
                if Sir_key == "LGDLGD":
                    n = cursor.execute(sql)
                    cursor.connection.commit()
                    print(inputId + " signing up successfully")
                    return render_template("signup/SignupSuccess.html")
                else:
                    return render_template("signup/SignupFail.html")
            elif identity_Flag == "1":
                n = cursor.execute(sql)
                cursor.connection.commit()
                print(inputId + " signing up successfully")
                return render_template("signup/SignupSuccess.html")


# 主页
@app.route('/index/index', methods=['GET'])
def index():
    if request.method == 'GET':
        return render_template("index/index.html", id=session.get('userid'))


# 上传CT
@app.route('/upload/upload', methods=['POST', 'GET'])
def upload():
    if request.method == 'GET':
        return render_template("upload/upload_image.html", id=session.get('userid'))
    if request.method == 'POST':
        f = request.files['image']
        base_path = os.path.dirname(__file__)
        # print(base_path)
        img_path = secure_filename(f.filename)
        upload_path = os.path.join(base_path, 'static/img/nii_path', img_path)
        # print(upload_path)
        f.save(upload_path)

        return render_template("index/index.html", id=session.get('userid'))


# 开始运行
if __name__ == '__main__':
    # app.run()
    server = pywsgi.WSGIServer(('0.0.0.0', 5001), app)
    server.serve_forever()
