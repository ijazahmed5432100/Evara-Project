from django.shortcuts import render,redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from .models import Address,ShippingAddress,Profile
from django.contrib import messages
import re
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth import authenticate
from django.core.mail import send_mail
from django.conf import settings
import random
import string
from django.contrib.auth.models import User
from django.http import JsonResponse
from django.views.decorators.http import require_POST




# Create your views here.






@login_required
def user_profile(request):
    if request.method == 'POST':
        # Get form data
        username = request.POST.get('username')
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        
        # Check if username is already taken
        if User.objects.exclude(pk=request.user.pk).filter(username=username).exists():
            messages.error(request, 'This username is already taken.')
            return redirect('user_profile')
        
        # Update user information
        user = request.user
        user.username = username
        user.first_name = first_name
        user.last_name = last_name
        user.save()
        
        messages.success(request, 'Profile updated successfully!')
        return redirect('user_profile')

    addresses = Address.objects.filter(user=request.user, is_deleted=False)
    context = {
        'addresses': addresses
    }
    return render(request, 'user/profile.html', context)














@login_required
@require_POST
def update_profile_picture(request):
    try:
        if request.FILES.get('avatar'):
            # Get or create profile
            profile, created = Profile.objects.get_or_create(user=request.user)
            
            # Delete old avatar if it exists
            if profile.avatar:
                profile.avatar.delete(save=False)
            
            # Save new avatar
            profile.avatar = request.FILES['avatar']
            profile.save()
            
            return JsonResponse({'success': True})
        return JsonResponse({'success': False, 'error': 'No image provided'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)











"""
VIEW ADDRESS PAGE
"""
@login_required
def view_addresses(request):
    addresses = Address.objects.filter(user=request.user, is_deleted = False)

    # If no address is marked as default, set the oldest address as default
    if not addresses.filter(is_default=True).exists() and addresses.exists():
        oldest_address = addresses.order_by('id').first()
        oldest_address.is_default = True
        oldest_address.save()


    return render(request, 'user/address.html', {'addresses':addresses})






"""
DEFAULT ADDRESS SETTING
"""
@login_required
def set_default_address(request, address_id):
    address = get_object_or_404(Address, id=address_id, user=request.user)

    # Set the selected address as default
    address.is_default = True
    address.save()

    messages.success(request, "Default address updated successfully")
    
    return redirect('addresses')




"""
NEW ADDRESS ADDING
"""
@login_required
def add_address(request):
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        address = request.POST.get('address', '').strip()
        city = request.POST.get('city', '').strip()
        state = request.POST.get('state', '').strip()
        country = request.POST.get('country', '').strip()
        postcode = request.POST.get('postcode', '').strip()
        phone = request.POST.get('phone', '').strip()

        errors = []
        if not all([name, address, city, state ,country, postcode, phone]):
            errors.append("All fields except addutional info are required.")
        if not postcode.isdigit():
            errors.append('Postcode must be numeric. ')
        phone_regex = re.compile(r'^\+?[1-9]\d{1,14}$')    
        if not phone_regex.match(phone):
            errors.append("Invalid phone number format.")

        # Check if the address already exists for the user
        if Address.objects.filter(
            user=request.user,
            name=name,
            address=address,
            city=city,
            state=state,
            country=country,
            postcode=postcode,
            phone=phone
        ).exists():
            errors.append("This address already exists.")

        if errors:
            return render(request, 'user/add_address.html',{
                'errors':errors,
                'data': {
                    'name': name,
                        'address': address,
                        'city': city,
                        'state': state,
                        'country': country,
                        'postcode': postcode,
                        'phone': phone,
                    },
                },
            ) 


        Address.objects.create(
            user=request.user,
            name=name,
            address=address,
            city=city,
            state=state,
            country=country,
            postcode=postcode,
            phone=phone,
        ) 
        messages.success(request, 'Address added successfully!')
        return redirect('addresses')  
                
    return render(request, 'user/add_address.html')







"""
EDIT ALREADY HAVING ADDRESS
"""
@login_required
def edit_address(request, address_id):
    address = get_object_or_404(Address, id=address_id, user=request.user)

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        address_line = request.POST.get('address', '').strip()
        city = request.POST.get('city', '').strip()
        state = request.POST.get('state', '').strip()
        country = request.POST.get('country', '').strip()
        postcode = request.POST.get('postcode', '').strip()
        phone = request.POST.get('phone', '').strip()

        errors = []
        if not all([name, address_line, city, state, country, postcode, phone]):
            errors.append("All fields are required.")
        if not postcode.isdigit():
            errors.append("Postcode must be numeric.")
        phone_regex = re.compile(r'^\+?[1-9]\d{1,14}$')
        if not phone_regex.match(phone):
            errors.append("Invalid phone number format.")

        # Check if the address already exists for the user
        if Address.objects.filter(
            user=request.user,
            name=name,
            address=address_line,
            city=city,
            state=state,
            country=country,
            postcode=postcode,
            phone=phone
        ).exclude(id=address_id).exists():
            errors.append("This address already exists.")

        if errors:
            return render(
                request,
                'user/edit_address.html',
                {
                    'errors': errors,
                    'data': {
                        'id': address_id,
                        'name': name,
                        'address': address_line,
                        'city': city,
                        'state': state,
                        'country': country,
                        'postcode': postcode,
                        'phone': phone,
                    },
                },
            )

        address.name = name
        address.address = address_line
        address.city = city
        address.state = state
        address.country = country
        address.postcode = postcode
        address.phone = phone
        address.save()

        messages.success(request, "Address updated successfully!")
        return redirect('addresses')

    return render(request, 'user/edit_address.html', {'address': address})








"""
DELETING ADDRESS
"""
@login_required
def delete_address(request, address_id):
    address = get_object_or_404(Address, id=address_id, user=request.user)

    if request.method == 'POST':
        address.delete()
        messages.success(request, 'Address deleted successfully!')
        return redirect('addresses')

    return redirect('addresses')







"""
CHANGE PASSWORD
"""
@login_required
def change_password(request):
    if request.method == 'POST':
        current_password = request.POST.get('current_password')
        new_password = request.POST.get('new_password')
        confirm_password = request.POST.get('confirm_password')

        user = authenticate(username=request.user.username, password=current_password)
        if not user:
            messages.error(request, 'The current password you entered is incorrect.')
            return redirect('change_password')

        if new_password != confirm_password:
            messages.error(request, 'The new password and confirm password do not match.')
            return redirect('change_password')

        is_valid, error_message = validate_password(new_password)
        if not is_valid:
            messages.error(request, error_message)
            return redirect('change_password')

        user.set_password(new_password)
        user.save()
        update_session_auth_hash(request, user)
        messages.success(request, 'Password changed successfully!')
        return redirect('user_profile')

    return render(request, 'user/change_password.html')





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
CHANGE EMAIL FUNCTION
"""
@login_required
def change_email(request):
    if request.method == 'POST':
        new_email = request.POST.get('new_email', '').strip()

        # Validate email format
        email_regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_regex, new_email):
            messages.error(request, 'Invalid email address format. Please enter a valid email.')
            return render(request, 'user/change_email.html')

        # Check if the email is already in use
        if User.objects.filter(email=new_email).exists():
            messages.error(request, 'This email is already registered. Please use a different email.')
            return render(request, 'user/change_email.html')

        # Generate OTP and store it in the session
        otp = ''.join(random.choices(string.digits, k=6))
        request.session['new_email'] = new_email
        request.session['otp'] = otp

        # Send OTP to the new email
        subject = 'Email Change Verification'
        message = f'Your OTP to change your email is: {otp}'
        from_email = settings.DEFAULT_FROM_EMAIL
        try:
            send_mail(subject, message, from_email, [new_email])
        except Exception as e:
            messages.error(request, 'Failed to send the OTP. Please try again later.')
            return render(request, 'user/change_email.html')

        messages.success(request, 'An OTP has been sent to your new email. Please verify to complete the process.')
        return redirect('verify_email')  # Redirect to the OTP verification page

    return render(request, 'user/change_email.html')









"""
EMAIL VERIFICATION
"""
@login_required
def verify_email(request):
    if request.method == 'POST':
        entered_otp = request.POST.get('otp', '').strip()
        session_otp = request.session.get('otp')
        new_email = request.session.get('new_email')

        # Check for missing session data
        if not session_otp or not new_email:
            messages.error(request, 'Session expired or invalid. Please restart the email change process.')
            return redirect('change_email')

        # Check if OTP matches
        if entered_otp == session_otp:
            # Update user's email
            user = request.user
            user.email = new_email
            user.save()

            # Clear session variables
            request.session.pop('otp', None)
            request.session.pop('new_email', None)

            return redirect('user_profile')

        # Handle invalid OTP
        messages.error(request, 'Invalid OTP. Please try again.')
        return render(request, 'user/verify_email.html')

    return render(request, 'user/verify_email.html')
