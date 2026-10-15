"""
Authentication controller: register / login / logout.

The login view mirrors the "Alternative: invalid -> try again / valid ->
login successful" flow from the sequence diagrams — credentials are
verified against the hashed password in the database, and either branch
gives the user clear feedback.
"""
from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user

from app.extensions import db
from app.models import User, Role
from app.auth.forms import RegisterForm, LoginForm

auth_bp = Blueprint("auth", __name__, template_folder="../templates/auth")


def _redirect_for_role(user: User):
    if user.is_admin():
        return redirect(url_for("admin.dashboard"))
    if user.is_researcher():
        return redirect(url_for("researcher.dashboard"))
    return redirect(url_for("farmer.dashboard"))


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return _redirect_for_role(current_user)

    form = RegisterForm()
    if form.validate_on_submit():
        user = User(
            full_name=form.full_name.data.strip(),
            username=form.username.data.strip(),
            email=form.email.data.strip().lower(),
            role=form.role.data,
            # Researcher accounts require admin approval before they get
            # elevated access; farmers are usable immediately.
            is_approved=(form.role.data != Role.RESEARCHER),
        )
        user.set_password(form.password.data)  # bcrypt hashing happens here
        db.session.add(user)
        db.session.commit()

        if user.role == Role.RESEARCHER:
            flash("Account created. A researcher/officer account needs admin approval "
                  "before you can log in with elevated access.", "info")
        else:
            flash("Account created successfully. You can now log in.", "success")
        return redirect(url_for("auth.login"))

    return render_template("auth/register.html", form=form)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return _redirect_for_role(current_user)

    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data.strip()).first()

        # --- verify credentials (alt: invalid vs valid) ---
        if user is None or not user.check_password(form.password.data):
            flash("Invalid username or password. Please try again.", "danger")
            return render_template("auth/login.html", form=form)

        if not user.is_active_account:
            flash("This account has been deactivated. Contact an administrator.", "danger")
            return render_template("auth/login.html", form=form)

        if user.role == Role.RESEARCHER and not user.is_approved:
            flash("Your researcher account is pending admin approval.", "warning")
            return render_template("auth/login.html", form=form)

        # --- valid: login successful ---
        login_user(user)
        user.last_login_at = datetime.utcnow()
        db.session.commit()
        flash(f"Welcome back, {user.full_name.split()[0]}!", "success")
        return _redirect_for_role(user)

    return render_template("auth/login.html", form=form)


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("index"))
