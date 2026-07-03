from datetime import date
from flask import Flask, abort, render_template, redirect, url_for, flash, request
from flask_bootstrap import Bootstrap5
from flask_ckeditor import CKEditor
from flask_gravatar import Gravatar
from flask_login import UserMixin, login_user, LoginManager, current_user, logout_user, login_required
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import relationship, DeclarativeBase, Mapped, mapped_column
from sqlalchemy import Integer, String, Text, ForeignKey
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
# Import your forms from the forms.py
from forms import CreatePostForm, RegisterForm, LoginForm, CommentForm
from functools import wraps
from hashlib import md5
from pathlib import Path
import os
from dotenv import load_dotenv


base_dir = Path(__file__).resolve().parent
env_file = base_dir / ".env"

if env_file.exists():
    load_dotenv()

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'DevKey')
    SQLALCHEMY_DATABASE_URI = os.environ.get('SQLALCHEMY_DATABASE_URI', 'sqlite:///new_posts.db')

class Base(DeclarativeBase):
    pass

# CREATE DATABASE
db = SQLAlchemy(model_class=Base)

# TODO: Create a User table for all your registered users. 
class User(UserMixin, db.Model):
    __tablename__ = "user"
    id:Mapped[int] = mapped_column(Integer, primary_key=True)
    email:Mapped[str] = mapped_column(String(100), unique=True)
    password:Mapped[str] = mapped_column(String(100))
    name:Mapped[str] = mapped_column(String(100))
    #This will act like a List of BlogPost objects attached to each User. 
    #The "author" refers to the author property in the BlogPost class.
    posts:Mapped[list['BlogPost']] = relationship(back_populates='author') # setting up one to many
    comments:Mapped[list['Comment']] = relationship(back_populates='comment_author') # setting up one to many

    def avatar(self):
        digest = md5(self.email.lower().encode('utf-8')).hexdigest()
        return f"https://www.gravatar.com/avatar/{digest}?d=identicon" #&s={size}"


# CONFIGURE TABLES
class BlogPost(db.Model):
    __tablename__ = "blog_posts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(250), unique=True, nullable=False)
    subtitle: Mapped[str] = mapped_column(String(250), nullable=False)
    date: Mapped[str] = mapped_column(String(250), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)    
    img_url: Mapped[str] = mapped_column(String(250), nullable=False)
    # Create Foreign Key, "user.id" the user refers to the tablename of User.
    author_id:Mapped[int] = mapped_column(ForeignKey('user.id'))
    # Create reference to the User object. The "posts" refers to the posts property in the User class.
    author:Mapped['User'] = relationship(back_populates='posts')

    comments:Mapped[list['Comment']] = relationship(back_populates='parent_post') # setting up one to many

    def __repr__(self):
        return self.__tablename__
    
class Comment(db.Model):
    __tablename__ = "comments"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    # Create Foreign Key, "user.id" the user refers to the tablename of User.
    author_id:Mapped[int] = mapped_column(ForeignKey('user.id'))
    # Create reference to the User object. The "comments" refers to the comments property in the User class.
    comment_author:Mapped['User'] = relationship(back_populates='comments')
    post_id:Mapped[int] = mapped_column(ForeignKey('blog_posts.id'))
    # Create reference to the User object. The "comments" refers to the comments property in the User class.
    parent_post:Mapped['BlogPost'] = relationship(back_populates='comments')


app = Flask(__name__)
app.config['SECRET_KEY'] = Config.SECRET_KEY

app.config['SQLALCHEMY_DATABASE_URI'] = Config.SQLALCHEMY_DATABASE_URI

db.init_app(app)

ckeditor = CKEditor(app)
Bootstrap5(app)

# TODO: Configure Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)

@login_manager.user_loader
def load_user(user_id):
    return db.get_or_404(User, user_id)


with app.app_context():
    db.create_all()

# custom wrapper function to return function only to the admin user
def admin_only(func):
    @wraps(func)
    def decorated_function(*args, **kwargs):
        if current_user.id != 1:
            return abort(403)
        return func(*args, **kwargs)
    return decorated_function

# cutom wrapper to return the function only to instance owner or site admin
def owner_or_admin(func):
    @wraps(func)
    def decorated_function(*args, **kwargs):
        post_id = kwargs.get('post_id')
        comment_id = kwargs.get('comment_id')

        if comment_id:
            comment = db.get_or_404(Comment, comment_id)
            user_id = comment.author_id
        elif post_id:
            post = db.get_or_404(BlogPost, post_id)
            user_id = post.author_id
        else:
            return abort(400)
        
        if current_user.id == user_id or current_user.id == 1:
            return func(*args, **kwargs)
        return abort(403)
    return decorated_function


