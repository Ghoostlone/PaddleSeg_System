import os.path

import cv2
import pymysql
from flask import Flask, request, session, redirect
from flask import render_template
from flask_bootstrap import Bootstrap
from werkzeug.utils import secure_filename
import shutil
from gevent import pywsgi
import vtk
from trimesh.exchange.obj import export_obj

#几个nii转ply的方法
def read_nii(filename):
    """
    读取nii文件，输入文件路径
    """
    reader = vtk.vtkNIFTIImageReader()
    reader.SetFileName(filename)
    reader.Update()
    return reader


def get_mc_contour(file, setvalue):
    """
    计算轮廓的方法
    file:读取的vtk类
    setvalue:要得到的轮廓的值
    """
    contour = vtk.vtkDiscreteMarchingCubes()
    # ChatGPT say:
    # vtkDiscreteMarchingCubes和vtkMarchingCubes是两个在VTK（Visualization Toolkit）库中用于构建3D模型的算法。它们的主要区别在于如何处理输入数据。
    # vtkMarchingCubes是一种连续的算法，用于从体数据（例如体素数据或标量场数据）中提取等值面。
    # 它基于Marching Cubes算法，将体数据划分为小立方体单元，并根据单元内部的数值情况确定等值面的形状和拓扑关系。
    # vtkMarchingCubes可以处理连续的数据集，并产生光滑的等值面。
    # 与之相反，vtkDiscreteMarchingCubes是一种离散的算法，用于从离散的体数据中提取等值面。
    # 它适用于离散的数据集，其中体素只能具有预定义的几种状态，例如0和1。离散数据集通常用于表示二值图像或分割结果等。
    # vtkDiscreteMarchingCubes使用类似的原理，但对于离散数据集，它仅考虑预定义状态之间的界面，并生成离散的等值面。
    # 总结一下，vtkMarchingCubes适用于处理连续的体数据，可以产生光滑的等值面，
    # 而vtkDiscreteMarchingCubes适用于处理离散的体数据，只考虑预定义状态之间的界面，生成离散的等值面。
    # 选择使用哪个算法取决于您的数据类型和应用需求。
    contour.SetInputConnection(file.GetOutputPort())

    contour.ComputeNormalsOn()
    contour.SetValue(0, setvalue)
    return contour


def smoothing(smoothing_iterations, pass_band, feature_angle, contour):
    '''
    使轮廓变平滑
    smoothing_iterations:迭代次数
    pass_band:值越小单次平滑效果越明显
    feature_angle:暂时不知道作用
    '''
    # vtk有两种平滑函数，效果类似
    vtk.vtkSmoothPolyDataFilter()
    smoother = vtk.vtkSmoothPolyDataFilter()
    smoother.SetInputConnection(contour.GetOutputPort())
    smoother.SetNumberOfIterations(50)
    smoother.SetRelaxationFactor(0.6)  # 越大效果越明显

    vtk.vtkWindowedSincPolyDataFilter()
    smoother = vtk.vtkWindowedSincPolyDataFilter()
    smoother.SetInputConnection(contour.GetOutputPort())
    smoother.SetNumberOfIterations(smoothing_iterations)
    smoother.BoundarySmoothingOff()
    smoother.FeatureEdgeSmoothingOff()
    smoother.SetFeatureAngle(feature_angle)
    smoother.SetPassBand(pass_band)
    smoother.NonManifoldSmoothingOn()
    smoother.NormalizeCoordinatesOn()
    smoother.Update()
    return smoother


def singledisplay(obj):
    mapper = vtk.vtkPolyDataMapper()
    mapper.SetInputConnection(obj.GetOutputPort())
    mapper.ScalarVisibilityOff()

    actor = vtk.vtkActor()
    actor.SetMapper(mapper)

    renderer = vtk.vtkRenderer()
    renderer.SetBackground([0.1, 0.1, 0.5])
    renderer.AddActor(actor)
    window = vtk.vtkRenderWindow()
    window.SetSize(512, 512)
    window.AddRenderer(renderer)

    interactor = vtk.vtkRenderWindowInteractor()
    interactor.SetRenderWindow(window)

    # 开始显示
    window.Render()
    interactor.Initialize()
    interactor.Start()
    export_obj(window)
    return window


