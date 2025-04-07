from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from .models import Cart, CartItem
from products.models import Product, ProductVariant
from django.contrib import messages
from decimal import Decimal
import logging
from django.views.decorators.http import require_POST
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger


logger = logging.getLogger(__name__)



@login_required
def cart_view(request):
    """Display the user's cart"""
    if not request.user.is_authenticated:
        return render(request, 'user/cart.html', {'cart_empty': True, 'message': 'Your cart is empty. Please log in to add items.'})

    cart, created = Cart.objects.get_or_create(user=request.user)
    cart_items = cart.items.all()

    # Check stock availability for each item in the cart
    out_of_stock_items = []
    for item in cart_items:
        if item.product_variant.stock < item.quantity:
            out_of_stock_items.append({
                'product_name': item.product_variant.product.name,
                'variant': f"{item.product_variant.color} / {item.product_variant.size}",
                'available_stock': item.product_variant.stock,
            })

    total_listed_price = Decimal('0.00')
    total_offer_price = Decimal('0.00')
    for item in cart_items:
        product = item.product_variant.product
        # product_offer = ProductOffer.objects.filter(product=product, is_active=True).first()
        # category_offer = CategoryOffer.objects.filter(category=product.category, is_active=True).first()

        # Calculate the final price based on the best offer
        # if product_offer and category_offer:
        #     final_price = min(
        #         product.price * (1 - product_offer.discount_percentage / 100),
        #         product.price * (1 - category_offer.discount_percentage / 100)
        #     )
        # elif product_offer:
        #     final_price = product.price * (1 - product_offer.discount_percentage / 100)
        # elif category_offer:
        #     final_price = product.price * (1 - category_offer.discount_percentage / 100)
        # else:
        final_price = product.price

        quantity = Decimal(str(item.quantity))
        item.subtotal = final_price * quantity
        item.subtotal_listed_price = product.price * quantity
        item.subtotal_offer_price = final_price * quantity
        total_listed_price += item.subtotal_listed_price
        total_offer_price += item.subtotal_offer_price

    discounted_amount = total_listed_price - total_offer_price
    delivery_charge = Decimal('40.00') if total_offer_price < Decimal('1000.00') else Decimal('0.00')
    grand_total = total_offer_price + delivery_charge

    if not cart_items.exists():
        return render(request, 'user/cart.html', {'cart_empty': True, 'message': 'Your cart is empty. Start shopping now!'})

    # Pagination
    page = request.GET.get('page', 1)
    paginator = Paginator(cart_items, 10)  # Show 10 items per page

    try:
        cart_items = paginator.page(page)
    except PageNotAnInteger:
        cart_items = paginator.page(1)
    except EmptyPage:
        cart_items = paginator.page(paginator.num_pages)

    context = {
        'cart_items': cart_items,
        'cart_empty': False,
        'out_of_stock_items': out_of_stock_items,
        'cart_count': cart_items.paginator.count,
        'total_listed_price': total_listed_price,
        'total_offer_price': total_offer_price,
        'discounted_amount': discounted_amount,
        'delivery_charge': delivery_charge,
        'grand_total': grand_total,
    }

    return render(request, 'user/cart.html', context)











    # cart, _ = Cart.objects.get_or_create(user=request.user)
    # cart_items = list(cart.items.select_related('product', 'variant'))  # Optimize DB query
   
    # for item in cart_items:
    #     if not item.variant_id:  # Explicitly check for None
    #         item.variant_id = 0  # Set to 0 if None
    
    # total_price = cart.get_total_price() 


    # return render(request, 'user/cart.html', {
    #     'cart_items': cart_items,
    #     'total_price': total_price,
    # })







@login_required
def add_to_cart(request):
    product_id = request.POST.get('product_id')
    color = request.POST.get('color')
    size = request.POST.get('size')
    quantity = int(request.POST.get('quantity', 1))

    logger.info(f"Adding to cart: product_id={product_id}, color={color}, size={size}, quantity={quantity}")

    try:
        product = Product.objects.get(id=product_id)

        # Check if the product has any variants
        variants = ProductVariant.objects.filter(product=product)

        if not variants.exists():
            logger.error(f"No variants available for product_id={product_id}")
            return JsonResponse({'success': False, 'error': 'No stock available for this product.'})

        # Find the variant based on selected color and size
        if color and size:
            product_variant = variants.filter(color=color, size=size).first()
        if not product_variant:
            # Attempt to find a default variant if the exact match is not found
            product_variant = variants.first()

        if not product_variant:
            logger.error(f"No valid variant found for product_id={product_id}, color={color}, size={size}")
            return JsonResponse({'success': False, 'error': 'No valid variant found for this product.'})

        # Check stock availability
        if product_variant.stock <= 0:
            logger.error(f"Product variant out of stock: variant_id={product_variant.id}")
            return JsonResponse({'success': False, 'error': 'This product is out of stock.'})

        # Add to cart or update existing cart item
        cart, created = Cart.objects.get_or_create(user=request.user)
        cart_item, created = CartItem.objects.get_or_create(cart=cart, product_variant=product_variant)
        if not created:
            cart_item.quantity += quantity
            return JsonResponse({'success': False, 'error': 'This product is already in the cart.'})

        cart_item.quantity=quantity
        cart_item.save()

        logger.info(f"Item added to cart: product_id={product_id}, variant_id={product_variant.id}, quantity={quantity}")
        return JsonResponse({'success': True, 'message': 'Item added to cart.'})

    except Product.DoesNotExist:
        logger.error(f"Product not found: product_id={product_id}")
        return JsonResponse({'success': False, 'error': 'Product not found.'})
    except Exception as e:
        logger.error(f"Error adding to cart: {str(e)}")
        return JsonResponse({'success': False, 'error': str(e)})















"""
UPDATE CART
"""
@login_required
@require_POST
def update_cart(request, item_id, action):
    logger.debug(f"Update Cart URL: /update_cart/{item_id}/{action}/")
    try:
        cart_item = CartItem.objects.get(id=item_id, cart__user=request.user)
        product_variant = cart_item.product_variant
        
        MAX_QUANTITY = 5

        if action == "increase":
            # Check both stock and maximum limit
            if cart_item.quantity >= MAX_QUANTITY:
                return JsonResponse({
                    'message': 'Maximum quantity limit (5) reached for this product',
                    'status': 'error'
                }, status=400)
            elif cart_item.quantity + 1 > product_variant.stock:
                return JsonResponse({
                    'message': 'Stock will be unavailable',
                    'status': 'error'
                }, status=400)
            cart_item.quantity += 1
        elif action == "decrease" and cart_item.quantity > 1:
            cart_item.quantity -= 1
        
        cart_item.save()
        return JsonResponse({
            'message': 'Cart updated successfully.',
            'status': 'success'
        })
    except CartItem.DoesNotExist:
        return JsonResponse({
            'message': 'Item not found in the cart.',
            'status': 'error'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'message': str(e),
            'status': 'error'
        }, status=500)









"""
REMOVE FROM CART
"""
@login_required
@require_POST
def remove_from_cart(request, item_id):
    logger.debug(f"Remove From Cart URL: /remove_from_cart/{item_id}/")
    try:
        cart_item = CartItem.objects.get(id=item_id, cart__user=request.user)
        cart_item.delete()
        return JsonResponse({'message': 'Item removed from cart successfully.'})
    except CartItem.DoesNotExist:
        return JsonResponse({'message': 'Item not found in the cart.'}, status=404)
    except Exception as e:
        return JsonResponse({'message': str(e)}, status=500)






