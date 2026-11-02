from app.models import DiseaseClass, PredictionRecord, Role, User
from click.testing import CliRunner


def test_seed_demo_data_creates_only_maize_classes(app, db):
    from run import seed_demo_data

    result = CliRunner().invoke(seed_demo_data)
    assert result.exit_code == 0, result.output

    diseases = DiseaseClass.query.order_by(DiseaseClass.model_output_index).all()
    assert [disease.name for disease in diseases] == [
        "Healthy",
        "Maize Leaf Blight",
        "Maize Common Rust",
        "Maize Gray Leaf Spot",
    ]
    assert {disease.crop_type for disease in diseases} == {"Maize"}


def test_sync_removes_unlinked_classes_but_preserves_prediction_history(app, db):
    from run import sync_maize_classes

    unlinked = DiseaseClass(
        name="Tomato Early Blight",
        crop_type="Tomato",
        model_output_index=3,
    )
    linked = DiseaseClass(
        name="Bean Angular Leaf Spot",
        crop_type="Bean",
        model_output_index=4,
    )
    farmer = User(
        full_name="Test Farmer",
        username="maizehistoryfarmer",
        email="maizehistoryfarmer@example.com",
        role=Role.FARMER,
    )
    farmer.set_password("FarmerPass1")
    db.session.add_all([unlinked, linked, farmer])
    db.session.flush()
    record = PredictionRecord(
        user_id=farmer.id,
        disease_class_id=linked.id,
        image_path="uploads/history.png",
        confidence_score=0.8,
    )
    db.session.add(record)
    db.session.commit()

    result = CliRunner().invoke(sync_maize_classes)
    assert result.exit_code == 0, result.output

    assert db.session.get(DiseaseClass, unlinked.id) is None
    preserved = db.session.get(DiseaseClass, linked.id)
    assert preserved is not None
    assert preserved.model_output_index is None
    assert db.session.get(PredictionRecord, record.id) is not None
    maize_classes = DiseaseClass.query.filter_by(crop_type="Maize").all()
    assert {disease.model_output_index for disease in maize_classes} == {0, 1, 2, 3}


def test_training_label_map_is_maize_only():
    from train_model import CLASS_NAMES, _leaf_group_id, _plant_target

    assert CLASS_NAMES == [
        "Healthy",
        "Maize Leaf Blight",
        "Maize Common Rust",
        "Maize Gray Leaf Spot",
        "Reject",
    ]
    assert _plant_target("Corn_(maize)___healthy") == 0
    assert _plant_target("Corn_(maize)___Cercospora_leaf_spot Gray_leaf_spot") == 3
    assert _plant_target("Tomato___healthy") == CLASS_NAMES.index("Reject")
    assert _plant_target("Corn_(maize)___unmapped_label") is None
    assert _leaf_group_id(
        "raw/color/Corn_(maize)___healthy/abc___R.S_HL 5498 copy 2.jpg",
        {},
    ) == "fallback_r.s_hl 5498"
    assert _leaf_group_id(
        "raw/color/Corn_(maize)___healthy/def___R.S_HL 5498 copy.jpg",
        {},
    ) == "fallback_r.s_hl 5498"


def test_researcher_surfaces_only_maize_classes(client, db):
    maize = DiseaseClass(
        name="Maize Gray Leaf Spot",
        crop_type="Maize",
        model_output_index=3,
    )
    historical = DiseaseClass(
        name="Tomato Early Blight",
        crop_type="Tomato",
        model_output_index=None,
    )
    researcher = User(
        full_name="Test Researcher",
        username="maizeonlyresearcher",
        email="maizeonlyresearcher@example.com",
        role=Role.RESEARCHER,
    )
    researcher.set_password("ResearchPass1")
    db.session.add_all([maize, historical, researcher])
    db.session.commit()
    client.post(
        "/auth/login",
        data={"username": researcher.username, "password": "ResearchPass1"},
    )

    library = client.get("/researcher/library")
    upload_form = client.get("/researcher/upload-training")

    assert b"Maize Gray Leaf Spot" in library.data
    assert b"Tomato Early Blight" not in library.data
    assert b"Maize Gray Leaf Spot" in upload_form.data
    assert b"Tomato Early Blight" not in upload_form.data
