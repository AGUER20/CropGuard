"""
Entry point + CLI bootstrap commands.

Usage (from the project root, inside your virtualenv):

    flask --app run.py init-db          # create all tables from the models
    flask --app run.py seed-demo-data   # insert sample diseases + demo users
    flask --app run.py run              # start the dev server
    python run.py                       # (equivalent) start the dev server
"""
import click
from app import create_app
from app.extensions import db
from app.models import User, DiseaseClass, TreatmentGuide, Role

app = create_app()


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
        diseases = [
            ("Healthy", "Maize", "No visible disease symptoms.", 0, None),
            ("Maize Leaf Blight", "Maize", "Long, cigar-shaped grey-green lesions on leaves.", 1,
             ("Apply a registered fungicide (e.g. strobilurin-based) at early symptom onset; "
              "remove and destroy heavily infected leaves.",
              "Rotate maize with a non-host crop for at least one season.",
              "Use resistant maize varieties and avoid overhead irrigation late in the day.")),
            ("Maize Common Rust", "Maize", "Small, reddish-brown pustules on both leaf surfaces.", 2,
             ("Apply a triazole or strobilurin fungicide when pustules first appear.",
              "Scout fields weekly during humid periods.",
              "Plant rust-tolerant hybrids and ensure adequate plant spacing.")),
            ("Tomato Early Blight", "Tomato", "Dark concentric-ringed spots on older leaves.", 3,
             ("Remove infected lower leaves and apply a chlorothalonil-based fungicide every 7-10 days.",
              "Stake plants to improve airflow.",
              "Mulch around the base and avoid wetting foliage when watering.")),
            ("Tomato Late Blight", "Tomato", "Water-soaked lesions turning brown/black, spreading fast.", 4,
             ("Apply a copper-based or systemic fungicide immediately; remove severely infected plants.",
              "Increase row spacing to reduce humidity.",
              "Use certified disease-free seedlings and avoid overhead irrigation.")),
            ("Bean Angular Leaf Spot", "Bean", "Angular brown lesions bound by leaf veins.", 5,
             ("Apply a copper-based bactericide/fungicide at first sign of lesions.",
              "Avoid working in fields when leaves are wet.",
              "Rotate with non-legume crops and use certified clean seed.")),
        ]
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


if __name__ == "__main__":
    app.run(debug=True)