def multidisplay(obj):
    # This sets the block at flat index 3 red
    # Note that the index is the flat index in the tree, so the whole multiblock
    # is index 0 and the blocks are flat indexes 1, 2 and 3.  This affects
    # the block returned by mbds.GetBlock(2).
    colors = vtk.vtkNamedColors()
    mapper = vtk.vtkCompositePolyDataMapper2()
    mapper.SetInputDataObject(obj)
    cdsa = vtk.vtkCompositeDataDisplayAttributes()
    mapper.SetCompositeDataDisplayAttributes(cdsa)
    # 上色
    mapper.SetBlockColor(1, colors.GetColor3d('Red'))
    mapper.SetBlockColor(2, colors.GetColor3d('Lavender'))
    mapper.SetBlockColor(3, colors.GetColor3d('Gray'))
    mapper.SetBlockColor(4, colors.GetColor3d('Green'))
    mapper.SetBlockColor(5, colors.GetColor3d('Yellow'))
    mapper.SetBlockColor(6, colors.GetColor3d('Pink'))
    mapper.SetBlockColor(7, colors.GetColor3d('Brown'))
    mapper.SetBlockColor(8, colors.GetColor3d('Turquoise'))
    mapper.SetBlockColor(9, colors.GetColor3d('Orange'))
    mapper.SetBlockColor(10, colors.GetColor3d('Blue'))
    mapper.SetBlockColor(11, colors.GetColor3d('Purple'))
    actor = vtk.vtkActor()
    actor.SetMapper(mapper)

    # Create the Renderer, RenderWindow, and RenderWindowInteractor.
    renderer = vtk.vtkRenderer()
    renderWindow = vtk.vtkRenderWindow()
    renderWindow.AddRenderer(renderer)
    renderWindowInteractor = vtk.vtkRenderWindowInteractor()
    renderWindowInteractor.SetRenderWindow(renderWindow)

    # Enable user interface interactor.
    renderer.AddActor(actor)
    renderer.SetBackground(colors.GetColor3d('SteelBlue'))
    renderWindow.SetWindowName('CompositePolyDataMapper')
    renderWindow.Render()
    renderWindowInteractor.Start()


def write_ply(obj, save_dir, color):
    """
    输入必须是单个模型，vtkMultiBlockDataSet没有GetOutputPort()类
    """

    plyWriter = vtk.vtkPLYWriter()
    plyWriter.SetFileName(save_dir)
    plyWriter.SetColorModeToUniformCellColor()
    plyWriter.SetColor(color[0], color[1], color[2])
    plyWriter.SetInputConnection(obj.GetOutputPort())
    plyWriter.Write()

# 初始化Flask后端
app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(5)
bootstrap = Bootstrap(app)

# 连接到数据库
cnn = pymysql.connect(host="frp-act.top", port=55926, user="root", password="oypjyozj", database="test", charset="utf8")
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
        cursor.execute("SELECT pwd , identity FROM `user` WHERE id='" + inputId + "'")
        result = cursor.fetchall()
        print(result)
        if result:
            for row in result:
                if row[0] == inputPassword:
                    session['userid'] = inputId
                    session['identity'] = row[1]
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
        if session.get('identity') == "doctor":
            return render_template("index/for_doctor.html", id=session.get('userid'))
        elif session.get('identity') == "patient":
            return render_template("index/for_patient.html", id=session.get('userid'))


