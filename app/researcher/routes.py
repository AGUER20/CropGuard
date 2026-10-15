"""
Researcher / agricultural officer controller: browse the disease library,
monitor prediction trends, and contribute new training images to grow the
dataset — the "elevated access" actions described in 3.8.
"""
import os
import uuid

from flask import Blueprint, render_template, redirect, url_for, flash, current_app
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename

from app.extensions import db
from app.models import DiseaseClass, PredictionRecord, TrainingImage
from app.utils.decorators import role_required, allowed_file
from app.researcher.forms import TrainingImageForm

researcher_bp = Blueprint("researcher", __name__, template_folder="../templates/researcher")


@researcher_bp.route("/dashboard")
@login_required
@role_required("researcher")
def dashboard():
    disease_count = DiseaseClass.query.count()
    prediction_count = PredictionRecord.query.count()
    pending_training_images = TrainingImage.query.filter_by(status="pending").count()
    return render_template(
        "researcher/dashboard.html",
        disease_count=disease_count,
        prediction_count=prediction_count,
        pending_training_images=pending_training_images,
    )


@researcher_bp.route("/library")
@login_required
@role_required("researcher")
def library():
    diseases = DiseaseClass.query.order_by(DiseaseClass.crop_type, DiseaseClass.name).all()
    return render_template("researcher/library.html", diseases=diseases)


@researcher_bp.route("/trends")
@login_required
@role_required("researcher")
def trends():
    # Aggregate prediction counts per disease for a simple Chart.js bar chart.
    rows = (
        db.session.query(DiseaseClass.name, db.func.count(PredictionRecord.id))
        .join(PredictionRecord, PredictionRecord.disease_class_id == DiseaseClass.id)
        .group_by(DiseaseClass.name)
        .order_by(db.func.count(PredictionRecord.id).desc())
        .all()
    )
    labels = [r[0] for r in rows]
    counts = [r[1] for r in rows]

    avg_confidence = db.session.query(db.func.avg(PredictionRecord.confidence_score)).scalar() or 0
    return render_template(
        "researcher/trends.html",
        labels=labels,
        counts=counts,
        avg_confidence=round(avg_confidence * 100, 1),
        total=sum(counts),
    )


@researcher_bp.route("/upload-training", methods=["GET", "POST"])
@login_required
@role_required("researcher")
def upload_training():
    form = TrainingImageForm()
    form.disease_class_id.choices = [(d.id, d.name) for d in DiseaseClass.query.order_by(DiseaseClass.name)]

    if form.validate_on_submit():
        file = form.image.data
        if not allowed_file(file.filename, current_app.config["ALLOWED_EXTENSIONS"]):
            flash("Unsupported file type.", "danger")
            return redirect(url_for("researcher.upload_training"))

        filename = f"train_{uuid.uuid4().hex}_{secure_filename(file.filename)}"
        save_path = os.path.join(current_app.config["UPLOAD_FOLDER"], filename)
        file.save(save_path)

        record = TrainingImage(
            disease_class_id=form.disease_class_id.data,
            uploaded_by_id=current_user.id,
            image_path=f"uploads/{filename}",
        )
        db.session.add(record)
        db.session.commit()
        flash("Training image uploaded and queued for review.", "success")
        return redirect(url_for("researcher.upload_training"))

    recent_uploads = (
        TrainingImage.query.filter_by(uploaded_by_id=current_user.id)
        .order_by(TrainingImage.uploaded_at.desc())
        .limit(10)
        .all()
    )
    return render_template("researcher/upload_training.html", form=form, recent_uploads=recent_uploads)
