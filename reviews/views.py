from django.shortcuts import render,get_object_or_404,redirect
from django.contrib.auth.decorators import login_required
from products.models import Product
from orders.models import OrderItem
from django.contrib import messages
from .models import Review



# Create your views here.




"""
ADD REVIEW
"""
@login_required
def add_review(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    
    if not OrderItem.objects.filter(order__user=request.user, product=product, status='delivered').exists():
        messages.error(request, "You must purchase this product to leave a review.")
        return redirect('product_details', product_id=product.id)
    
    if Review.objects.filter(user=request.user, product=product).exists():
        messages.error(request, "You have already reviewed this product.")
        return redirect('product_details', product_id=product.id)
    
    if request.method == 'POST':
        rating = request.POST.get('rating')
        review_text = request.POST.get('review_text')
        
        Review.objects.create(
            user=request.user,
            product=product,
            rating=rating,
            review_text=review_text
        )
        
        messages.success(request, "Your review has been submitted successfully.")
        return redirect('product_details', product_id=product.id)
    
    return render(request, 'user/add_review.html', {'product': product})






"""
REVIEW EDITING
"""
@login_required
def edit_review(request, review_id):
    review = get_object_or_404(Review, id=review_id, user=request.user)
    
    if request.method == 'POST':
        rating = request.POST.get('rating')
        review_text = request.POST.get('review_text')
        
        review.rating = rating
        review.review_text = review_text
        review.save()
        
        messages.success(request, "Your review has been updated successfully.")
        return redirect('product_details', product_id=review.product.id)
    
    return render(request, 'user/edit_review.html', {'review': review}) 



