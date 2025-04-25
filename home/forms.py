from django import forms
from django.core.validators import RegexValidator

class ContactForm(forms.Form):
    name = forms.CharField(
        max_length=100,
        required=True,
        validators=[
            RegexValidator(
                regex='^[a-zA-Z\s]*$',
                message='Name should contain only alphabets and spaces.',
                code='invalid_name'
            )
        ],
        widget=forms.TextInput(attrs={
            'placeholder': 'Your Name',
            'class': 'form-control',
            'style': 'height: 50px; font-size: 16px;'
        })
    )

    # Email field
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={
            'placeholder': 'Your Email',
            'class': 'form-control',
            'style': 'height: 50px; font-size: 16px;'
        })
    )

    # Subject field
    subject = forms.CharField(
        max_length=200,
        required=True,
        widget=forms.TextInput(attrs={
            'placeholder': 'Subject',
            'class': 'form-control',
            'style': 'height: 50px; font-size: 16px;'
        })
    )

    # Message field with minimum length validation
    message = forms.CharField(
        widget=forms.Textarea(attrs={
            'placeholder': 'Your Message',
            'class': 'form-control',
            'style': 'font-size: 16px;',
            'rows': 6 
        }),
        required=True,
        min_length=10,
        error_messages={
            'min_length': 'Message must be at least 10 characters long.'
        }
    )

    # Custom clean method for additional validation
    def clean(self):
        cleaned_data = super().clean()
        name = cleaned_data.get('name')
        message = cleaned_data.get('message')

        if name and name.lower() == 'admin':
            self.add_error('name', 'Name cannot be "Admin".')

        forbidden_words = ['spam', 'advertisement']
        if message:
            for word in forbidden_words:
                if word in message.lower():
                    self.add_error('message', f'Message contains forbidden word: {word}.')

        return cleaned_data
