from django.shortcuts import render,HttpResponse,redirect
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.views.decorators.cache import never_cache
from django.db.models import Q
from django.contrib import messages
from datetime import datetime, timedelta,timezone
from django.core.mail import send_mail
from django.utils import timezone as django_timezone
import random
import re
from django.http import JsonResponse
import secrets
from user_profile.models import Referral
from wallet.models import Wallet, WalletTransaction


"""
GENERATE 4 DIGIT OTP
"""
def generate_otp():
    return str(secrets.randbelow(10000)).zfill(4)





"""
SEND OTP TO EMAIL ACCOUNT
"""

def send_otp_email(email, otp):
    subject = "Your OTP Code"
    message = f"Your OTP Code is: {otp}"
    try:
        send_mail(subject, message, "your_gmail.com", [email])
        return True
    except Exception as e:
        print(f"Error sending email: {e}")
        return False





"""
PASSWORD VALIDATION
"""
def validate_password(password):
    if len(password) < 8:
        return False, "Password must be at least 8 characters long."
    if not re.search(r"[A-Z]", password):
        return False, "Password must contain at least one uppercase letter."
    if not re.search(r"[a-z]", password):
        return False, "Password must contain at least one lowercase letter."
    if not re.search(r"\d", password):
        return False, "Password must contain at least one number."
    if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
        return False, "Password must contain at least one special character."
    return True, ""





"""
USER LOGIN
"""
@never_cache
def LoginPage(request):
    if request.user.is_authenticated:
        return redirect('home')
    

    form_data = {} 
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')
        form_data['email'] = email



        if not email or not password:
            messages.error(request, 'Please enter both email and password.')
            return render(request, 'login.html', {'form_data': form_data})

        user=authenticate(request, username=email, password=password)

        if user is not None:
            login(request, user)
            return redirect('home') # Redirect to homepage 
        else:
            messages.error(request, "Invalid email or password")
            return render(request, 'login.html', {'form_data': form_data})


    return render(request,  'login.html' , {'form_data': form_data})






"""
USER SIGN UP/ REGISTRATION
"""
@never_cache
def SignupPage(request):
    if request.user.is_authenticated:
        return redirect('home')
    
    
    form_data={}
    if request.method == 'POST':
        username= request.POST.get('username').strip()
        first_name=request.POST.get('first_name').strip()
        last_name = request.POST.get('last_name').strip()
        email = request.POST.get('email').strip()
        password = request.POST.get('password')
        confirm_password = request.POST.get('confirm_password')
        referral_code =request.POST.get('referral_code', '').strip()
        form_data= {
            'username':username,
            'first_name': first_name,
            'last_name': last_name,
            'email': email,
            'referral_code': referral_code,
        }

        errors= {}

        #Check if the username or email already exists
        if User.objects.filter(username=username).exists():
            errors['username'] = "Username already exists. Please choose a different one."
        if User.objects.filter(email=email).exists():
            errors['email']= "Email is already registered. Please use a different email."
        if password != confirm_password:
            errors['password'] = "password do not match"


        if errors:
            for error in errors.values():
                messages.error(request,error)
            return render(request, 'signup.html', {'form_data': form_data})
        
        #validate referral code
        referred_by = None
        if referral_code:
            try:
                referral = Referral.objects.get(referral_code=referral_code)
                referred_by = referral.user
            except Referral.DoesNotExist:
                messages.error(request, "Invalid referral code.")
                return render(request, 'register.html', {'form_data': form_data})
            

        

        otp = generate_otp()
        expires_at = django_timezone.now() + timedelta(minutes=1)


        #store OTP and user information in session
        request.session['otp'] = otp
        request.session['otp_expires_at'] = int(expires_at.timestamp())
        request.session['username'] = username
        request.session['email'] = email 
        request.session['password'] = password
        request.session['first_name'] = first_name
        request.session['last_name'] = last_name
        request.session['referral_code'] = referral_code   #Store referral code in session

        if not send_otp_email(email, otp):
            messages.error(request, "Failed to send OTP email. Please try again.")
            return render(request, 'signup.html', {'form_data': form_data})
        
        return redirect('verify_otp')
 
        
    return render(request, 'signup.html', {'form_data': form_data})







