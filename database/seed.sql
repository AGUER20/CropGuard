-- Reference-only sample data (the same rows are inserted automatically,
-- in Python, by `flask --app run.py seed-demo-data` — see run.py).
USE cropguard_db;

INSERT INTO disease_classes (name, crop_type, description, model_output_index) VALUES
  ('Healthy', 'Maize', 'No visible disease symptoms.', 0),
  ('Maize Leaf Blight', 'Maize', 'Long, cigar-shaped grey-green lesions on leaves.', 1),
  ('Maize Common Rust', 'Maize', 'Small, reddish-brown pustules scattered on both leaf surfaces.', 2),
  ('Tomato Early Blight', 'Tomato', 'Dark concentric-ringed spots, usually on older leaves first.', 3),
  ('Tomato Late Blight', 'Tomato', 'Water-soaked lesions that turn brown/black and spread rapidly.', 4),
  ('Bean Angular Leaf Spot', 'Bean', 'Angular, brown lesions bound by leaf veins.', 5);

INSERT INTO treatment_guides (disease_class_id, treatment_text, management_tips, prevention_tips) VALUES
  (2, 'Apply a registered fungicide (e.g. strobilurin-based) at early symptom onset; remove and destroy heavily infected leaves.',
      'Rotate maize with a non-host crop for at least one season.',
      'Use resistant maize varieties and avoid overhead irrigation late in the day.'),
  (3, 'Apply a triazole or strobilurin fungicide when pustules first appear on the lower canopy.',
      'Scout fields weekly during humid periods.',
      'Plant rust-tolerant hybrids and ensure adequate plant spacing for airflow.'),
  (4, 'Remove infected lower leaves and apply a chlorothalonil-based fungicide on a 7-10 day schedule.',
      'Stake plants to improve airflow and reduce leaf-to-soil contact.',
      'Mulch around the base of plants and avoid wetting foliage when watering.'),
  (5, 'Apply a copper-based or systemic fungicide immediately; destroy severely infected plants.',
      'Increase spacing between rows to reduce humidity around the canopy.',
      'Use certified disease-free seed and avoid working in wet fields.'),
  (6, 'Apply a copper-based bactericide/fungicide at first sign of angular lesions.',
      'Avoid overhead irrigation and working fields when leaves are wet.',
      'Rotate with non-legume crops and use certified clean seed.');
