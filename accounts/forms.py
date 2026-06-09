# forms.py
from django import forms
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model

User = get_user_model()

# Input widget attributes (updated to Bootstrap classes)
INPUT_FIELD_ATTRS = {
    'class': 'form-control'
}

# Custom registration form (directly adapted from attached RegistrationForm)
class RegistrationForm(forms.Form):
    first_name = forms.CharField(max_length=255, widget=forms.TextInput(attrs={**INPUT_FIELD_ATTRS, 'placeholder': 'First Name'}))
    last_name = forms.CharField(max_length=255, widget=forms.TextInput(attrs={**INPUT_FIELD_ATTRS, 'placeholder': 'Last Name'}))
    email = forms.EmailField(widget=forms.EmailInput(attrs={**INPUT_FIELD_ATTRS, 'placeholder': 'Email'}))
    password = forms.CharField(widget=forms.PasswordInput(attrs={**INPUT_FIELD_ATTRS, 'placeholder': 'Password'}))
    password_confirm = forms.CharField(widget=forms.PasswordInput(attrs={**INPUT_FIELD_ATTRS, 'placeholder': 'Confirm Password'}))

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        password_confirm = cleaned_data.get('password_confirm')
        if password and password_confirm and password != password_confirm:
            raise ValidationError("Passwords do not match.")
        return cleaned_data