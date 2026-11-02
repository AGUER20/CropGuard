-- Reference-only sample data (the same rows are inserted automatically,
-- in Python, by `flask --app run.py seed-demo-data` — see run.py).
USE cropguard_db;

INSERT INTO disease_classes (name, crop_type, description, model_output_index) VALUES
  ('Healthy', 'Maize', 'No visible disease symptoms on the leaf.', 0),
  ('Maize Leaf Blight', 'Maize', 'Northern leaf blight can cause long, cigar-shaped lesions on maize leaves.', 1),
  ('Maize Common Rust', 'Maize', 'Common rust may appear as raised reddish-brown pustules on maize leaves.', 2),
  ('Maize Gray Leaf Spot', 'Maize', 'Gray leaf spot may produce elongated rectangular lesions bounded by leaf veins.', 3);

INSERT INTO treatment_guides (disease_class_id, treatment_text, management_tips, prevention_tips) VALUES
  (2, 'Confirm symptoms with a local agricultural extension specialist before treatment.',
      'Scout fields and manage infected crop residue where locally recommended.',
      'Use locally adapted resistant varieties and follow local disease-management guidance.'),
  (3, 'Confirm symptoms with a local agricultural extension specialist before treatment.',
      'Monitor disease development and follow locally approved integrated pest-management guidance.',
      'Use locally adapted resistant varieties and consult local guidance on planting practices.'),
  (4, 'Confirm symptoms with a local agricultural extension specialist before treatment.',
      'Manage crop residue and rotation according to local agronomic recommendations.',
      'Use locally adapted resistant varieties and follow local disease-management guidance.');
