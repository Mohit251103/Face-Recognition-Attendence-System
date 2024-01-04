import base64
from flask import Flask, render_template, request, redirect, Response, session
from flask_pymongo import PyMongo
import face_recognition
import cv2
import numpy as np
import datetime
import csv
import pandas as pd
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import Mapped, mapped_column

app = Flask(__name__)
app.config["MONGO_URI"] = "mongodb://localhost:27017/myDatabase"
# app.config["MONGO_URI"] = "mongodb://localhost:27017/SubjectsForSection"
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///project.db"
app.config["SECRET_KEY"] = "mysecret"
db = PyMongo(app).db
# db_sub = PyMongo(app).db
db_sql = SQLAlchemy(app)

f = None
camera = None

class Subject(db_sql.Model):
    id: Mapped[int] = mapped_column(db_sql
                                    .Integer, primary_key=True)
    section: Mapped[str] = mapped_column(db_sql
                                         .String, unique=True, nullable=False)
    subjects: Mapped[str] = mapped_column(db_sql
                                          .String(255))

with app.app_context():
    db_sql.create_all()

def gen_frames(known_face_encodings, expected_students, temp_students,lnwriter,collection):
    while True:
        success, frame = camera.read()  # read the camera frame
        if not success:
            print("not readed successfully")
            break
        else:
            small_frame = cv2.resize(frame,(0,0),fx=0.25,fy=0.25)
            rgb_small_frame = cv2.cvtColor(small_frame,cv2.COLOR_BGR2RGB)
            face_locations = face_recognition.face_locations(rgb_small_frame)
            face_encodings = face_recognition.face_encodings(rgb_small_frame, face_locations)
            name = ""
            for face_encoding in face_encodings:
                matches = face_recognition.compare_faces(known_face_encodings,face_encoding)
                face_distance = face_recognition.face_distance(known_face_encodings,face_encoding)
                best_match_index = np.argmin(face_distance)

                if(matches[best_match_index]):
                    name = expected_students[best_match_index]

            present_students = []
            if name in expected_students:
                font = cv2.FONT_HERSHEY_SIMPLEX
                bottomLeftCornerOfText = (10,100)
                fontScale = 1.5
                fontColor = (255,0,0)
                thickness = 3
                lineType = 2
                cv2.putText(frame, name,bottomLeftCornerOfText,font,fontScale,fontColor,thickness,lineType)


                if name in temp_students:
                    temp_students.remove(name)
                    present_students.append(name)

            # present_students.sort()
            # print(present_students)
            for roll in present_students:
                current_date = datetime.datetime.now().strftime("%Y-%m-%d")
                student = db[collection].find_one({'uroll': roll})
                # attendence = student['attendence']
                # total_attendence = student["totalAttendence"]
                # temp_attendence = int(attendence[subject])
                # temp_total_attendence = int(total_attendence[subject])
                # attendence[subject] = temp_attendence+1
                # total_attendence[subject] = temp_total_attendence+1
                # db[collection].update_one({'uroll': roll},{ "$set": {'attendence': attendence, "totalAttendence":total_attendence}})
                lnwriter.writerow([roll, student['name'], 'Present', current_date])

        ret, buffer = cv2.imencode('.jpg', frame)
        if not ret:
            print("Not encoded successfully")
        frame = buffer.tobytes()
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

@app.route("/")
def hello_world():
    collections = db.list_collection_names()
    return render_template("index.html",collections = collections)

@app.route("/addsection",methods=['GET','POST'])
def addSection():
    if request.method == 'POST':
        section = request.form['sectionName']
        subjects = request.form['subjectsTaught']
        section_subject = Subject(section=section, subjects=subjects)
        print(section_subject)
        db_sql.session.add(section_subject)
        db_sql.session.commit()
        subjects = subjects.split(",")
        sub = []
        for i in subjects:
            sub.append(i.upper())

        # db_sub.create_collection(section)
        # db_sub[section].insert_one({"subjects":sub})
        db.create_collection(section)
        session[f'subjectsOf{section}'] = sub
        return redirect('/')

    return render_template("addSection.html")

@app.route("/student/<string:collection>",methods=['GET','POST'])
def fetchStudentData(collection):
    data = db[collection].find({})
    students = []
    subjects = Subject.query.filter_by(section = collection).first().subjects
    subjects = subjects.split(",")
    sub = []
    for i in subjects:
        sub.append(i.upper())
    # if sub == []:
    #     attendence = data[0]['attendence']
    #     for i in attendence:
    #         sub.append(i)

    # print(sub)
    for student in data:
        with open(f"static/img/{student['uroll']}.png","wb") as f:
            f.write(base64.b64decode(student['image']))

        temp = student
        temp['image'] = f"{student['uroll']}.png"
        students.append(temp)
    return render_template("student.html",students = students,collection = collection, subjects = sub)

@app.route("/student/<string:collection>/delete")
def deleteCollection(collection):
    db[collection].drop()
    collections = db.list_collection_names()
    return render_template("index.html", collections=collections)

