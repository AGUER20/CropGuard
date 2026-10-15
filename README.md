# CropGuard — Web-Enabled Plant Disease Detection System

A full-stack implementation of the CropGuard system described in the project
proposal: a Flask (Python) web application that uses a fine-tuned
**MobileNetV2** CNN to diagnose plant leaf diseases from a photo and deliver
treatment advice, with role-based dashboards for **farmers**, **researchers /
agricultural officers**, and **administrators**.

Stack: **Python (Flask)** backend · **Jinja2 + Bootstrap 5 + JavaScript**
frontend · **MySQL** database (via SQLAlchemy) · **bcrypt** password hashing.

---

## 1. Architecture

MVC pattern, matching proposal section 3.8:

- **View** — Jinja2 templates in `app/templates/`, styled with Bootstrap 5 +
  a custom CropGuard theme (`app/static/css/style.css`) and hand-drawn SVG
  illustrations (`app/static/img/`).
- **Controller** — Flask blueprints, one per module: `app/auth`,
  `app/farmer`, `app/researcher`, `app/admin`.
- **Model** — SQLAlchemy models in `app/models.py` (`User`, `DiseaseClass`,
  `TreatmentGuide`, `PredictionRecord`, `Feedback`, `TrainingImage`), backed
  by MySQL. `database/schema.sql` has the equivalent raw SQL DDL.
- **ML pipeline** — `app/ml/preprocessing.py` (resize/normalise) and
  `app/ml/inference.py` (MobileNetV2 loading + prediction, with a
  deterministic demo fallback — see §5).

```
cropguard/
├── app/
│   ├── auth/            login, register (bcrypt hashing)
│   ├── farmer/           upload → diagnose → treatment advice → feedback
│   ├── researcher/       disease library, trends, training-image upload
│   ├── admin/             user management, reports (+ CSV export)
│   ├── ml/                preprocessing.py, inference.py
│   ├── utils/             role_required decorator
│   ├── models.py, extensions.py, config.py, __init__.py
│   ├── static/            css/, js/, img/ (SVG illustrations), uploads/
│   └── templates/
├── database/schema.sql, seed.sql
├── model/                 drop your trained .h5 + class_indices.json here
├── tests/                 pytest unit + integration tests
├── run.py                 entry point + CLI bootstrap commands
├── requirements.txt
└── .env.example
```

---

## 2. Setup in VS Code

