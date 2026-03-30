from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import os

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///platform.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'your_secret_key_123'
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['PROFILE_PICS_FOLDER'] = 'profile_pics'
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024  # 500MB max
ALLOWED_EXTENSIONS = {'mp4', 'avi', 'mov', 'mkv'}
ALLOWED_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# --- MODELS ---

class Teacher(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    bio = db.Column(db.Text)
    subject = db.Column(db.String(100), default='General')
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    videos = db.relationship('Video', backref='teacher', lazy=True)

class Video(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    filename = db.Column(db.String(300), nullable=False)
    subject = db.Column(db.String(100), default='General')
    teacher_id = db.Column(db.Integer, db.ForeignKey('teacher.id'), nullable=False)

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), nullable=False, unique=True)
    password = db.Column(db.String(200), nullable=False)
    score = db.Column(db.Integer, default=0)
    is_teacher = db.Column(db.Boolean, default=False)
    profile_pic = db.Column(db.String(300), default='default.png')
    test_results = db.relationship('TestResult', backref='user', lazy=True)

class Test(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    question = db.Column(db.Text, nullable=False)
    option_a = db.Column(db.String(200))
    option_b = db.Column(db.String(200))
    option_c = db.Column(db.String(200))
    option_d = db.Column(db.String(200))
    correct = db.Column(db.String(1))
    explanation = db.Column(db.Text)
    video_id = db.Column(db.Integer, db.ForeignKey('video.id'), nullable=False)

class TestResult(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    video_id = db.Column(db.Integer, db.ForeignKey('video.id'), nullable=False)
    score = db.Column(db.Integer, default=0)

class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    video_id = db.Column(db.Integer, db.ForeignKey('video.id'), nullable=False)
    username = db.Column(db.String(100))

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def allowed_image(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_IMAGE_EXTENSIONS

# --- ROUTES ---

@app.route('/')
def home():
    videos = Video.query.all()
    return render_template('home.html', videos=videos)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = generate_password_hash(request.form['password'])
        is_teacher = 'is_teacher' in request.form
        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            flash('Username already exists!')
            return redirect(url_for('register'))
        new_user = User(username=username, password=password, is_teacher=is_teacher)
        db.session.add(new_user)
        db.session.commit()
        if is_teacher:
            teacher = Teacher(name=username, user_id=new_user.id)
            db.session.add(teacher)
            db.session.commit()
        flash('Account created! Please login.')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for('home'))
        flash('Wrong username or password!')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('home'))

@app.route('/upload', methods=['GET', 'POST'])
@login_required
def upload():
    if not current_user.is_teacher:
        flash('Only teachers can upload videos!')
        return redirect(url_for('home'))
    if request.method == 'POST':
        title = request.form['title']
        description = request.form['description']
        file = request.files['video']
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            teacher = Teacher.query.filter_by(user_id=current_user.id).first()
            subject = request.form['subject']
            new_video = Video(title=title, description=description, filename=filename, subject=subject, teacher_id=teacher.id)
            db.session.add(new_video)
            db.session.commit()
            flash('Video uploaded successfully!')
            return redirect(url_for('home'))
        flash('Invalid file type! Use mp4, avi, mov or mkv.')
    return render_template('upload.html')

@app.route('/search')
def search():
    q = request.args.get('q', '')
    videos = Video.query.filter(
        Video.title.contains(q) | Video.description.contains(q)
    ).all()
    return render_template('search.html', videos=videos, query=q)

@app.route('/video/<int:video_id>', methods=['GET', 'POST'])
def video(video_id):
    video = Video.query.get_or_404(video_id)
    comments = Comment.query.filter_by(video_id=video_id).all()
    if request.method == 'POST':
        if not current_user.is_authenticated:
            return redirect(url_for('login'))
        content = request.form['content']
        comment = Comment(content=content, user_id=current_user.id, video_id=video_id, username=current_user.username)
        db.session.add(comment)
        db.session.commit()
        return redirect(url_for('video', video_id=video_id))
    return render_template('video.html', video=video, comments=comments)

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/teacher/<int:teacher_id>')
def teacher_profile(teacher_id):
    teacher = Teacher.query.get_or_404(teacher_id)
    return render_template('teacher.html', teacher=teacher)

@app.route('/video/<int:video_id>/test', methods=['GET', 'POST'])
@login_required
def take_test(video_id):
    video = Video.query.get_or_404(video_id)
    tests = Test.query.filter_by(video_id=video_id).all()
    already_taken = TestResult.query.filter_by(user_id=current_user.id, video_id=video_id).first()
    results = None
    score = 0
    if request.method == 'POST':
        results = []
        for test in tests:
            answer = request.form.get(f'question_{test.id}')
            is_correct = answer == test.correct
            if is_correct:
                score += 10
            results.append({
                'question': test.question,
                'your_answer': answer,
                'correct': test.correct,
                'is_correct': is_correct,
                'explanation': test.explanation,
                'option_a': test.option_a,
                'option_b': test.option_b,
                'option_c': test.option_c,
                'option_d': test.option_d,
            })
        current_user.score += score
        if not already_taken:
            result = TestResult(user_id=current_user.id, video_id=video_id, score=score)
            db.session.add(result)
        db.session.commit()
        already_taken = True
    return render_template('test.html', video=video, tests=tests, results=results, score=score, total=len(tests)*10, total_score=current_user.score, already_taken=already_taken)

@app.route('/add_question/<int:video_id>', methods=['GET', 'POST'])
@login_required
def add_question(video_id):
    if not current_user.is_teacher:
        flash('Only teachers can add questions!')
        return redirect(url_for('home'))
    if request.method == 'POST':
        question = Test(
            question=request.form['question'],
            option_a=request.form['option_a'],
            option_b=request.form['option_b'],
            option_c=request.form['option_c'],
            option_d=request.form['option_d'],
            correct=request.form['correct'],
            video_id=video_id
        )
        db.session.add(question)
        db.session.commit()
        flash('Question added successfully!')
        return redirect(url_for('video', video_id=video_id))
    return render_template('add_question.html', video_id=video_id)

@app.route('/leaderboard')
def leaderboard():
    users = User.query.order_by(User.score.desc()).limit(10).all()
    return render_template('leaderboard.html', users=users)

@app.route('/edit_bio', methods=['GET', 'POST'])
@login_required
def edit_bio():
    if not current_user.is_teacher:
        return redirect(url_for('home'))
    teacher = Teacher.query.filter_by(user_id=current_user.id).first()
    if request.method == 'POST':
        teacher.bio = request.form['bio']
        teacher.subject = request.form['subject']
        db.session.commit()
        flash('Profile updated!')
        return redirect(url_for('my_teacher_profile'))
    return render_template('edit_bio.html', teacher=teacher)

@app.route('/profile')
@login_required
def profile():
    user = User.query.get(current_user.id)
    rank = User.query.filter(User.score > user.score).count() + 1
    completed_tests = TestResult.query.filter_by(user_id=current_user.id).all()
    completed_videos = [Video.query.get(t.video_id) for t in completed_tests]
    return render_template('profile.html', user=user, rank=rank, completed_videos=completed_videos)

@app.route('/upload_photo', methods=['POST'])
@login_required
def upload_photo():
    file = request.files['photo']
    if file and allowed_image(file.filename):
        filename = secure_filename(f"user_{current_user.id}.{file.filename.rsplit('.', 1)[1].lower()}")
        file.save(os.path.join(app.config['PROFILE_PICS_FOLDER'], filename))
        current_user.profile_pic = filename
        db.session.commit()
        flash('Profile photo updated!')
    else:
        flash('Invalid file! Use png, jpg, jpeg or gif.')
    if current_user.is_teacher:
        teacher = Teacher.query.filter_by(user_id=current_user.id).first()
        return redirect(url_for('my_teacher_profile'))
    return redirect(url_for('profile'))

@app.route('/my_teacher_profile')
@login_required
def my_teacher_profile():
    if not current_user.is_teacher:
        return redirect(url_for('home'))
    teacher = Teacher.query.filter_by(user_id=current_user.id).first()
    rank = User.query.filter(User.score > current_user.score).count() + 1
    return render_template('teacher_profile.html', teacher=teacher, user=current_user, rank=rank)

@app.route('/profile_pics/<filename>')
def profile_pic(filename):
    return send_from_directory(app.config['PROFILE_PICS_FOLDER'], filename)

@app.route('/subject/<path:subject_name>')
def subject(subject_name):
    videos = Video.query.filter_by(subject=subject_name).all()
    return render_template('subject.html', videos=videos, subject_name=subject_name)

with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(debug=False)