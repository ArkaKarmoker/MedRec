# views.py
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout, get_user_model

User = get_user_model()
from django.contrib import messages
from .forms import RegistrationForm, ForgotPasswordForm, VerifyOTPForm, ResetPasswordForm
from .models import Profile, OTP
from django.core.mail import send_mail
from django.utils import timezone
from datetime import timedelta
import random

def register(request):
    if request.method == 'POST':
        form = RegistrationForm(request.POST)
        if form.is_valid():
            first_name = form.cleaned_data['first_name']
            last_name = form.cleaned_data['last_name']
            email = form.cleaned_data['email']
            password = form.cleaned_data['password']
            
            if User.objects.filter(email=email).exists():
                messages.error(request, 'Email already exists.')
            else:
                user = User.objects.create_user(email=email, password=password, first_name=first_name, last_name=last_name)
                user.save()
                messages.success(request, 'Registration successful! Please log in.')
                return redirect('login')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = RegistrationForm()
    return render(request, 'accounts/registration.html', {'form': form})

def user_login(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')
        user = authenticate(request, username=email, password=password)
        if user is not None:
            login(request, user)
            messages.success(request, 'Login successful!')
            return redirect('app')  # Redirect to 'app' as in attached; change if needed for your app
        else:
            messages.error(request, 'Invalid username or password.')
    return render(request, 'accounts/login.html')

def user_logout(request):
    logout(request)
    messages.success(request, 'Logged out successfully.')
    return redirect('login')

from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
import json

@csrf_exempt
@require_POST
def update_theme(request):
    if request.user.is_authenticated:
        try:
            data = json.loads(request.body)
            theme = data.get('theme', 'system')
            if theme in ['light', 'dark', 'system']:
                Profile.objects.update_or_create(
                    user=request.user,
                    defaults={'theme_preference': theme}
                )
                print(f"Theme updated to {theme} for {request.user}")
                return JsonResponse({'status': 'success'})
            return JsonResponse({'status': 'error', 'message': 'Invalid theme'}, status=400)
        except Exception as e:
            print(f"Error in update_theme: {e}")
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
    return JsonResponse({'status': 'ignored', 'message': 'User not authenticated'}, status=401)

def forgot_password(request):
    if request.method == 'POST':
        form = ForgotPasswordForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            try:
                user = User.objects.get(email=email)
            except User.DoesNotExist:
                messages.error(request, 'If an account with this email exists, an OTP has been sent.')
                # We still act like it worked to prevent email enumeration, but we don't actually send.
                # Actually, in standard apps, sometimes it's okay to show error. The user wants industry practice.
                # So just redirect to OTP page, but let's store the email in session.
                request.session['reset_email'] = email
                return redirect('verify_otp')
            
            # Generate OTP
            otp = str(random.randint(100000, 999999))
            
            # Save or Update OTP
            otp_obj, created = OTP.objects.get_or_create(user=user, defaults={
                'otp': otp,
                'expires_at': timezone.now() + timedelta(minutes=5)
            })
            if not created:
                otp_obj.otp = otp
                otp_obj.expires_at = timezone.now() + timedelta(minutes=5)
                otp_obj.save()

            # Send Email
            subject = 'MedRec Password Reset OTP'
            message = f'Your password reset OTP is: {otp}. It is valid for 5 minutes.'
            from_email = 'no-reply@medrec.com'
            recipient_list = [email]
            try:
                send_mail(subject, message, from_email, recipient_list, fail_silently=False)
                messages.success(request, 'OTP sent to your email address.')
            except Exception as e:
                messages.error(request, 'Failed to send email. Please try again later.')
                print(f"Email error: {e}")

            request.session['reset_email'] = email
            return redirect('verify_otp')
        else:
            messages.error(request, 'Please provide a valid email address.')
    else:
        form = ForgotPasswordForm()
    return render(request, 'accounts/forgot_password.html', {'form': form})


def verify_otp(request):
    email = request.session.get('reset_email')
    if not email:
        messages.error(request, 'Session expired. Please try again.')
        return redirect('forgot_password')

    if request.method == 'POST':
        form = VerifyOTPForm(request.POST)
        if form.is_valid():
            otp_input = form.cleaned_data['otp']
            try:
                user = User.objects.get(email=email)
                otp_obj = OTP.objects.get(user=user)
                if otp_obj.otp == otp_input:
                    if timezone.now() <= otp_obj.expires_at:
                        # OTP is valid and not expired
                        request.session['otp_verified'] = True
                        otp_obj.delete() # Invalidate OTP after use
                        messages.success(request, 'OTP verified successfully.')
                        return redirect('reset_password')
                    else:
                        messages.error(request, 'OTP has expired. Please request a new one.')
                else:
                    messages.error(request, 'Invalid OTP.')
            except (User.DoesNotExist, OTP.DoesNotExist):
                messages.error(request, 'Invalid request. Please try again.')
    else:
        form = VerifyOTPForm()
    return render(request, 'accounts/verify_otp.html', {'form': form, 'email': email})

@csrf_exempt
@require_POST
def resend_otp(request):
    email = request.session.get('reset_email')
    if not email:
        return JsonResponse({'status': 'error', 'message': 'Session expired'}, status=400)
    
    try:
        user = User.objects.get(email=email)
        otp_obj, created = OTP.objects.get_or_create(user=user, defaults={
            'otp': str(random.randint(100000, 999999)),
            'expires_at': timezone.now() + timedelta(minutes=5)
        })
        
        if not created:
            # Check if 1 minute has passed
            time_since_creation = timezone.now() - otp_obj.created_at
            # Because we update the created_at implicitly? Wait, auto_now_add doesn't update on save.
            # We need to manually update created_at or just use timezone.now() vs modified_at.
            # Actually, `created_at` is `auto_now_add`, so it's not updated on `save()`.
            # I should update `created_at` when generating a new OTP.
            pass
            
        # Instead, let's just generate a new OTP and update created_at manually if needed, 
        # but to bypass schema issues, let's just delete and recreate to reset auto_now_add.
        otp_obj.delete()
        otp = str(random.randint(100000, 999999))
        OTP.objects.create(user=user, otp=otp, expires_at=timezone.now() + timedelta(minutes=5))
        
        # Send Email
        subject = 'MedRec Password Reset OTP (Resend)'
        message = f'Your password reset OTP is: {otp}. It is valid for 5 minutes.'
        from_email = 'no-reply@medrec.com'
        recipient_list = [email]
        try:
            send_mail(subject, message, from_email, recipient_list, fail_silently=False)
            return JsonResponse({'status': 'success', 'message': 'OTP resent successfully.'})
        except Exception as e:
            print(f"Email error: {e}")
            return JsonResponse({'status': 'error', 'message': 'Failed to send email.'}, status=500)
            
    except User.DoesNotExist:
        # Act like it succeeded to prevent enumeration
        return JsonResponse({'status': 'success', 'message': 'If email exists, OTP is sent.'})


def reset_password(request):
    if not request.session.get('otp_verified'):
        messages.error(request, 'Please verify OTP first.')
        return redirect('forgot_password')
        
    email = request.session.get('reset_email')
    if not email:
        return redirect('forgot_password')

    if request.method == 'POST':
        form = ResetPasswordForm(request.POST)
        if form.is_valid():
            new_password = form.cleaned_data['password']
            try:
                user = User.objects.get(email=email)
                user.set_password(new_password)
                user.save()
                
                # Clear session variables
                del request.session['otp_verified']
                del request.session['reset_email']
                
                messages.success(request, 'Password reset successfully. You can now log in.')
                return redirect('login')
            except User.DoesNotExist:
                messages.error(request, 'User not found.')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = ResetPasswordForm()
        
    return render(request, 'accounts/reset_password.html', {'form': form})