1. **Open the folder** `cropguard/` in VS Code, and open a terminal
   (`` Ctrl+` ``).

2. **Create and activate a virtual environment:**
   ```bash
   python -m venv venv
   # Windows:
   venv\Scripts\activate
   # macOS / Linux:
   source venv/bin/activate
   ```
   Select this interpreter in VS Code: `Ctrl+Shift+P` → *Python: Select
   Interpreter* → pick `./venv`.

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```
   > `tensorflow` is the heaviest package here. If you only want to explore
   > the app before training a model, you can skip it for now — see §5, the
   > app runs fine without it until you load a real `.h5` model.

4. **Create the MySQL database:**
   ```sql
   CREATE DATABASE cropguard_db CHARACTER SET utf8mb4;
   ```
   (or let `flask init-db` create the tables for you once `.env` points at
   an existing empty database — see next step.)

5. **Configure environment variables:**
   ```bash
   cp .env.example .env
   ```
   Edit `.env` and set `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_NAME` to
   match your local MySQL install, and set `SECRET_KEY` to a random string.

6. **Initialise and seed the database:**
   ```bash
   flask --app run.py init-db
   flask --app run.py seed-demo-data
   ```
   This creates all tables and inserts 6 sample disease classes with
   treatment guides, plus one demo account per role:

   | Role | Username | Password |
   |---|---|---|
   | Farmer | `farmer1` | `Farmer123!` |
   | Researcher | `researcher1` | `Research123!` |
   | Admin | `admin1` | `Admin123!` |

7. **Run the app:**
   ```bash
   flask --app run.py run --debug
   ```
   Open **http://127.0.0.1:5000**.

---

## 3. Running tests

```bash
pytest
```
Covers the image preprocessing pipeline (resize/normalise output shape and
value range) and the auth flow (password hashing, invalid vs. valid login),
per the unit/integration testing plan in proposal §3.6.

---

## 4. Where the design diagrams map to code

| Diagram element (proposal §3.4 / the sequence diagrams) | Implementation |
|---|---|
| Login `alt` [invalid → try again] / [valid → login successful] | `app/auth/routes.py::login()` |
| Farmer: upload photo → preprocess → model → diagnosis → treatment guide | `app/farmer/routes.py::diagnose()` |
| Feedback loop | `app/farmer/routes.py::submit_feedback()`, `Feedback` model |
| Researcher elevated login (approval-gated) | `is_approved` flag + `role_required()` |
| Researcher: browse library / monitor trends / upload training images | `app/researcher/routes.py` |
| Admin: manage user accounts | `app/admin/routes.py::users/approve_user/toggle_active/delete_user` |
| Admin: generate / view report | `app/admin/routes.py::reports/export_report_csv` |
| ERD entities: User, DiseaseClass, PredictionRecord, TreatmentGuide | `app/models.py`, `database/schema.sql` |

---

## 5. Plugging in the real MobileNetV2 model

The app is fully runnable **without** a trained model: if
`model/mobilenetv2_cropguard.h5` doesn't exist, `app/ml/inference.py`
transparently uses a deterministic demo predictor (same photo → same
result) so every screen, route, and database table can be exercised while
the model is still being trained (Spiral 2/3 of the methodology).

To train the supported diagnoses and an explicit reject class, run:

```bash
python train_model.py --epochs 8 --batch-size 32 --max-per-class 1500
```

The first run fetches the selected PlantVillage images with HTTP range reads,
plus the public Beans and CIFAR-10 datasets. PlantVillage leaves are grouped
before the 75/12.5/12.5 train/validation/test split to avoid the same leaf
appearing in multiple sets. Beans supplies angular leaf spot; unsupported
apple scab, potato blights, tomato leaf mold, and CIFAR-10 objects are trained
as `Reject`. The default cap
keeps CPU training manageable; pass `--max-per-class 0` to use every
available image. ImageNet-pretrained MobileNetV2 uses augmentation, class
weights, early stopping, and best-checkpoint saving. The script prints test
accuracy, per-class precision/recall, and a confusion matrix. Trained weights
and class mapping are written to the paths configured in `.env`
(`MODEL_PATH` and `CLASS_INDEX_PATH`). These artifacts are ignored by Git,
so train them locally after cloning.

The app rejects the model's `Reject` class instead of saving a diagnosis.
The existing image-content screen is an additional guard; neither it nor a
closed-set classifier can guarantee rejection of every possible out-of-
distribution image, so review test-set metrics before relying on diagnoses.

To use an independently trained compatible model instead:

1. Train/fine-tune MobileNetV2 (TensorFlow/Keras) on your labelled dataset.
2. Save the model: `model.save("model/mobilenetv2_cropguard.h5")`.
3. Save the label mapping so predictions map back to `DiseaseClass` rows:
   ```python
   import json
   inv_map = {v: k for k, v in train_generator.class_indices.items()}
   json.dump(inv_map, open("model/class_indices.json", "w"))
   ```
   Make sure each name matches a `DiseaseClass.name` in the database (and
   that `model_output_index` lines up), or add missing rows via the
   researcher's disease library workflow.
4. Restart the app — `is_using_demo_model()` will now return `False`, and
   the "Demo prediction mode" banner on the result page disappears
   automatically.

---

The sequence diagram used to guide this build is included in
`docs/diagrams/` (`.svg` and editable `.drawio`).

---

## 6. Security notes

- Passwords are hashed with **bcrypt** (`Flask-Bcrypt`) — never stored or
  logged in plain text.
- CSRF protection is enabled on every form via **Flask-WTF**.
- Role-based access control (`app/utils/decorators.py::role_required`)
  gates every farmer/researcher/admin route; researcher accounts also
  require explicit admin approval before elevated routes unlock.
- File uploads are restricted to `.jpg/.jpeg/.png`, capped at 8 MB, and
  saved under a randomised filename (`uuid4`) to avoid collisions/overwrite
  attacks.