"""
OTP VERIFICATION
"""

def verify_otp(request):

    email = request.session.get('email')

    if request.method == 'POST':
        entered_otp = request.POST.get('otp')
        otp = request.session.get('otp')
        otp_expires_at = request.session.get('otp_expires_at') 


        if not otp:
            return render(request, 'verify_otp.html', {'error': 'OTP not found.', 'email':email})


        try:
            otp_expires_at = datetime.fromtimestamp(otp_expires_at, tz=timezone.utc)
        except ValueError:
            return render(request, 'verify_otp.html', {'error':'Invalid OTP expiration format.', 'email':email})


        if django_timezone.now() > otp_expires_at:
            return render(request, 'verify_otp.html', {'error': 'OTP has expired.', 'email': email})


        if str(otp) == entered_otp:
            #proceed with registration
            username = request.session['username']
            password = request.session['password']
            first_name = request.session['first_name']
            last_name = first_name = request.session['last_name']
            referral_code = request.session.get('referral_code')  # Get referral code from session


            user = User.objects.create_user(

                username=email,
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name,
                
                                              
            )

            # Create a referral entry for the new user
            Referral.objects.create(user=user)

            # Credit ₹50 to the new user's wallet
            wallet, _ = Wallet.objects.get_or_create(user=user)
            #WalletTransaction.objects.create()

            # Handle referral code
            if referral_code:
                try:
                    referral = Referral.objects.get(referral_code=referral_code)
                    referred_by = referral.user
                    Referral.objects.filter(user=user).update(referred_by=referred_by)

                    # wallet, _ = Wallet.objects.get_or_create(user=user)
                    wallet.balance += 50
                    wallet.save()
                    WalletTransaction.objects.create(
                        wallet=wallet,
                        amount=50,
                        transaction_type='credit',
                        description='Referral bonus for new user'
                    )

                    # Credit ₹100 to the referred user's wallet
                    referred_wallet, _ = Wallet.objects.get_or_create(user=referred_by)
                    referred_wallet.balance += 100
                    referred_wallet.save()
                    WalletTransaction.objects.create(
                        wallet=referred_wallet,
                        amount=100,
                        transaction_type='credit',
                        description='Referral bonus for referring user'
                    )
                except Referral.DoesNotExist:
                    pass 




            #clear session data
            for key in ['otp', 'otp_expires_at', 'username', 'email', 'password', 'first_name', 'last_name', 'referral_code']:
                request.session.pop(key, None)



            #Log in the user
            user.backend = 'django.contrib.auth.backends,ModelBackend' #Use the appropriate backend
            login(request, user)
            return redirect('home')
        else:
            return render(request, 'verify_otp.html', {'error': 'Invalid OTP. Please try again.', 'email':email})


    return render(request, 'verify_otp.html', {'email':email})



"""
RESEND OTP
"""

def resend_otp(request):
    if request.method == 'POST':
        otp = request.session.get('otp')
        otp_expires_at = request.session.get('otp_expires_at')

        # Check if the OTP is still valid
        if otp and django_timezone.now() < django_timezone.make_aware(datetime.fromtimestamp(otp_expires_at)):
            # Calculate time remaining for the OTP to expire
            time_remaining = (django_timezone.make_aware(datetime.fromtimestamp(otp_expires_at)) - django_timezone.now()).seconds
            return JsonResponse({'success': False, 'message': f"Please wait {time_remaining} seconds before requesting a new OTP."})

        # Send new OTP if expired or not present
        new_otp = generate_otp()
        expires_at = django_timezone.now() + timedelta(minutes=1)
        request.session['otp'] = new_otp
        request.session['otp_expires_at'] = int(expires_at.timestamp())  

        if send_otp_email(request.session['email'], new_otp):
            return JsonResponse({'success': True, 'message': 'New OTP sent successfully!'})
        else:
            return JsonResponse({'success': False, 'message': 'Failed to send OTP. Please try again.'})
    





    