@app.route("/student/<string:collection>/<string:uroll>/personalData")
def personalData(collection,uroll):
    student = db[collection].find_one({'uroll':uroll})
    subjects = Subject.query.filter_by(section=collection).first().subjects
    subjects = subjects.split(",")
    sub = []
    for i in subjects:
        sub.append(i.upper())

    percentage = {}
    for i in sub:
        if int(student['totalAttendence'][i]) == 0:
            sub_perc = 0
        else:
            sub_perc = int(student['attendence'][i]) / int(student['totalAttendence'][i]) * 100
        percentage[i] = sub_perc
    temp = student
    temp['image'] = f"{student['uroll']}.png"
    return render_template("studentPersonal.html",student = temp,collection = collection, subjects = sub, percentage=percentage)

@app.route("/student/<string:collection>/addstudent",methods=['GET','POST'])
def addStudentData(collection):
    data = db[collection].find({})
    subjects = Subject.query.filter_by(section=collection).first().subjects
    subjects = subjects.split(",")
    sub = []
    for i in subjects:
        sub.append(i.upper())
    if request.method == 'POST':
        uroll = request.form['uroll']
        name = request.form['name']
        photo = request.form['photo']
        with open(f"static/{photo}","rb") as f:
            data = f.read()
            encoded_photo = base64.b64encode(data)
        # encoded_photo = base64.b64encode(photo)

        # print(uroll,name)
        attendence = {}
        total_attendence = {}
        for i in sub:
            # subAttendence = request.form[i]
            attendence[i] = 0
            total_attendence[i] = 0
        # print(attendence)
        db[collection].insert_one({"uroll": uroll, "name": name, "attendence": attendence,"totalAttendence":total_attendence, "image":encoded_photo})
        return redirect('/')
    return render_template("add.html",collection = collection,subjects = sub)

@app.route("/student/<string:collection>/attendence",methods=['GET','POST'])
def selectSubject(collection):
    data = db[collection].find({})
    subjects = Subject.query.filter_by(section=collection).first().subjects
    subjects = subjects.split(",")
    sub = []
    for i in subjects:
        sub.append(i.upper())
    if request.method == 'POST':
        subject = request.form['subject']
        return render_template("attendence.html", collection=collection, students=db[collection].find({}),
                               subject=subject)

    return render_template("attendenceSubject.html",collection=collection, subjects = sub)


# @app.route("/student/<string:collection>/<string:subject>/takeAttendence",methods=['GET','POST'])
# def recordAttendence(collection,subject):
#
#     while True:
#         status, frame = camera.read()
#         cv2.imshow('Video',frame)
#         key = cv2.waitKey(1)
#         if key == ord('q'):
#             break
#     camera.release()
#     cv2.destroyAllWindows()
#     return render_template("attendenceSubject.html",collection=collection,students=db[collection].find({}),subject=subject)

@app.route("/video_feed")
def videoFeed():
    global camera
    camera = cv2.VideoCapture(0)
    global f
    collection = request.args.get('collection')
    subject = request.args.get('subject')
    students = db[collection].find({})
    known_faces = []
    expected_students = []
    for student in students:
        image_url = f"static/img/{student['uroll']}.png"
        # image = cv2.imread(image_url)
        # rgb_image = cv2.cvtColor(image,cv2.COLOR_BGR2RGB)
        # known_faces.append(rgb_image)
        image = face_recognition.load_image_file(image_url)
        known_faces.append(image)
        expected_students.append(student['uroll'])

    known_face_encodings = []
    for face in known_faces:
        face_encoding = face_recognition.face_encodings(face)[0]
        known_face_encodings.append(face_encoding)

    dt = datetime.datetime.now()
    current_date = dt.strftime("%Y-%m-%d")

    f = open(f"{collection}-{subject}-{current_date}.csv", 'w+', newline="")
    lnwriter = csv.writer(f)
    lnwriter.writerow(["University Roll No","Name","Status","Date"])

    temp_students = expected_students.copy()

    return Response(gen_frames(known_face_encodings,expected_students,temp_students,lnwriter,collection), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route("/closeVideo/<string:collection>/<string:subject>")
def closeVideo(collection,subject):
    global f
    if f:
        f.close()

    current_date = datetime.datetime.now().strftime("%Y-%m-%d")
    data = pd.read_csv(f'{collection}-{subject}-{current_date}.csv')
    # print(data)
    data.sort_values("University Roll No")

    present_students = []
    with open(f'{collection}-{subject}-{current_date}.csv', mode='r') as file:
        csvFile = csv.DictReader(file)
        for line in csvFile:
            present_students.append(line['University Roll No'])

    data = db[collection].find({})
    expected_students = []
    for i in data:
        expected_students.append(i['uroll'])

    for roll in expected_students:
        if(roll in present_students):
            student = db[collection].find_one({'uroll': roll})
            attendence = student['attendence']
            total_attendence = student["totalAttendence"]
            temp_attendence = int(attendence[subject])
            temp_total_attendence = int(total_attendence[subject])
            attendence[subject] = temp_attendence + 1
            total_attendence[subject] = temp_total_attendence + 1
            db[collection].update_one({'uroll': roll},
                                      {"$set": {'attendence': attendence, "totalAttendence": total_attendence}})
        else:
            student = db[collection].find_one({'uroll': roll})
            total_attendence = student["totalAttendence"]
            temp_total_attendence = int(total_attendence[subject])
            total_attendence[subject] = temp_total_attendence + 1
            db[collection].update_one({'uroll': roll},
                                      {"$set": {"totalAttendence": total_attendence}})


    camera.release()
    cv2.destroyAllWindows()
    return redirect(f"/student/{collection}")

@app.route("/contact")
def contact():
    return render_template("contact.html")

app.run(debug=True)