"""
SQLAlchemy models — the Model layer of the MVC architecture described in
Chapter Three (3.8) of the proposal.

Entities mirror the ERD referenced in the proposal: User, DiseaseClass,
PredictionRecord, TreatmentGuide -- plus Feedback (user ratings/corrections
that feed the retraining loop) and TrainingImage (researcher-contributed
dataset growth) which the conceptual diagram's feedback loop and the
researcher role both depend on.
"""
from datetime import datetime
from flask_login import UserMixin
from app.extensions import db, bcrypt


class Role:
    FARMER = "farmer"
    RESEARCHER = "researcher"
    ADMIN = "admin"
    ALL = (FARMER, RESEARCHER, ADMIN)


class User(db.Model, UserMixin):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(120), nullable=False)
    username = db.Column(db.String(60), unique=True, nullable=False, index=True)
    email = db.Column(db.String(150), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default=Role.FARMER)

    # Researchers/agricultural officers get elevated access only once an
    # admin approves the account (see 3.8 "different access levels").
    is_approved = db.Column(db.Boolean, nullable=False, default=True)
    is_active_account = db.Column(db.Boolean, nullable=False, default=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login_at = db.Column(db.DateTime, nullable=True)

    predictions = db.relationship("PredictionRecord", backref="farmer", lazy="dynamic",
                                   foreign_keys="PredictionRecord.user_id")
    feedback_entries = db.relationship("Feedback", backref="author", lazy="dynamic")
    training_uploads = db.relationship("TrainingImage", backref="uploader", lazy="dynamic")

    # -- password helpers -------------------------------------------------
    def set_password(self, raw_password: str) -> None:
        self.password_hash = bcrypt.generate_password_hash(raw_password).decode("utf-8")

    def check_password(self, raw_password: str) -> bool:
        return bcrypt.check_password_hash(self.password_hash, raw_password)

    # -- Flask-Login required property ------------------------------------
    @property
    def is_active(self):  # overrides UserMixin.is_active
        return self.is_active_account

    # -- role helpers -------------------------------------------------------
    def is_admin(self):
        return self.role == Role.ADMIN

    def is_researcher(self):
        return self.role == Role.RESEARCHER

    def is_farmer(self):
        return self.role == Role.FARMER

    def __repr__(self):
        return f"<User {self.username} ({self.role})>"


class DiseaseClass(db.Model):
    """One row per label the MobileNetV2 model can predict."""
    __tablename__ = "disease_classes"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)
    crop_type = db.Column(db.String(80), nullable=False)
    description = db.Column(db.Text, nullable=True)
    sample_image_path = db.Column(db.String(255), nullable=True)
    # Index the model output vector maps to -> this row (class_indices.json)
    model_output_index = db.Column(db.Integer, nullable=True, unique=True)

    treatment_guide = db.relationship("TreatmentGuide", backref="disease", uselist=False)
    predictions = db.relationship("PredictionRecord", backref="disease", lazy="dynamic")
    training_images = db.relationship("TrainingImage", backref="disease", lazy="dynamic")

    def __repr__(self):
        return f"<DiseaseClass {self.name}>"


class TreatmentGuide(db.Model):
    """Treatment & management advice tied 1-to-1 with a DiseaseClass."""
    __tablename__ = "treatment_guides"

    id = db.Column(db.Integer, primary_key=True)
    disease_class_id = db.Column(db.Integer, db.ForeignKey("disease_classes.id"), nullable=False, unique=True)
    treatment_text = db.Column(db.Text, nullable=False)
    management_tips = db.Column(db.Text, nullable=True)
    prevention_tips = db.Column(db.Text, nullable=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class PredictionRecord(db.Model):
    """One row per diagnosis run by a farmer (or any logged-in user)."""
    __tablename__ = "prediction_records"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    disease_class_id = db.Column(db.Integer, db.ForeignKey("disease_classes.id"), nullable=True)

    image_path = db.Column(db.String(255), nullable=False)
    confidence_score = db.Column(db.Float, nullable=False)  # 0.0 - 1.0
    predicted_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    inference_ms = db.Column(db.Integer, nullable=True)  # latency, for the <3s NFR in 3.2.3

    feedback = db.relationship("Feedback", backref="prediction", uselist=False)

    def confidence_percent(self):
        return round(self.confidence_score * 100, 1)


class Feedback(db.Model):
    """
    Farmer rating/correction on a prediction — this is the feedback loop
    described in the conceptual diagram (2.5) that helps the system
    "keep being integrated" and improve accuracy over time.
    """
    __tablename__ = "feedback"

    id = db.Column(db.Integer, primary_key=True)
    prediction_id = db.Column(db.Integer, db.ForeignKey("prediction_records.id"), nullable=False, unique=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    rating = db.Column(db.Integer, nullable=False)  # 1-5 stars
    is_flagged_incorrect = db.Column(db.Boolean, default=False)
    comment = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class TrainingImage(db.Model):
    """
    New dataset images contributed by researchers/agricultural officers to
    expand the training set (3.8, researcher elevated-access actions).
    """
    __tablename__ = "training_images"

    id = db.Column(db.Integer, primary_key=True)
    disease_class_id = db.Column(db.Integer, db.ForeignKey("disease_classes.id"), nullable=False)
    uploaded_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    image_path = db.Column(db.String(255), nullable=False)
    status = db.Column(db.String(20), default="pending")  # pending | approved | rejected
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)
