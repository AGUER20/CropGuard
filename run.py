"""
Entry point + CLI bootstrap commands.

Usage (from the project root, inside your virtualenv):

    flask --app run.py init-db          # create all tables from the models
    flask --app run.py seed-demo-data   # insert sample diseases + demo users
    flask --app run.py sync-maize-classes  # migrate an existing disease library safely
    flask --app run.py run              # start the dev server
    python run.py                       # (equivalent) start the dev server
"""
import click
from app import create_app
from app.extensions import db
from app.models import (
    User,
    DiseaseClass,
    PredictionRecord,
    TrainingImage,
    TreatmentGuide,
    Role,
)

app = create_app()

MAIZE_CLASSES = [
    (
        "Healthy",
        "Maize",
        "No visible disease symptoms on the leaf.",
        0,
        None,
    ),
    (
        "Maize Leaf Blight",
        "Maize",
        "Northern leaf blight can cause long, cigar-shaped lesions on maize leaves.",
        1,
        (
            "Confirm symptoms with a local agricultural extension specialist before treatment.",
            "Scout fields and remove or manage infected crop residue where locally recommended.",
            "Use locally adapted resistant varieties and follow local disease-management guidance.",
        ),
    ),
    (
        "Maize Common Rust",
        "Maize",
        "Common rust may appear as raised reddish-brown pustules on maize leaves.",
        2,
        (
            "Confirm symptoms with a local agricultural extension specialist before treatment.",
            "Monitor disease development and follow locally approved integrated pest-management guidance.",
            "Use locally adapted resistant varieties and consult local guidance on planting practices.",
        ),
    ),
    (
        "Maize Gray Leaf Spot",
        "Maize",
        "Gray leaf spot may produce elongated rectangular lesions bounded by leaf veins.",
        3,
        (
            "Confirm symptoms with a local agricultural extension specialist before treatment.",
            "Manage crop residue and rotation according to local agronomic recommendations.",
            "Use locally adapted resistant varieties and follow local disease-management guidance.",
        ),
    ),
]


@app.cli.command("init-db")
def init_db():
    """Create all database tables (equivalent to database/schema.sql)."""
    db.create_all()
    click.echo("Database tables created.")


@app.cli.command("seed-demo-data")
def seed_demo_data():
    """Insert sample disease classes, treatment guides, and one demo
    account per role (admin / researcher / farmer) so the system is
    explorable immediately after setup."""
    if DiseaseClass.query.count() == 0:
        diseases = MAIZE_CLASSES
        for name, crop, desc, idx, guide in diseases:
            d = DiseaseClass(name=name, crop_type=crop, description=desc, model_output_index=idx)
            db.session.add(d)
            db.session.flush()  # get d.id before commit
            if guide:
                treatment_text, management_tips, prevention_tips = guide
                db.session.add(TreatmentGuide(
                    disease_class_id=d.id,
                    treatment_text=treatment_text,
                    management_tips=management_tips,
                    prevention_tips=prevention_tips,
                ))
        db.session.commit()
        click.echo(f"Seeded {len(diseases)} disease classes + treatment guides.")
    else:
        click.echo("Disease classes already exist — skipping.")

    demo_accounts = [
        ("Amina Farmer", "farmer1", "farmer1@example.com", Role.FARMER, "Farmer123!"),
        ("Kevin Researcher", "researcher1", "researcher1@example.com", Role.RESEARCHER, "Research123!"),
        ("Grace Admin", "admin1", "admin1@example.com", Role.ADMIN, "Admin123!"),
    ]
    for full_name, username, email, role, password in demo_accounts:
        if User.query.filter_by(username=username).first():
            continue
        user = User(full_name=full_name, username=username, email=email, role=role, is_approved=True)
        user.set_password(password)
        db.session.add(user)
    db.session.commit()
    click.echo("Demo accounts ready: farmer1/Farmer123!  researcher1/Research123!  admin1/Admin123!")


@app.cli.command("sync-maize-classes")
def sync_maize_classes():
    """Keep only maize diagnosis classes without deleting linked history."""
    maize_names = {disease[0] for disease in MAIZE_CLASSES}
    removed = 0
    preserved = 0

    for disease in DiseaseClass.query.all():
        if disease.name in maize_names:
            continue
        has_predictions = PredictionRecord.query.filter_by(
            disease_class_id=disease.id
        ).first() is not None
        has_training_images = TrainingImage.query.filter_by(
            disease_class_id=disease.id
        ).first() is not None
        if has_predictions or has_training_images:
            disease.model_output_index = None
            preserved += 1
            click.echo(
                f"Preserving {disease.name}: linked prediction or training-image records exist."
            )
            continue
        if disease.treatment_guide is not None:
            db.session.delete(disease.treatment_guide)
        db.session.delete(disease)
        removed += 1

    for disease in DiseaseClass.query.all():
        disease.model_output_index = None
    db.session.flush()

    for name, crop, description, output_index, guide in MAIZE_CLASSES:
        disease = DiseaseClass.query.filter_by(name=name).first()
        if disease is None:
            disease = DiseaseClass(name=name)
            db.session.add(disease)
        disease.crop_type = crop
        disease.description = description
        disease.model_output_index = output_index
        if guide is not None:
            treatment, management, prevention = guide
            treatment_guide = disease.treatment_guide
            if treatment_guide is None:
                treatment_guide = TreatmentGuide(disease=disease)
                db.session.add(treatment_guide)
            treatment_guide.treatment_text = treatment
            treatment_guide.management_tips = management
            treatment_guide.prevention_tips = prevention

    db.session.commit()
    click.echo(
        f"Maize classes synchronized; removed {removed} unlinked non-maize classes "
        f"and preserved {preserved} classes with linked history."
    )


if __name__ == "__main__":
    app.run(debug=True)