# 上传CT
@app.route('/upload/upload', methods=['POST', 'GET'])
def upload():
    if request.method == 'GET':
        return render_template("upload/upload_image.html", id=session.get('userid'))
    if request.method == 'POST':
        f = request.files['image']
        diagnosis_ID = request.form.get("diagnosis")
        patient_ID = request.form.get("id")
        base_path = os.path.dirname(__file__)
        print(base_path)
        # 检测用户名匹配
        cursor.execute("SELECT * FROM `user` WHERE id='" + patient_ID + "'")
        result = cursor.fetchall()
        print(result)
        if result:
            for row in result:
                if row[3] == "patient":
                    img_path = secure_filename(f.filename).split('.',1)[0]+"_0000.nii.gz"
                    print(img_path)
                    dir_path = os.path.join(base_path, 'static/img/nii_path', patient_ID)
                    print(dir_path)
                    upload_path = os.path.join(base_path, 'static/img/nii_path', patient_ID, img_path)
                    print(upload_path)
                    # upload_path = upload_path.replaceAll("\\", "\\\\")

                    if os.path.exists(dir_path):
                        f.save(upload_path)
                    # print(upload_path)
                    else:
                        os.mkdir(dir_path)
                        f.save(upload_path)
                    print(diagnosis_ID, session.get('userid'), patient_ID, upload_path)
                    print(upload_path)
                    upload_path = upload_path.replace("\\", "/")
                    sql = "INSERT INTO diagnosis VALUES (" + diagnosis_ID + "," + session.get(
                        'userid') + "," + patient_ID + ",'" + upload_path + "')        "
                    cursor.execute(sql)
                    cursor.connection.commit()
                    print(123132132132132132121213123213213)
                    return "已上传成功"
                else:
                    return "此ID非病人，请重新输入"
        else:
            return "查无此人，请重新输入病人ID"



# 看CT
@app.route('/CT_view/ct_view', methods=['GET', 'POST'])
def CT_view():
    if request.method == 'GET':
        return render_template("CT_view/ct_view.html", id=session.get('userid'))
    if request.method == 'POST':
        P_ID = request.form.get("P_ID")
        ply_path = "../static/img/ply_path/" + P_ID + "/"
        print(ply_path)
        return render_template("CT_view/3D_render.html", id=session.get('userid'), ply_path=ply_path)


@app.route('/start_Predict',methods=['GET','POST'])
def start_Predict():
    if request.method=='GET':
        return render_template("Predict/start_Predict.html",id=session.get('userid'))
    if request.method=='POST':
        P_ID=request.form.get("id")
        print(P_ID)
        session['patient_id_selected']=P_ID
        cursor.execute("SELECT * FROM `diagnosis` WHERE patient_id='" + P_ID + "'")
        result = cursor.fetchall()
        print(result)
        all_row=""
        if result:
            for row in result:
                all_row=all_row+row[3]+"<br />"
            return all_row
        else:
            return 124141412412412412412412412412
        # command_Line = "python nnunet/infer.py --image_folder /root/autodl-tmp/Flask/static/img/nii_path/"
        # os.system(command_Line)
@app.route('/run_predict',methods=['POST'])
def run_Pred():
    if request.method=='POST':
        File_path=request.form.get("file_path")
        #todo 保存文件路径split
        session['File']=File_path.split('/',)
        final_path=File_path.split('.',1)[0]+".nii.gz"
        final_path=final_path.replace('nii_path','seg_path')
        final_path=final_path.replace('_0000.nii.gz','.nii.gz')
        session['final_path'] = final_path
        print(session.get('final_path'))
        return render_template("Predict/running.html")

