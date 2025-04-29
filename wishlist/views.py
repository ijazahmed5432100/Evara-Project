from django.shortcuts import render, redirect, get_object_or_404 # type: ignore
from products.models import Product 
from .models import Wishlist, WishlistItem
from django.contrib.auth.decorators import login_required # type: ignore
from django.http import JsonResponse # type: ignore
from cart.models import Cart, CartItem
import logging
from django.contrib import messages # type: ignore

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

        # Check stock status based on variants
        variants = item.product.variants.all()
        item.is_in_stock = any(variant.stock > 0 for variant in variants) if variants.exists() else False



    return render(request,'user/wishlist.html', {'wishlist_items': items, 'wishlist_items': wishlist_items} )



@login_required
def add_to_wishlist(request, product_id):
    """Add a product to the user's wishlist."""
    product = get_object_or_404(Product, id=product_id)
    wishlist, created = Wishlist.objects.get_or_create(user=request.user)

    # Check if the product is already in the wishlist
    if not WishlistItem.objects.filter(wishlist=wishlist, product=product).exists():
        WishlistItem.objects.create(wishlist=wishlist, product=product)
        return JsonResponse({"success": True, "message": "Product added to wishlist"})
    else:
        return JsonResponse({"success": False, "message": "Product is already in your wishlist"})





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







