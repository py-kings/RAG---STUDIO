"""
Document forms.
"""
from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileRequired, FileAllowed
from wtforms import StringField, SubmitField
from wtforms.validators import DataRequired, Length, Optional


class DocumentUploadForm(FlaskForm):
    title = StringField(
        "Title", validators=[Optional(), Length(max=255)],
        description="Leave blank to use the original filename.",
    )
    file = FileField(
        "Document",
        validators=[
            FileRequired(message="Please choose a file to upload."),
            FileAllowed(["pdf", "docx", "txt"], "Only PDF, DOCX, and TXT files are allowed."),
        ],
    )
    submit = SubmitField("Upload")
