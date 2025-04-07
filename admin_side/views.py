from django.shortcuts import render,redirect,get_object_or_404
import logging
from django.contrib import messages
from django.contrib.auth import authenticate, login,logout
from django.contrib.auth.decorators import user_passes_test,login_required
from django.contrib.auth.models import User
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.views.decorators.cache import never_cache



# Create your views here.


"""
ERROR FINDING/DEBUG
"""
logger = logging.getLogger(__name__)





"""
ADMIN CHECK
"""
def is_admin(user):
    return user.is_staff



"""
ADMIN LOGIN
"""
@never_cache
def admin_login(request):
    max_attempts = 5
    


    if request.session.get('login_attempts', 0) >= max_attempts:
        messages.error(request, 'Too many failed login attempts. Try again later')
        return render(request, 'admin/admin_login.html')
    
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')

        user = authenticate(request, username=username,password=password)

        if user is not None and user.is_staff:
            login(request, user)
            request.session['login_attempts'] = 0 #Reset failed attempts
            return redirect('admin_dashboard')
        
        else:
            request.session['login_attempts'] = request.session.get('login_attempts', 0) + 1
            logger.warning(f"Failed admin login attempt for username: {username}")
            messages.error(request, 'Invalid credentials or not an admin user.')
            return render(request, 'admin/admin_login.html')
    
    

    return render(request, 'admin/admin_login.html')




@never_cache
def admin_dashboard(request):
    return render(request, 'admin/dashboard.html')




"""
ADMIN SIDE USER MANAGEMENT
"""
@never_cache
@user_passes_test(is_admin)
def user_manage(request):
    query = request.GET.get('q', '') 
    users = User.objects.filter(is_superuser=False).order_by('-date_joined')

    if query:
        users = users.filter(username__icontains=query)
        

    page = request.GET.get('page', 1)
    paginator = Paginator(users, 10)


    try:
        users = paginator.page(page)
    except PageNotAnInteger:
        users = paginator.page(1)
    except EmptyPage:
        users = paginator.page(paginator.num_pages)        

    return render(request, 'admin/users.html', {'users':users , 'query': query,})





"""
BLOCK USER
"""
@never_cache
@user_passes_test(is_admin)
def block_user(request,user_id):
    user = get_object_or_404(User, id=user_id)
    user.is_active = False
    user.save()
    messages.success(request, f"{user.username} has been blocked.")
    return redirect('users')






"""
UNBLOCK USER
"""
@never_cache
@user_passes_test(is_admin)
def unblock_user(request, user_id):
    user = get_object_or_404(User, id=user_id)
    user.is_active = True
    user.save()
    messages.success(request, f'{user.username} has been unblocked.')
    return redirect('users')






"""
ADMIN LOGOUT
"""
@never_cache
@login_required(login_url='admin_login') 
def admin_logout(request):
    logout(request)
    return redirect('admin_login')














