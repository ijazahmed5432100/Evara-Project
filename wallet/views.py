from django.shortcuts import render
from .models import Wallet, WalletTransaction
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger


# Create your views here.


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