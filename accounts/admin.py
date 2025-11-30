from django.contrib import admin
from .models import Profile  # Import your Profile model

# Register the Profile model with the admin site
admin.site.register(Profile)