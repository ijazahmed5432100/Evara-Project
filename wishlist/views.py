from django.shortcuts import render, redirect, get_object_or_404
from products.models import Product 
from .models import Wishlist, WishlistItem
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from cart.models import Cart, CartItem
import logging
from django.contrib import messages

# Create your views here.


logger = logging.getLogger(__name__)


@login_required
def wishlist_view(request):
    """Display the user's wishlist."""
    wishlist,created = Wishlist.objects.get_or_create(user=request.user)
    items = wishlist.items.select_related("product")
    
    wishlist_items = WishlistItem.objects.filter(wishlist__user=request.user).select_related('product')

    for item in wishlist_items:
        # Fetch the first image of the product
        first_image = item.product.images.first()
        item.first_image_url = first_image.image.url if first_image else None



    return render(request,'user/wishlist.html', {'wishlist_items': items, 'wishlist_items': wishlist_items} )



@login_required
def add_to_wishlist(request, product_id):
    """Add a product product to the users wishlist."""
    product = get_object_or_404(Product, id=product_id)
    wishlist, created = Wishlist.objects.get_or_create(user=request.user)

    # Check if the product is already in the wishlist
    if not WishlistItem.objects.filter(wishlist=wishlist, product=product).exists():
        WishlistItem.objects.create(wishlist=wishlist, product=product)

    return JsonResponse({"status":"success", "message": "Added to wishlist"})




@login_required
def remove_from_wishlist(request, item_id):
    """Remove an item from the wishlist."""
    item = get_object_or_404(WishlistItem, id=item_id, wishlist__user = request.user )
    item.delete()
    messages.success(request, 'Product removed from wishlist.')
    return redirect('wishlist')
    # return JsonResponse({ 'status': 'success', 'message': 'Removed from wishlist' })







"""
MOVE TO CART
"""
@login_required
def move_to_cart(request, item_id):
    wishlist_item = get_object_or_404(WishlistItem, id=item_id, wishlist__user=request.user)
    product = wishlist_item.product

    # Check if the product is already in the cart
    cart, created = Cart.objects.get_or_create(user=request.user)
    if CartItem.objects.filter(cart=cart, product_variant__product=product).exists():
        messages.error(request, 'Product is already in your cart.')
    else:
        # Assuming the product has a default variant
        product_variant = product.variants.first()
        if not product_variant:
            messages.error(request, 'No valid variant found for this product.')
        else:
            CartItem.objects.create(cart=cart, product_variant=product_variant, quantity=1)
            wishlist_item.delete()
            messages.success(request, 'Product moved to cart.')
            return redirect('wishlist')

    return redirect('wishlist')







# @login_required
# def move_to_cart(request, item_id):
#     """Move a wishlist item to the cart and remove it from the wishlist."""
#     try:
#         item = get_object_or_404(WishlistItem, id=item_id, wishlist__user=request.user)
        
#         # Ensure the cart exists
#         cart, created = Cart.objects.get_or_create(user=request.user)
        
#         # Move to cart
#         cart_item, created = CartItem.objects.get_or_create(cart=cart, product=item.product)
#         if not created:
#             cart_item.quantity += 1  # Increase quantity if already exists
#             cart_item.save()

#         # Remove from wishlist
#         item.delete()

#         return JsonResponse({"status": "success", "message": "Moved to cart"})
    
#     except Exception as e:
#         logger.error(f"Error in move_to_cart: {str(e)}")
#         return JsonResponse({"status": "error", "message": str(e)}, status=500)






    


# @login_required
# def move_to_cart(request, item_id):
#     """Move a wishlist item to the cart and remove it from the wishlist."""
#     item = get_object_or_404(WishlistItem, id=item_id, wishlist__user=request.user)
    
#     # Ensure the cart exists
#     cart, created = Cart.objects.get_or_create(user=request.user)
    
#     # Move to cart
#     cart_item, created = CartItem.objects.get_or_create(cart=cart, product=item.product)
#     if not created:
#         cart_item.quantity += 1  # Increase quantity if already exists
#         cart_item.save()

#     # Remove from wishlist
#     item.delete()

#     return JsonResponse({"status": "success", "message": "Moved to cart"})




    


# @login_required
# def move_to_cart(request, item_id):
#     """Move a wishlist item to the cart and remove it from the wishlist."""
#     try:
#         # Get the wishlist item
#         item = get_object_or_404(WishlistItem, id=item_id, wishlist__user=request.user)

#         # Ensure the cart exists
#         cart, created = Cart.objects.get_or_create(user=request.user)

#         # Move item to cart
#         cart_item, cart_created = CartItem.objects.get_or_create(cart=cart, product=item.product)
        
#         if not cart_created:
#             cart_item.quantity += 1  # Increase quantity if already in cart
#             cart_item.save()

#         # Remove from wishlist
#         item.delete()

#         return JsonResponse({"status": "success", "message": "Moved to cart"})

#     except Exception as e:
#         return JsonResponse({"status": "error", "message": str(e)}, status=500)






    





    