@app.route('/PaddleSeg',methods=['GET'])
def PaddleSeg():
    if request.method=='GET':
        P_ID_SELECTED=session.get('patient_id_selected')
        file_path="/root/autodl-tmp/Flask/static/img/nii_path/"+P_ID_SELECTED+"/"
        output_path = "/root/autodl-tmp/Flask/static/img/seg_path/" + P_ID_SELECTED + "/"
        if os.path.exists(output_path):
            print("有了")
        else:
            os.mkdir(output_path)
            print("没有，创了")
        SegCommand="/root/miniconda3/envs/PaddleSeg/bin/python "\
                    "/root/autodl-tmp/Flask/PaddleSeg/contrib/MedicalSeg/nnunet/infer.py --image_folder "+file_path+" --output_folder "+output_path+" " \
                    "--plan_path /root/autodl-tmp/Flask/predict/nnUNetPlansv2.1_plans_3D.pkl " \
                    "--model_paths /root/autodl-tmp/Flask/predict/baseline_model/model.pdmodel " \
                    "--param_paths /root/autodl-tmp/Flask/predict/baseline_model/model.pdiparams " \
                    "--postprocessing_json_path /root/autodl-tmp/Flask/predict/baseline_model/postprocessing.json " \
                    "--model_type cascade_lowres " \
                    "--disable_postprocessing " \
                    "--save_npz"
        os.system("cd /root/autodl-tmp/Flask/PaddleSeg/contrib/MedicalSeg")
        os.chdir("/root/autodl-tmp/Flask/PaddleSeg/contrib/MedicalSeg")
        print(os.getcwd())
        os.system(SegCommand)
        os.chdir("/root/autodl-tmp/Flask")
        #分割完毕，开始转nii为ply保存
        print("这是final_path",session.get("final_path"))
        #todo 保存位置记得改
        nii_dir = session.get('final_path')
        ply_path = "./static/img/ply_path/" + P_ID_SELECTED + "/"
        if os.path.exists(ply_path):
            print("有了")
        else:
            os.mkdir(ply_path)
            print("没有，创了")
        save_dir = ply_path
        smoothing_iterations = 100
        pass_band = 0.005
        feature_angle = 120
        reader = read_nii(nii_dir)

        color = [(0, 0, 0), (128, 0, 0), (0, 128, 0), (128, 128, 0), (0, 0, 128), (128, 0, 128), (0, 128, 128),
                 (128, 128, 128), (64, 0, 0), (192, 0, 0), (64, 128,
                                                            0), (192, 128, 0), (64, 0, 128), (192, 0, 128),
                 (64, 128, 128), (192, 128, 128), (0, 64, 0), (128, 64, 0), (0, 192, 0), (128, 192, 0), (0, 64, 128),
                 (128, 64, 12)]

        mbds = vtk.vtkMultiBlockDataSet()
        mbds.SetNumberOfBlocks(11)
        items = ['background', '1', '2',
                 '3', '4', '5', '6', '7', '8', '9', '10', '11', '12']
        for iter in range(1, 12):
            print(iter)
            contour = get_mc_contour(reader, iter)
            smoothing_iterations = 100
            pass_band = 0.005
            feature_angle = 120
            smoother = smoothing(smoothing_iterations, pass_band,
                                 feature_angle, contour)
            write_ply(smoother, save_dir + f'{items[iter]}.ply', color[iter])

            mbds.SetBlock(iter, smoother.GetOutput())
            #
        # singledisplay(smoother)
        # write_ply(mbds, save_dir + f'final.ply', color[3])
        # multidisplay(mbds)#多重展示
        return render_template("index/for_doctor.html", id=session.get('userid'))

@app.route('/P_CT', methods=['POST', 'GET'])
def p_ct():
    if request.method == 'GET':
        return render_template("CT_view/ct_view_P.html", id=session.get('userid'))
    if request.method == 'POST':
        P_ID = session.get('userid')
        base_path = os.path.dirname(__file__)
        print(base_path)
        ply_path = "static/img/ply_path/" + P_ID
        upload_path = os.path.join(base_path,ply_path)
        print(upload_path)
        return render_template("CT_view/3D_render.html", id=session.get('userid'), ply_path=upload_path)


@app.route('/search', methods=['POST'])
def search():
    if request.method == 'POST':
        cursor.execute("SELECT * FROM `user` WHERE identity='patient'")
        result = cursor.fetchall()
        return_things = ""
        if result:
            # print(result)
            for i in result:
                # print(i[0])
                return_things = return_things + "&nbsp&nbsp&nbsp" + i[0]
        return return_things

@app.route('/tomesh', methods=['GET'])
def tomesh():
    if request.method=='GET':
        print(12123123)
    if request.method == 'POST':
        cursor.execute("SELECT * FROM `user` WHERE identity='patient'")
        result = cursor.fetchall()
        return_things = ""
        if result:
            # print(result)
            for i in result:
                # print(i[0])
                return_things = return_things + "&nbsp&nbsp&nbsp" + i[0]
        return return_things


# 开始运行
if __name__ == '__main__':
    # app.run()
    server = pywsgi.WSGIServer(('0.0.0.0', 6006), app)
    server.serve_forever()
