from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileRequired, FileAllowed
from wtforms import IntegerField, TextAreaField, SubmitField, HiddenField
from wtforms.validators import DataRequired, NumberRange, Optional, Length


class DiagnoseForm(FlaskForm):
    leaf_image = FileField(
        "Leaf photo",
        validators=[FileRequired(message="Please choose or capture a photo."),
                    FileAllowed(["jpg", "jpeg", "png"], "Only JPG/PNG images are allowed.")],
    )
    submit = SubmitField("Diagnose leaf")


class FeedbackForm(FlaskForm):
    prediction_id = HiddenField()
    rating = IntegerField("Rating (1-5)", validators=[DataRequired(), NumberRange(min=1, max=5)])
    comment = TextAreaField("Comments (optional)", validators=[Optional(), Length(max=1000)])
    submit = SubmitField("Submit feedback")
