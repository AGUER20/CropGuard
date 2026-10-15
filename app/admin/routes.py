"""
Administrator controller: user-account oversight and detection-activity
reporting (3.8: "Administrators oversee user accounts and generate reports
summarising detection activity").
"""
import csv
import io
from datetime import datetime, timedelta

from flask import Blueprint, render_template, redirect, url_for, flash, abort, Response
from flask_login import login_required, current_user

from app.extensions import db
from app.models import User, PredictionRecord, DiseaseClass, Feedback, Role
from app.utils.decorators import role_required

admin_bp = Blueprint("admin", __name__, template_folder="../templates/admin")


@admin_bp.route("/dashboard")
@login_required
@role_required("admin")
def dashboard():
    stats = {
        "total_users": User.query.count(),
        "total_farmers": User.query.filter_by(role=Role.FARMER).count(),
        "total_researchers": User.query.filter_by(role=Role.RESEARCHER).count(),
        "pending_researchers": User.query.filter_by(role=Role.RESEARCHER, is_approved=False).count(),
        "total_predictions": PredictionRecord.query.count(),
        "total_diseases": DiseaseClass.query.count(),
    }
    return render_template("admin/dashboard.html", stats=stats)


@admin_bp.route("/users")
@login_required
@role_required("admin")
def users():
    all_users = User.query.order_by(User.created_at.desc()).all()
    return render_template("admin/users.html", users=all_users)


@admin_bp.route("/users/<int:user_id>/approve", methods=["POST"])
@login_required
@role_required("admin")
def approve_user(user_id):
    user = db.session.get(User, user_id) or abort(404)
    user.is_approved = True
    db.session.commit()
    flash(f"{user.full_name} approved for elevated access.", "success")
    return redirect(url_for("admin.users"))


@admin_bp.route("/users/<int:user_id>/toggle-active", methods=["POST"])
@login_required
@role_required("admin")
def toggle_active(user_id):
    user = db.session.get(User, user_id) or abort(404)
    if user.id == current_user.id:
        flash("You can't deactivate your own account.", "danger")
        return redirect(url_for("admin.users"))
    user.is_active_account = not user.is_active_account
    db.session.commit()
    state = "activated" if user.is_active_account else "deactivated"
    flash(f"{user.full_name}'s account has been {state}.", "info")
    return redirect(url_for("admin.users"))


@admin_bp.route("/users/<int:user_id>/delete", methods=["POST"])
@login_required
@role_required("admin")
def delete_user(user_id):
    user = db.session.get(User, user_id) or abort(404)
    if user.id == current_user.id:
        flash("You can't delete your own account.", "danger")
        return redirect(url_for("admin.users"))
    db.session.delete(user)
    db.session.commit()
    flash("User account deleted.", "info")
    return redirect(url_for("admin.users"))


@admin_bp.route("/reports")
@login_required
@role_required("admin")
def reports():
    since = datetime.utcnow() - timedelta(days=30)
    recent_predictions = PredictionRecord.query.filter(PredictionRecord.predicted_at >= since).count()

    by_disease = (
        db.session.query(DiseaseClass.name, db.func.count(PredictionRecord.id))
        .join(PredictionRecord, PredictionRecord.disease_class_id == DiseaseClass.id)
        .group_by(DiseaseClass.name)
        .order_by(db.func.count(PredictionRecord.id).desc())
        .all()
    )
    avg_rating = db.session.query(db.func.avg(Feedback.rating)).scalar() or 0
    flagged_incorrect = Feedback.query.filter_by(is_flagged_incorrect=True).count()

    return render_template(
        "admin/reports.html",
        recent_predictions=recent_predictions,
        by_disease=by_disease,
        avg_rating=round(avg_rating, 2),
        flagged_incorrect=flagged_incorrect,
        window_days=30,
    )


@admin_bp.route("/reports/export.csv")
@login_required
@role_required("admin")
def export_report_csv():
    """Download the detection-activity report as CSV (view report ->
    downloadable artifact, matching the UAT task 'downloading a report')."""
    rows = (
        db.session.query(
            PredictionRecord.id,
            User.username,
            DiseaseClass.name,
            PredictionRecord.confidence_score,
            PredictionRecord.predicted_at,
        )
        .join(User, PredictionRecord.user_id == User.id)
        .outerjoin(DiseaseClass, PredictionRecord.disease_class_id == DiseaseClass.id)
        .order_by(PredictionRecord.predicted_at.desc())
        .all()
    )

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["Prediction ID", "Farmer", "Disease", "Confidence %", "Date"])
    for r in rows:
        writer.writerow([r[0], r[1], r[2] or "Unclassified", round(r[3] * 100, 1), r[4].isoformat()])

    return Response(
        buffer.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=cropguard_detection_report.csv"},
    )
