from django.shortcuts import render,redirect,get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from coupons.models import Coupon,CouponUsage
from django.core.paginator import Paginator
from .forms import CouponForm
from django.contrib import messages
from django.utils import timezone
from decimal import Decimal
from functools import wraps
from django.views.decorators.cache import never_cache


# Create your views here.





###############################################USER SIDE START###############################################
"""
APPLY COUPON
"""
@login_required
def apply_coupon(request):
    if request.method == "POST":
        coupon_code = request.POST.get('coupon_code')
        request.session['entered_coupon_code'] = coupon_code  # Store the entered coupon code in the session
        try:
            coupon = Coupon.objects.get(coupon_code=coupon_code, is_active=True)
            if coupon.is_valid():
                # Check if the user has already used this coupon
                if CouponUsage.objects.filter(user=request.user, coupon=coupon).exists():
                    messages.error(request, 'You have already used this coupon.')
                else:
                    # Check if the cart total meets the minimum purchase amount
                    cart_total = Decimal(request.session.get('cart_total', '0.00'))
                    if cart_total >= coupon.minimum_purchase_amount:
                        request.session['coupon_code'] = coupon_code
                        messages.success(request, 'Coupon applied successfully.')
                    else:
                        messages.error(request, f'Minimum purchase amount of ₹{coupon.minimum_purchase_amount} required to apply this coupon.')
            else:
                messages.error(request, 'This coupon is not valid.')
        except Coupon.DoesNotExist:
            messages.error(request, 'Invalid coupon code.')
    return redirect('place_order')




"""
REMOVE COUPON
"""
@login_required
def remove_coupon(request):
    if 'coupon_code' in request.session:
        del request.session['coupon_code']
        messages.success(request, 'Coupon removed successfully.')
    return redirect('place_order')





"""
AVAILABLE COUPONS LISTING IN THE USER SIDE
"""
@login_required
def view_coupons(request):
    now = timezone.now().date()

    # Filter valid coupons active and within the validity period
    valid_coupons = Coupon.objects.filter(
        valid_from__lte=now,   
        valid_to__gte=now,    
        is_active=True      
    )

    # Check which coupons the user has already used
    used_coupons = CouponUsage.objects.filter(user=request.user).values_list('coupon_id', flat=True)

    # Flag for used coupons
    coupon_list = []
    for coupon in valid_coupons:
        coupon_list.append({
            'coupon': coupon,
            'is_used': coupon.coupon_id in used_coupons,
        })

    context = {
        'coupon_list': coupon_list,
    }
    return render(request, 'user/view_coupons.html', context)






















###############################################ADMIN SIDE START###############################################

"""
ADMIN CHECK
"""
def is_admin(user):
    return user.is_authenticated and user.is_superuser




def admin_required(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('admin_login')  # your admin login page route name
        if not request.user.is_staff:  # or use a custom user check like user.role == 'admin'
            return redirect('admin_login')  # or maybe a "permission denied" page
        return view_func(request, *args, **kwargs)
    return _wrapped_view




"""
COUPON LISTING IN THE ADMIN SIDE
"""
@admin_required
@never_cache
@user_passes_test(is_admin)
def coupon_list(request):
    query = request.GET.get('q', '')
    coupons = Coupon.objects.all()

    if query:
        coupons = coupons.filter(coupon_code__icontains=query)

    paginator = Paginator(coupons, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'coupons': page_obj,
        'query': query,
    }
    return render(request, 'admin/coupon_list.html', context)





"""
ADD NEW COUPON
"""
@admin_required
@never_cache
@user_passes_test(is_admin)
def add_coupon(request):
    if request.method == 'POST':
        form = CouponForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Coupon added successfully.')
            return redirect('coupon_list')
    else:
        form = CouponForm()
    return render(request, 'admin/add_coupon.html', {'form': form})





"""
EDIT AVAILABLE COUPON
"""
@admin_required
@never_cache
@user_passes_test(is_admin)
def edit_coupon(request, coupon_id):
    coupon = get_object_or_404(Coupon, coupon_id=coupon_id)
    if request.method == 'POST':
        form = CouponForm(request.POST, instance=coupon)
        if form.is_valid():
            form.save()
            messages.success(request, 'Coupon updated successfully.')
            return redirect('coupon_list')
    else:
        form = CouponForm(instance=coupon)
    return render(request, 'admin/edit_coupon.html', {'form': form, 'coupon': coupon})







"""
COUPON ACTIVATE/DEACTIVATE
"""
@admin_required
@never_cache
@user_passes_test(is_admin)
def toggle_coupon_status(request, coupon_id):
    coupon = get_object_or_404(Coupon, coupon_id=coupon_id)
    coupon.is_active = not coupon.is_active
    coupon.save()
    action = "activated" if coupon.is_active else "deactivated"
    messages.success(request, f'Coupon {action} successfully.')
    return redirect('coupon_list')




"""
COUPON DELETING
"""
@admin_required
@never_cache
@user_passes_test(is_admin)
def delete_coupon(request, coupon_id):
    coupon = get_object_or_404(Coupon, coupon_id=coupon_id)
    coupon.delete()
    messages.success(request, 'Coupon deleted successfully.')
    return redirect('coupon_list')


###############################################ADMIN SIDE END###############################################

