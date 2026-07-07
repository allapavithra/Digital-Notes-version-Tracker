import os
from flask import Flask, render_template, url_for, flash, redirect, request, send_file
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_login import LoginManager, login_user, current_user, logout_user, login_required
from models import db, User, Note, NoteVersion
from diff_utils import generate_side_by_side_diff, generate_structured_diff
from advanced_utils import extract_advanced_text, generate_advanced_structured_diff, insert_line_and_generate
import PyPDF2
import docx

app = Flask(__name__)
# Using a static secret key for dev
app.config['SECRET_KEY'] = '5791628bb0b13ce0c676dfde280ba245'
# The db will be created in an instance folder if not specified full path, using relative for now
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///site.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message_category = 'info'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def extract_text(file):
    filename = file.filename.lower()
    if filename.endswith('.pdf'):
        pdf_reader = PyPDF2.PdfReader(file)
        text = ''
        for page in pdf_reader.pages:
            t = page.extract_text()
            if t:
                text += t + '\n'
        return text
    elif filename.endswith('.docx'):
        doc = docx.Document(file)
        text = '\n'.join([para.text for para in doc.paragraphs])
        return text
    else:
        return file.read().decode('utf-8')

@app.route("/")
def home():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return render_template('layout.html')  # or a landing page

@app.route("/register", methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        user = User.query.filter_by(username=username).first()
        if user:
            flash('Username already exists. Please choose a different one.', 'danger')
        else:
            hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
            user = User(username=username, password=hashed_password)
            db.session.add(user)
            db.session.commit()
            flash('Your account has been created! You are now able to log in', 'success')
            return redirect(url_for('login'))
    return render_template('register.html')

@app.route("/login", methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
        
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        user = User.query.filter_by(username=username).first()
        if user and bcrypt.check_password_hash(user.password, password):
            login_user(user, remember=True)
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('dashboard'))
        else:
            flash('Login Unsuccessful. Please check username and password', 'danger')
    return render_template('login.html')

@app.route("/logout")
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route("/dashboard")
@login_required
def dashboard():
    notes = Note.query.filter_by(author=current_user).order_by(Note.date_posted.desc()).all()
    # Find most edited note if needed
    for note in notes:
        note.version_count = len(note.versions)
        note.latest_version = note.versions[-1] if note.versions else None
        
    return render_template('dashboard.html', notes=notes)

@app.route("/note/new", methods=['GET', 'POST'])
@login_required
def new_note():
    if request.method == 'POST':
        title = request.form.get('title')
        content = request.form.get('content')
        file = request.files.get('file')
        
        if file and file.filename != '':
            try:
                content = extract_text(file)
            except Exception as e:
                flash(f'Error extracting file: {str(e)}', 'danger')
                return render_template('editor.html', title="New Note")
                
        if not title or not content:
            flash('Title and content are required.', 'danger')
            return render_template('editor.html', title="New Note", note_title=title, content=content)
            
        note = Note(title=title, author=current_user)
        db.session.add(note)
        db.session.flush() # get note.id
        
        version = NoteVersion(content=content, version_num=1, note_id=note.id)
        db.session.add(version)
        db.session.commit()
        flash('Note has been created!', 'success')
        return redirect(url_for('dashboard'))
        
    return render_template('editor.html', title="New Note")

@app.route("/note/<int:note_id>/edit", methods=['GET', 'POST'])
@login_required
def edit_note(note_id):
    note = Note.query.get_or_404(note_id)
    if note.author != current_user:
        flash('Unauthorized', 'danger')
        return redirect(url_for('dashboard'))
        
    latest_version = note.versions[-1]
    
    if request.method == 'POST':
        title = request.form.get('title')
        content = request.form.get('content')
        file = request.files.get('file')
        
        if file and file.filename != '':
            try:
                content = extract_text(file)
            except Exception as e:
                flash(f'Error extracting file: {str(e)}', 'danger')
                return render_template('editor.html', title="Edit Note", note=note, content=latest_version.content)
                
        if title != note.title:
            note.title = title
            
        if content and latest_version.content:
            content_norm = content.replace('\r\n', '\n')
            latest_norm = latest_version.content.replace('\r\n', '\n')
            has_changed = (content_norm != latest_norm)
        else:
            has_changed = (content != latest_version.content)

        if has_changed:
            new_v_num = latest_version.version_num + 1
            new_version = NoteVersion(content=content, version_num=new_v_num, note_id=note.id)
            db.session.add(new_version)
            
        db.session.commit()
        flash('Note has been updated!', 'success')
        return redirect(url_for('timeline', note_id=note.id))
        
    return render_template('editor.html', title="Edit Note", note=note, content=latest_version.content)

@app.route("/note/<int:note_id>/timeline")
@login_required
def timeline(note_id):
    note = Note.query.get_or_404(note_id)
    if note.author != current_user:
        flash('Unauthorized', 'danger')
        return redirect(url_for('dashboard'))
        
    versions = reversed(note.versions) # newest first
    return render_template('timeline.html', note=note, versions=versions)

@app.route("/note/<int:note_id>/compare", methods=['GET', 'POST'])
@login_required
def compare(note_id):
    note = Note.query.get_or_404(note_id)
    if note.author != current_user:
        flash('Unauthorized', 'danger')
        return redirect(url_for('dashboard'))
        
    diff_result = None
    v1_display = None
    v2_display = None
    selected_v1 = None
    selected_v2 = None

    if request.method == 'POST':
        # Check if an upload file was submitted
        file = request.files.get('file')
        if file and file.filename != '':
            try:
                uploaded_text = extract_text(file)
                base_v_id = request.form.get('base_version')
                base_v = NoteVersion.query.get(base_v_id) if base_v_id else note.versions[-1]
                
                diff_result = generate_side_by_side_diff(base_v.content, uploaded_text)
                return render_template('compare.html', note=note, diff_result=diff_result, 
                                       v1_display=f"Version {base_v.version_num}", 
                                       v2_display=f"Uploaded: {file.filename}",
                                       all_versions=note.versions, show_selectors=True, selected_v1=base_v.id)
            except Exception as e:
                flash(f'Error extracting file: {str(e)}', 'danger')
                return redirect(url_for('compare', note_id=note.id))
        else:
            v1_id = request.form.get('v1')
            v2_id = request.form.get('v2')
            
            v1 = NoteVersion.query.get(v1_id)
            v2 = NoteVersion.query.get(v2_id)
            
            if not v1 or not v2:
                flash('Invalid versions selected', 'danger')
                return redirect(url_for('timeline', note_id=note.id))
                
            diff_result = generate_side_by_side_diff(v1.content, v2.content)
            return render_template('compare.html', note=note, diff_result=diff_result,
                                   v1_display=f"Version {v1.version_num} ({v1.created_at.strftime('%b %d, %Y')})",
                                   v2_display=f"Version {v2.version_num} ({v2.created_at.strftime('%b %d, %Y')})",
                                   all_versions=note.versions, show_selectors=True, selected_v1=v1.id, selected_v2=v2.id)
        
    # By default, compare latest 2 if available
    if len(note.versions) >= 2:
        v1 = note.versions[-2]
        v2 = note.versions[-1]
        diff_result = generate_side_by_side_diff(v1.content, v2.content)
        return render_template('compare.html', note=note, diff_result=diff_result,
                               v1_display=f"Version {v1.version_num} ({v1.created_at.strftime('%b %d, %Y')})",
                               v2_display=f"Version {v2.version_num} ({v2.created_at.strftime('%b %d, %Y')})",
                               all_versions=note.versions, show_selectors=True, selected_v1=v1.id, selected_v2=v2.id)
                               
    return render_template('compare.html', note=note, all_versions=note.versions, show_selectors=True)

@app.route("/comparator", methods=['GET', 'POST'])
def comparator():
    if request.method == 'POST':
        action = request.form.get('action', 'compare')
        
        if action == 'compare':
            file1 = request.files.get('file1')
            file2 = request.files.get('file2')
            
            if file1 and file1.filename != '' and file2 and file2.filename != '':
                try:
                    ext1 = os.path.splitext(file1.filename)[1].lower()
                    ext2 = os.path.splitext(file2.filename)[1].lower()
                    text1 = extract_advanced_text(file1, ext1)
                    text2 = extract_advanced_text(file2, ext2)
                    diff_result = generate_advanced_structured_diff(text1, text2)
                    return render_template('comparator.html', diff_result=diff_result, file1=file1.filename, file2=file2.filename)
                except Exception as e:
                    flash(f'Error comparing files: {str(e)}', 'danger')
            else:
                flash('Please upload both files for comparison.', 'warning')
                
        elif action == 'insert':
            file_edit = request.files.get('file_edit')
            line_num = request.form.get('line_num', type=int)
            line_content = request.form.get('line_content')
            
            if file_edit and file_edit.filename != '' and line_num is not None and line_content:
                try:
                    ext = os.path.splitext(file_edit.filename)[1].lower()
                    buf, mime = insert_line_and_generate(file_edit, ext, line_num, line_content)
                    
                    return send_file(
                        buf,
                        mimetype=mime,
                        as_attachment=True,
                        download_name=f"edited_{file_edit.filename}"
                    )
                except Exception as e:
                    flash(f'Error modifying file: {str(e)}', 'danger')
            else:
                flash('Please provide file, line number, and text to insert.', 'warning')
                
    return render_template('comparator.html')

@app.route("/note/<int:note_id>/restore/<int:version_id>")
@login_required
def restore(note_id, version_id):
    note = Note.query.get_or_404(note_id)
    if note.author != current_user:
        flash('Unauthorized', 'danger')
        return redirect(url_for('dashboard'))
        
    target_version = NoteVersion.query.get_or_404(version_id)
    latest_version = note.versions[-1]
    
    if target_version.content != latest_version.content:
        new_v_num = latest_version.version_num + 1
        new_version = NoteVersion(content=target_version.content, version_num=new_v_num, note_id=note.id)
        db.session.add(new_version)
        db.session.commit()
        flash(f'Restored to Version {target_version.version_num} as new Version {new_v_num}', 'success')
    else:
        flash('Already at this version.', 'info')
        
    return redirect(url_for('timeline', note_id=note.id))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
