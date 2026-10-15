import io

import pytest
from PIL import Image, ImageDraw

from app.models import PredictionRecord, Role, User


def test_non_leaf_upload_never_creates_diagnosis(app, client, db, tmp_path, monkeypatch):
    upload_dir = tmp_path / "uploads"
    upload_dir.mkdir()
    app.config["UPLOAD_FOLDER"] = str(upload_dir)

    farmer = User(
        full_name="Test Farmer",
        username="uploadfarmer",
        email="uploadfarmer@example.com",
        role=Role.FARMER,
    )
    farmer.set_password("FarmerPass1")
    db.session.add(farmer)
    db.session.commit()

    login = client.post(
        "/auth/login",
        data={"username": "uploadfarmer", "password": "FarmerPass1"},
        follow_redirects=True,
    )
    assert login.status_code == 200

    def fail_inference(*args, **kwargs):
        pytest.fail("Inference must not run for a non-leaf upload.")

    monkeypatch.setattr("app.farmer.routes.ml_inference.predict", fail_inference)

    car = Image.new("RGB", (224, 224), color=(30, 105, 40))
    ImageDraw.Draw(car).rectangle((35, 65, 189, 175), fill=(35, 38, 42))
    image_bytes = io.BytesIO()
    car.save(image_bytes, format="PNG")
    image_bytes.seek(0)

    response = client.post(
        "/farmer/diagnose",
        data={"leaf_image": (image_bytes, "car.png")},
        content_type="multipart/form-data",
        follow_redirects=True,
    )

    assert b"Upload a clear, close-up photo of a plant leaf" in response.data
    assert PredictionRecord.query.count() == 0
    assert list(upload_dir.iterdir()) == []