def ForgotPassword(request):
    if request.method == 'POST':
        email = request.POST.get('email')


        # Initialize OTP attempt count if not already set
        if 'otp_attempts' not in request.session:
            request.session['otp_attempts'] = 0

        otp_attempts = request.session.get('otp_attempts', 0)


        if otp_attempts >= 3:
            messages.error(request, "You have exceeded the maximum number of OTP attempts. Please try again later.")
            return render(request, 'forgot_password.html')


        try:
            user = User.objects.get(email=email)
            otp = generate_otp()
            expires_at = django_timezone.now() + timedelta(minutes=3)


             # Store OTP and expiry as timestamps in session
            request.session['password_reset_otp'] = otp
            request.session['password_reset_expires_at'] = int(expires_at.timestamp())
            request.session['reset_email'] = email  #Store email in session

            # Reset OTP attempts since the user requested a new OTP
            request.session['otp_attempts'] = 0
            request.session.modified = True



            if send_otp_email(email, otp):
                messages.success(request, 'OTP sent successfully to your email.')
                return redirect('verify_forgot_password_otp')
            else:
                messages.error(request, 'Failed to send OTP. Please try again.')
        except User.DoesNotExist:
            messages.error(request, 'Email not Found.')
            return render(request, 'forgot_password.html', {'email': email})
        

    return render(request,'forgot_password.html')





"""
VERIFY FORGOT PASSWORD OTP
"""
def verify_forgot_password_otp(request):
    if request.method == 'POST':
        entered_otp = request.POST.get('otp')

        otp = request.session.get('password_reset_otp')
        otp_expires_at = request.session.get('password_reset_expires_at')
        attempts = request.session.get('otp_attemps', 0)


        if not otp or not otp_expires_at:
            messages.error(request, 'OTP not found or expired.')
            return redirect('forgot_password')

        try:
            otp_expires_at = datetime.fromtimestamp(otp_expires_at, tz=timezone.utc)
        except ValueError:
            messages.error(request, 'Invalid OTP expiration format.')
            return redirect('forgot_password')

        if django_timezone.now() > otp_expires_at:
            messages.error(request, 'OTP has expired')
            return redirect('forgot_password')


        if attempts >= 3:
            messages.error(request, 'Too many incorrect attempts. Please request a new OTP.')
            return redirect('forgot_password')

        if str(otp) == entered_otp:
            messages.success(request, 'OTP verified Successfully')

            # Clear OTP and attempts from session
            del request.session['password_reset_otp']
            del request.session['password_reset_expires_at']
            request.session.pop('otp_attempts', None)

            return redirect('reset_password')

        else:
            request.session['otp_attempts'] = attempts + 1
            messages.error(request, f"Invalid OTP. Attempt {attempts + 1} of 3..")
            return redirect('verify_forgot_password_otp')   


    return render(request,'verify_forgot_password_otp.html')





def reset_password(request):
    if request.method == 'POST':
        new_password = request.POST.get('new_password')
        confirm_password = request.POST.get('confirm_password')

        if not new_password or not confirm_password:
            messages.error(request, 'Please fill in all Fields')
            return redirect('reset_password')


        if new_password != confirm_password:
            messages.error(request, 'Passwords do not match.')
            return redirect('reset_password')


        email = request.session.get('reset_email')

        if not email:
            messages.error(request, 'Session expired. Please request a new password reset.')
            return redirect('ForgotPassword')


        try:
            user = User.objects.get(email=email)
            user.set_password(new_password)
            user.save()

            # Clear session data for security   
            del request.session['reset_email']


            messages.success(request, 'Password reset successfully. Please log in.')
            return redirect('login')

        except User.DoesNotExist:
            messages.error(request, 'User not found. Please try again.')
            return redirect('forgot_password')     


    return render(request,'reset_password.html')







#Logout
@never_cache
def User_Logout(request):
    logout(request)
    return redirect('login')









