-- ============================================================================
-- CropGuard — MySQL schema (mirrors app/models.py / the proposal's ERD:
-- User, DiseaseClass, PredictionRecord, TreatmentGuide, plus Feedback and
-- TrainingImage which support the researcher/admin workflows).
--
-- You normally do NOT need to run this by hand: `flask --app run.py
-- init-db` (see run.py) creates these tables from the SQLAlchemy models.
-- This file is provided so the raw SQL structure can be inspected,
-- reviewed, or imported directly if you prefer that workflow.
-- ============================================================================

CREATE DATABASE IF NOT EXISTS cropguard_db
  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE cropguard_db;

CREATE TABLE IF NOT EXISTS users (
  id                INT AUTO_INCREMENT PRIMARY KEY,
  full_name         VARCHAR(120)  NOT NULL,
  username          VARCHAR(60)   NOT NULL UNIQUE,
  email             VARCHAR(150)  NOT NULL UNIQUE,
  password_hash     VARCHAR(255)  NOT NULL,
  role              ENUM('farmer', 'researcher', 'admin') NOT NULL DEFAULT 'farmer',
  is_approved       BOOLEAN       NOT NULL DEFAULT TRUE,
  is_active_account BOOLEAN       NOT NULL DEFAULT TRUE,
  created_at        DATETIME      DEFAULT CURRENT_TIMESTAMP,
  last_login_at     DATETIME      NULL
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS disease_classes (
  id                  INT AUTO_INCREMENT PRIMARY KEY,
  name                VARCHAR(120) NOT NULL UNIQUE,
  crop_type           VARCHAR(80)  NOT NULL,
  description         TEXT         NULL,
  sample_image_path   VARCHAR(255) NULL,
  model_output_index  INT          NULL UNIQUE
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS treatment_guides (
  id                INT AUTO_INCREMENT PRIMARY KEY,
  disease_class_id  INT NOT NULL UNIQUE,
  treatment_text    TEXT NOT NULL,
  management_tips   TEXT NULL,
  prevention_tips   TEXT NULL,
  updated_at        DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  FOREIGN KEY (disease_class_id) REFERENCES disease_classes(id) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS prediction_records (
  id                 INT AUTO_INCREMENT PRIMARY KEY,
  user_id            INT NOT NULL,
  disease_class_id   INT NULL,
  image_path         VARCHAR(255) NOT NULL,
  confidence_score   FLOAT NOT NULL,
  predicted_at       DATETIME DEFAULT CURRENT_TIMESTAMP,
  inference_ms       INT NULL,
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
  FOREIGN KEY (disease_class_id) REFERENCES disease_classes(id) ON DELETE SET NULL,
  INDEX idx_predicted_at (predicted_at)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS feedback (
  id                    INT AUTO_INCREMENT PRIMARY KEY,
  prediction_id         INT NOT NULL UNIQUE,
  user_id               INT NOT NULL,
  rating                TINYINT NOT NULL CHECK (rating BETWEEN 1 AND 5),
  is_flagged_incorrect  BOOLEAN DEFAULT FALSE,
  comment               TEXT NULL,
  created_at            DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (prediction_id) REFERENCES prediction_records(id) ON DELETE CASCADE,
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS training_images (
  id                INT AUTO_INCREMENT PRIMARY KEY,
  disease_class_id  INT NOT NULL,
  uploaded_by_id    INT NOT NULL,
  image_path        VARCHAR(255) NOT NULL,
  status            ENUM('pending', 'approved', 'rejected') DEFAULT 'pending',
  uploaded_at       DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (disease_class_id) REFERENCES disease_classes(id) ON DELETE CASCADE,
  FOREIGN KEY (uploaded_by_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB;
