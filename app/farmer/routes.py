"""
Farmer controller: dashboard, photo upload -> preprocessing -> MobileNetV2
inference -> treatment advice, diagnosis history, and feedback submission.

This is the "core processing pipeline" from proposal section 3.8:
Input -> Preprocessing -> Processing -> Output -> Feedback loop.
"""
import os
import uuid

from flask import Blueprint, render_template, redirect, url_for, flash, current_app, abort
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename

from app.extensions import db
from app.models import DiseaseClass, PredictionRecord, Feedback
from app.utils.decorators import role_required, allowed_file
from app.farmer.forms import DiagnoseForm, FeedbackForm
from app.ml.preprocessing import looks_like_leaf_photo, preprocess_for_inference
from app.ml import inference as ml_inference

farmer_bp = Blueprint("farmer", __name__, template_folder="../templates/farmer")


@farmer_bp.route("/dashboard")
@login_required
@role_required("farmer")
def dashboard():
    recent = (
        PredictionRecord.query.filter_by(user_id=current_user.id)
        .order_by(PredictionRecord.predicted_at.desc())
        .limit(5)
        .all()
    )
    total_diagnoses = PredictionRecord.query.filter_by(user_id=current_user.id).count()
    return render_template("farmer/dashboard.html", recent=recent, total_diagnoses=total_diagnoses)


@farmer_bp.route("/diagnose", methods=["GET", "POST"])
@login_required
@role_required("farmer")
def diagnose():
    form = DiagnoseForm()
    if form.validate_on_submit():
        file = form.leaf_image.data
        if not allowed_file(file.filename, current_app.config["ALLOWED_EXTENSIONS"]):
            flash("Unsupported file type.", "danger")
            return redirect(url_for("farmer.diagnose"))

        # --- store the upload ---
        filename = f"{uuid.uuid4().hex}_{secure_filename(file.filename)}"
        save_path = os.path.join(current_app.config["UPLOAD_FOLDER"], filename)
        file.save(save_path)

        if not looks_like_leaf_photo(save_path):
            os.remove(save_path)
            flash("Upload a clear, close-up photo of a plant leaf to get a diagnosis.", "warning")
            return redirect(url_for("farmer.diagnose"))

        # --- preprocessing: resize, colour-adjust, normalise ---
        image_array = preprocess_for_inference(save_path, current_app.config["IMAGE_TARGET_SIZE"])

        # --- processing: MobileNetV2 inference ---
        fallback_names = [d.name for d in DiseaseClass.query.order_by(DiseaseClass.model_output_index).all()] \
            or ["Healthy"]
        predicted_name, confidence, latency_ms = ml_inference.predict(
            image_array, save_path, current_app.config, fallback_names
        )

        disease = DiseaseClass.query.filter_by(name=predicted_name).first()

        record = PredictionRecord(
            user_id=current_user.id,
            disease_class_id=disease.id if disease else None,
            image_path=f"uploads/{filename}",
            confidence_score=confidence,
            inference_ms=latency_ms,
        )
        db.session.add(record)
        db.session.commit()

        flash("Diagnosis complete.", "success")
        return redirect(url_for("farmer.result", prediction_id=record.id))

    return render_template("farmer/upload.html", form=form)


@farmer_bp.route("/result/<int:prediction_id>")
@login_required
@role_required("farmer")
def result(prediction_id):
    record = db.session.get(PredictionRecord, prediction_id)
    if record is None or record.user_id != current_user.id:
        abort(404)
    feedback_form = FeedbackForm(prediction_id=record.id)
    already_rated = Feedback.query.filter_by(prediction_id=record.id).first() is not None
    return render_template(
        "farmer/result.html",
        record=record,
        feedback_form=feedback_form,
        already_rated=already_rated,
        demo_mode=ml_inference.is_using_demo_model(),
    )


@farmer_bp.route("/history")
@login_required
@role_required("farmer")
def history():
    page = 1
    records = (
        PredictionRecord.query.filter_by(user_id=current_user.id)
        .order_by(PredictionRecord.predicted_at.desc())
        .paginate(page=page, per_page=current_app.config["ITEMS_PER_PAGE"], error_out=False)
    )
    return render_template("farmer/history.html", records=records)


@farmer_bp.route("/feedback/<int:prediction_id>", methods=["POST"])
@login_required
@role_required("farmer")
def submit_feedback(prediction_id):
    record = db.session.get(PredictionRecord, prediction_id)
    if record is None or record.user_id != current_user.id:
        abort(404)

    form = FeedbackForm()
    if form.validate_on_submit():
        existing = Feedback.query.filter_by(prediction_id=record.id).first()
        if existing is None:
            fb = Feedback(
                prediction_id=record.id,
                user_id=current_user.id,
                rating=form.rating.data,
                comment=form.comment.data,
                is_flagged_incorrect=(form.rating.data <= 2),
            )
            db.session.add(fb)
            db.session.commit()
            flash("Thanks — your feedback helps CropGuard improve.", "success")
        else:
            flash("You've already submitted feedback for this diagnosis.", "info")
    else:
        flash("Please give a rating between 1 and 5.", "danger")

    return redirect(url_for("farmer.result", prediction_id=record.id))
