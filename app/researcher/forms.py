from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileRequired, FileAllowed
from wtforms import SelectField, SubmitField
from wtforms.validators import DataRequired


class TrainingImageForm(FlaskForm):
    disease_class_id = SelectField("Disease class", coerce=int, validators=[DataRequired()])
    image = FileField(
        "Training image",
        validators=[FileRequired(), FileAllowed(["jpg", "jpeg", "png"], "Only JPG/PNG images are allowed.")],
    )
    submit = SubmitField("Upload training image")
