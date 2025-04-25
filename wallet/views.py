from django.shortcuts import render,get_object_or_404,redirect
from .models import Wallet, WalletTransaction
from django.contrib.auth.decorators import login_required,user_passes_test
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.urls import reverse
from django.contrib.auth.models import User
from functools import wraps
from django.views.decorators.cache import never_cache


# Create your views here.




# Admin access check
def is_admin(user):
    return user.is_authenticated and user.is_staff





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
WALLET PAGE
"""
@login_required
def wallet_view(request):
    try:
        wallet = Wallet.objects.get(user=request.user)
    except Wallet.DoesNotExist:
        # If the wallet does not exist, create a new one with zero balance
        wallet = Wallet.objects.create(user=request.user, balance=0.00)
    
    # Filter
    filter_type = request.GET.get('filter', 'all') 
    
    # Filter transactions based on the selected filter
    transactions = WalletTransaction.objects.filter(wallet=wallet).order_by('-created_at')
    if filter_type == 'credit':
        transactions = transactions.filter(transaction_type='credit')
    elif filter_type == 'debit':
        transactions = transactions.filter(transaction_type='debit')
    
    page = request.GET.get('page', 1) 
    paginator = Paginator(transactions, 10)
    
    try:
        transactions = paginator.page(page)
    except PageNotAnInteger:
        transactions = paginator.page(1)
    except EmptyPage:
        transactions = paginator.page(paginator.num_pages)
    
    return render(request, 'user/wallet.html', {
        'wallet': wallet,
        'transactions': transactions,
        'filter_type': filter_type,
    })












@admin_required
@never_cache
@user_passes_test(is_admin)
def admin_wallet_transaction_list(request):
    transactions = WalletTransaction.objects.all().order_by('-created_at')
    filter_type = request.GET.get('filter', 'all')
    if filter_type == 'credit':
        transactions = transactions.filter(transaction_type='credit')
    elif filter_type == 'debit':
        transactions = transactions.filter(transaction_type='debit')

    page = request.GET.get('page', 1)
    paginator = Paginator(transactions, 10)
    try:
        transactions = paginator.page(page)
    except PageNotAnInteger:
        transactions = paginator.page(1)
    except EmptyPage:
        transactions = paginator.page(paginator.num_pages)

    return render(request, 'admin/wallet_transaction_list.html', {
        'transactions': transactions,
        'filter_type': filter_type,
    })





@admin_required
@never_cache
@user_passes_test(is_admin)
def admin_wallet_transaction_detail(request, transaction_id):
    transaction = get_object_or_404(WalletTransaction, transaction_id=transaction_id)
    user = transaction.wallet.user
    order_url = reverse('admin_order_details', args=[transaction.order.id]) if transaction.order else None
    context = {
        'transaction': transaction,
        'user': transaction.wallet.user,
        'order_url': order_url,
    }
    return render(request, 'admin/wallet_transaction_detail.html',context)





