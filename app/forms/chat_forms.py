"""
Chat/assistant forms.
"""
from flask_wtf import FlaskForm
from wtforms import TextAreaField, SubmitField
from wtforms.validators import DataRequired, Length


class AskForm(FlaskForm):
    question = TextAreaField(
        "Ask a question",
        validators=[DataRequired(), Length(min=3, max=2000)],
        render_kw={"rows": 3, "placeholder": "e.g. What is the leave policy?"},
    )
    submit = SubmitField("Ask")