# TODO: Use Werkzeug to hash the user's password when creating a new user.
@app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegisterForm()

    if form.validate_on_submit():
        
        email = form.email.data        

        user = db.session.scalar(db.select(User).where(User.email == email))

        if user:
            flash('A user with that email already exists. Login')
            return redirect(url_for('login'))
        
        name = form.name.data
        password = form.password.data
        hash_word = generate_password_hash(password=password, method="pbkdf2", salt_length=8)
        
        new_user = User(name=name, email=email, password=hash_word)
        try:
            db.session.add(new_user)
            db.session.commit()
        except Exception as e:
            print(f"Error: {e}")
            flash('An unexpected error occurred. Please try again')
            return redirect(url_for('register'))
        else:
            print("successfully added user")
            login_user(new_user)
            return redirect(url_for('login'))        

    return render_template("register.html", form=form)


# TODO: Retrieve a user from the database based on their email. 
@app.route('/login', methods=['GET', 'POST'])
def login():

    form = LoginForm()

    if form.validate_on_submit():
        email = form.email.data
        password = form.password.data

        user = db.session.scalar(db.select(User).where(User.email == email))

        if not user:
            flash('A user with that email does not exist')
            return redirect(url_for('login'))
        elif not check_password_hash(user.password, password):
            flash('That passoword is incorrect')
            return redirect(url_for('login'))
        else:
            login_user(user)
            return redirect(url_for('get_all_posts'))

    return render_template("login.html", form=form)


@app.route('/logout')
@login_required 
def logout():
    logout_user()
    return redirect(url_for('get_all_posts'))


@app.route('/')
def get_all_posts():    

    page = request.args.get('page', 1, type=int)

    pagination = db.paginate(db.select(BlogPost).order_by(BlogPost.id.desc()), page=page, per_page=3)

    return render_template("index.html", pagination=pagination)



# TODO: Allow logged-in users to comment on posts
@app.route("/post/<int:post_id>", methods=["GET", "POST"])
def show_post(post_id):
    requested_post = db.get_or_404(BlogPost, post_id)
    form = CommentForm()

    if form.validate_on_submit():
        new_comment = Comment(text=form.comment.data, comment_author=current_user, parent_post=requested_post)
        db.session.add(new_comment)
        db.session.commit()           
        
        return redirect(url_for('show_post', post_id=post_id))    
    
    comments = db.session.scalars(db.select(Comment)).all()
    
    return render_template("post.html", post=requested_post, form=form, comments=comments)


# TODO: Use a decorator so only an admin user can create a new post
@app.route("/new-post", methods=["GET", "POST"])
@login_required # calling the custom wrapper function
def add_new_post():
    form = CreatePostForm()
    if form.validate_on_submit():
        new_post = BlogPost(
            title=form.title.data,
            subtitle=form.subtitle.data,
            body=form.body.data,
            img_url=form.img_url.data,
            author=current_user,
            date=date.today().strftime("%B %d, %Y")
        )
        db.session.add(new_post)
        db.session.commit()
        return redirect(url_for("get_all_posts"))
    return render_template("make-post.html", form=form)


# TODO: Use a decorator so only an admin user can edit a post
@app.route("/edit-post/<int:post_id>", methods=["GET", "POST"])
@owner_or_admin
@login_required # calling the custom wrapper function
def edit_post(post_id):
    post = db.get_or_404(BlogPost, post_id)
    edit_form = CreatePostForm(
        title=post.title,
        subtitle=post.subtitle,
        img_url=post.img_url,
        author=post.author,
        body=post.body
    )
    if edit_form.validate_on_submit():
        post.title = edit_form.title.data
        post.subtitle = edit_form.subtitle.data
        post.img_url = edit_form.img_url.data
        post.author = current_user
        post.body = edit_form.body.data
        db.session.commit()
        return redirect(url_for("show_post", post_id=post.id))
    return render_template("make-post.html", form=edit_form, is_edit=True)


@app.route("/user/<int:user_id>/delete", methods=['POST'])
@admin_only
def delete_user(user_id):
    user_to_delete = db.get_or_404(User, user_id)
    db.session.delete(user_to_delete)
    db.session.commit()
    return redirect(url_for('get_all_posts'))


# TODO: Use a decorator so only an admin user can delete a post
@app.route("/post/<int:post_id>/delete")
@owner_or_admin
@login_required
def delete_post(post_id):
    post_to_delete = db.get_or_404(BlogPost, post_id)
    db.session.delete(post_to_delete)
    db.session.commit()
    return redirect(url_for('get_all_posts'))


# TODO: Use a decorator so only an admin user can delete a post
@app.route("/post/<int:post_id>/comment/<int:comment_id>/delete")
@owner_or_admin
@login_required
def delete_comment(post_id, comment_id):

    comment_to_delete = db.get_or_404(Comment, comment_id)
    db.session.delete(comment_to_delete)
    db.session.commit()
    return redirect(url_for('show_post', post_id=post_id))


@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/contact")
def contact():
    return render_template("contact.html")


if __name__ == "__main__":
    app.run(debug=False)
