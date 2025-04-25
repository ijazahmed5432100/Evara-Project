from django.shortcuts import render,redirect,get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from user_profile.models import Address, ShippingAddress
from cart.models import Cart, CartItem
from django.http import JsonResponse,HttpResponse
from django.contrib import messages
from decimal import Decimal
from orders.models import Order, OrderItem
from django.urls import reverse
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.utils import timezone
from django.template.loader import render_to_string
from weasyprint import HTML
from django.views.decorators.http import require_POST
from wallet.models import Wallet,WalletTransaction
from offers.models import ProductOffer,CategoryOffer
from coupons.models import Coupon,CouponUsage
from django.views.decorators.cache import never_cache
from functools import wraps




# Create your views here.




###############################################USER SIDE START###############################################













@login_required
def place_order(request):
    user = request.user
    addresses = Address.objects.filter(user=user, is_deleted=False)
    default_address = addresses.filter(is_default=True).first()

    try:
        cart = Cart.objects.get(user=user)
        cart_items = CartItem.objects.filter(cart=cart)

        if not cart_items.exists():
            return JsonResponse({"error": "Your cart is empty. Please add items to checkout."}, status=400)

        for item in cart_items:
            if item.quantity > item.product_variant.stock:
                messages.error(request, 'Please remove the out of stock products')
                return redirect('cart_view')

        total_listed_price = Decimal('0.00')
        total_offer_price = Decimal('0.00')
        for item in cart_items:
            product = item.product_variant.product
            product_offer = ProductOffer.objects.filter(product=product, is_active=True).first()
            category_offer = CategoryOffer.objects.filter(category=product.category, is_active=True).first()

            if product_offer and category_offer:
                final_price = min(
                    product.price * (1 - product_offer.discount_percentage / 100),
                    product.price * (1 - category_offer.discount_percentage / 100)
                )
            elif product_offer:
                final_price = product.price * (1 - product_offer.discount_percentage / 100)
            elif category_offer:
                final_price = product.price * (1 - category_offer.discount_percentage / 100)
            else:
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

        request.session['cart_total'] = str(total_offer_price)

        coupon_discount = Decimal('0.00')
        coupon_code = request.session.get('coupon_code', None)
        coupon = None
        if coupon_code:
            try:
                coupon = Coupon.objects.get(coupon_code=coupon_code, is_active=True)
                if coupon.is_valid() and total_offer_price >= coupon.minimum_purchase_amount:
                    if not CouponUsage.objects.filter(user=user, coupon=coupon).exists():
                        coupon_discount = (coupon.discount_percentage / Decimal('100.00')) * total_offer_price
                        if coupon_discount > coupon.max_discount_amount:
                            coupon_discount = coupon.max_discount_amount
                        grand_total -= coupon_discount
                        discounted_amount += coupon_discount
                    else:
                        coupon = None  # Coupon already used
                        if 'coupon_code' in request.session:
                            del request.session['coupon_code']
            except Coupon.DoesNotExist:
                coupon = None
                if 'coupon_code' in request.session:
                    del request.session['coupon_code']

        # Filter available coupons
        now = timezone.now().date()
        available_coupons = Coupon.objects.filter(
            valid_from__lte=now,
            valid_to__gte=now,
            is_active=True,
            minimum_purchase_amount__lte=total_offer_price
        ).exclude(coupon_id__in=CouponUsage.objects.filter(user=user).values_list('coupon_id', flat=True))
        available_coupons = available_coupons[:2]

    except Cart.DoesNotExist:
        return JsonResponse({"error": "Cart not found"}, status=400)

    if request.method == "POST":
        try:
            address_id = request.POST.get("address_id")
            payment_method = request.POST.get("payment_method")

            if not address_id or not payment_method:
                return JsonResponse({"error": "Address or payment method not provided."}, status=400)

            address = Address.objects.get(id=address_id, user=user) if address_id else default_address
            if not address:
                return JsonResponse({"error": "No valid address found."}, status=400)

            shipping_address = ShippingAddress.objects.create(
                user=user,
                name=address.name,
                address=address.address,
                city=address.city,
                state=address.state,
                country=address.country,
                postcode=address.postcode,
                phone=address.phone,
            )

            if payment_method == "COD":
                payment_status = 'Pending'
                order_status = 'pending'
                order_item_status = 'order_placed'
            elif payment_method == "wallet":
                payment_status = 'Paid'
                order_status = 'pending'
                order_item_status = 'order_placed'
            elif payment_method == "razorpay":
                payment_status = 'Pending'
                order_status = 'processing'
                order_item_status = 'processing'
            else:
                return JsonResponse({"error": "Invalid payment method"}, status=400)

            order = Order.objects.create(
                user=user,
                shipping_address=shipping_address,
                payment_method=payment_method,
                payment_status=payment_status,
                status=order_status,
                total_price=grand_total,
                coupon=coupon,
                discount_coupon_amount=coupon_discount
            )

            for item in cart_items:
                if item.product_variant.stock < item.quantity:
                    order.delete()
                    return JsonResponse({"error": f"Not enough stock for {item.product_variant.product.name}."}, status=400)

                item.product_variant.stock -= item.quantity
                item.product_variant.save()

                product = item.product_variant.product
                product_offer = ProductOffer.objects.filter(product=product, is_active=True).first()
                category_offer = CategoryOffer.objects.filter(category=product.category, is_active=True).first()
                final_price = product.price
                if product_offer and category_offer:
                    final_price = min(
                        product.price * (1 - product_offer.discount_percentage / 100),
                        product.price * (1 - category_offer.discount_percentage / 100)
                    )
                elif product_offer:
                    final_price = product.price * (1 - product_offer.discount_percentage / 100)
                elif category_offer:
                    final_price = product.price * (1 - category_offer.discount_percentage / 100)

                OrderItem.objects.create(
                    order=order,
                    product=item.product_variant.product,
                    product_variant=item.product_variant,
                    quantity=item.quantity,
                    status=order_item_status,
                    price=final_price,
                    final_offer_price=final_price
                )

            # Only create CouponUsage if coupon is not None
            if coupon is not None:
                CouponUsage.objects.create(user=user, coupon=coupon)

            request.session['cart_details'] = {'order_id': order.id}

            if payment_method in ["COD", "wallet"]:
                if payment_method == "wallet":
                    wallet = Wallet.objects.get(user=user)
                    if wallet.balance < grand_total:
                        order.delete()
                        return JsonResponse({"error": "Insufficient funds in wallet."}, status=400)
                    wallet.balance -= grand_total
                    wallet.save()

                    WalletTransaction.objects.create(
                        wallet=wallet,
                        order=order,
                        amount=grand_total,
                        transaction_type='debit'
                    )

                # Clear cart and session data
                cart_items.delete()
                # Move session cleanup to after the response to avoid race conditions
                redirect_url = reverse('order_success', args=[order.id])
                # Clear session data after preparing the response
                if 'cart_details' in request.session:
                    del request.session['cart_details']
                if 'coupon_code' in request.session:
                    del request.session['coupon_code']
                return JsonResponse({"redirect": redirect_url})

            elif payment_method == "razorpay":
                return JsonResponse({"redirect": reverse('payments:initiate_payment')})

        except Exception as e:
            # Log the exception for debugging
            print(f"Error in place_order: {str(e)}")
            return JsonResponse({"error": str(e)}, status=400)

    context = {
        'addresses': addresses,
        'default_address': default_address,
        'cart_items': cart_items,
        'total_listed_price': total_listed_price,
        'total_offer_price': total_offer_price,
        'discounted_amount': discounted_amount,
        'delivery_charge': delivery_charge,
        'grand_total': grand_total,
        'coupon_discount': coupon_discount,
        'available_coupons': available_coupons,
    }
    return render(request, 'user/checkout.html', context)











# @login_required
# def place_order(request):
#     user = request.user
#     addresses = Address.objects.filter(user=user, is_deleted=False)
#     default_address = addresses.filter(is_default=True).first()

#     try:
#         cart = Cart.objects.get(user=user)
#         cart_items = CartItem.objects.filter(cart=cart)

#         if not cart_items.exists():
#             return JsonResponse({"error": "Your cart is empty. Please add items to checkout."}, status=400)

#         for item in cart_items:
#             if item.quantity > item.product_variant.stock:
#                 messages.error(request, 'Please remove the out of stock products')
#                 return redirect('cart_view')

#         total_listed_price = Decimal('0.00')
#         total_offer_price = Decimal('0.00')
#         for item in cart_items:
#             product = item.product_variant.product
#             product_offer = ProductOffer.objects.filter(product=product, is_active=True).first()
#             category_offer = CategoryOffer.objects.filter(category=product.category, is_active=True).first()

#             if product_offer and category_offer:
#                 final_price = min(
#                     product.price * (1 - product_offer.discount_percentage / 100),
#                     product.price * (1 - category_offer.discount_percentage / 100)
#                 )
#             elif product_offer:
#                 final_price = product.price * (1 - product_offer.discount_percentage / 100)
#             elif category_offer:
#                 final_price = product.price * (1 - category_offer.discount_percentage / 100)
#             else:
#                 final_price = product.price

#             quantity = Decimal(str(item.quantity))
#             item.subtotal = final_price * quantity
#             item.subtotal_listed_price = product.price * quantity
#             item.subtotal_offer_price = final_price * quantity
#             total_listed_price += item.subtotal_listed_price
#             total_offer_price += item.subtotal_offer_price

#         discounted_amount = total_listed_price - total_offer_price
#         delivery_charge = Decimal('40.00') if total_offer_price < Decimal('1000.00') else Decimal('0.00')
#         grand_total = total_offer_price + delivery_charge

#         request.session['cart_total'] = str(total_offer_price)

#         coupon_discount = Decimal('0.00')
#         coupon_code = request.session.get('coupon_code', None)
#         coupon = None
#         if coupon_code:
#             try:
#                 coupon = Coupon.objects.get(coupon_code=coupon_code, is_active=True)
#                 if coupon.is_valid() and total_offer_price >= coupon.minimum_purchase_amount:
#                     if not CouponUsage.objects.filter(user=user, coupon=coupon).exists():
#                         coupon_discount = (coupon.discount_percentage / Decimal('100.00')) * total_offer_price
#                         if coupon_discount > coupon.max_discount_amount:
#                             coupon_discount = coupon.max_discount_amount
#                         grand_total -= coupon_discount
#                         discounted_amount += coupon_discount
#             except Coupon.DoesNotExist:
#                 pass

#         # Filter available coupons
#         now = timezone.now().date()
#         available_coupons = Coupon.objects.filter(
#             valid_from__lte=now,
#             valid_to__gte=now,
#             is_active=True,
#             minimum_purchase_amount__lte=total_offer_price
#         ).exclude(coupon_id__in=CouponUsage.objects.filter(user=user).values_list('coupon_id', flat=True))
#         # Limit to 2 coupons for display
#         available_coupons = available_coupons[:2]

#     except Cart.DoesNotExist:
#         return JsonResponse({"error": "Cart not found"}, status=400)

#     if request.method == "POST":
#         try:
#             address_id = request.POST.get("address_id")
#             payment_method = request.POST.get("payment_method")

#             if not address_id or not payment_method:
#                 return JsonResponse({"error": "Address or payment method not provided."}, status=400)

#             address = Address.objects.get(id=address_id, user=user) if address_id else default_address
#             if not address:
#                 return JsonResponse({"error": "No valid address found."}, status=400)

#             shipping_address = ShippingAddress.objects.create(
#                 user=user,
#                 name=address.name,
#                 address=address.address,
#                 city=address.city,
#                 state=address.state,
#                 country=address.country,
#                 postcode=address.postcode,
#                 phone=address.phone,
#             )

#             if payment_method == "COD":
#                 payment_status = 'Pending'
#                 order_status = 'pending'
#                 order_item_status = 'order_placed'
#             elif payment_method == "wallet":
#                 payment_status = 'Paid'
#                 order_status = 'pending'
#                 order_item_status = 'order_placed'
#             elif payment_method == "razorpay":
#                 payment_status = 'Pending'
#                 order_status = 'processing'
#                 order_item_status = 'processing'
#             else:
#                 return JsonResponse({"error": "Invalid payment method"}, status=400)

#             order = Order.objects.create(
#                 user=user,
#                 shipping_address=shipping_address,
#                 payment_method=payment_method,
#                 payment_status=payment_status,
#                 status=order_status,
#                 total_price=grand_total,
#                 coupon=coupon,
#                 discount_coupon_amount=coupon_discount
#             )

#             for item in cart_items:
#                 if item.product_variant.stock < item.quantity:
#                     order.delete()
#                     return JsonResponse({"error": f"Not enough stock for {item.product_variant.product.name}."}, status=400)

#                 item.product_variant.stock -= item.quantity
#                 item.product_variant.save()

#                 product = item.product_variant.product
#                 product_offer = ProductOffer.objects.filter(product=product, is_active=True).first()
#                 category_offer = CategoryOffer.objects.filter(category=product.category, is_active=True).first()
#                 final_price = product.price
#                 if product_offer and category_offer:
#                     final_price = min(
#                         product.price * (1 - product_offer.discount_percentage / 100),
#                         product.price * (1 - category_offer.discount_percentage / 100)
#                     )
#                 elif product_offer:
#                     final_price = product.price * (1 - product_offer.discount_percentage / 100)
#                 elif category_offer:
#                     final_price = product.price * (1 - category_offer.discount_percentage / 100)

#                 OrderItem.objects.create(
#                     order=order,
#                     product=item.product_variant.product,
#                     product_variant=item.product_variant,
#                     quantity=item.quantity,
#                     status=order_item_status,
#                     price=final_price,
#                     final_offer_price=final_price
#                 )

#             if coupon:
#                 CouponUsage.objects.create(user=user, coupon=coupon)

#             request.session['cart_details'] = {'order_id': order.id}

#             if payment_method in ["COD", "wallet"]:
#                 if payment_method == "wallet":
#                     wallet = Wallet.objects.get(user=user)
#                     if wallet.balance < grand_total:
#                         order.delete()
#                         return JsonResponse({"error": "Insufficient funds in wallet."}, status=400)
#                     wallet.balance -= grand_total
#                     wallet.save()

#                     WalletTransaction.objects.create(
#                     wallet=wallet,
#                     order=order,
#                     amount=grand_total,
#                     transaction_type='debit'
#                 )

#                 cart_items.delete()
#                 del request.session['cart_details']
#                 del request.session['coupon_code']  # Clear coupon after use
#                 return JsonResponse({"redirect": reverse('order_success', args=[order.id])})
#             elif payment_method == "razorpay":
#                 return JsonResponse({"redirect": reverse('payments:initiate_payment')})

#         except Exception as e:
#             return JsonResponse({"error": str(e)}, status=400)

#     context = {
#         'addresses': addresses,
#         'default_address': default_address,
#         'cart_items': cart_items,
#         'total_listed_price': total_listed_price,
#         'total_offer_price': total_offer_price,
#         'discounted_amount': discounted_amount,
#         'delivery_charge': delivery_charge,
#         'grand_total': grand_total,
#         'coupon_discount': coupon_discount,
#         'available_coupons': available_coupons,  # Add available coupons to context
#     }
#     return render(request, 'user/checkout.html', context)












# @login_required
# def place_order(request):
#     user = request.user
#     addresses = Address.objects.filter(user=user, is_deleted=False)
#     default_address = addresses.filter(is_default=True).first()

#     try:
#         cart = Cart.objects.get(user=user)
#         cart_items = CartItem.objects.filter(cart=cart)

#         if not cart_items.exists():
#             return JsonResponse({"error": "Your cart is empty. Please add items to checkout."}, status=400)

#         for item in cart_items:
#             if item.quantity > item.product_variant.stock:
#                 messages.error(request, 'Please remove the out of stock products')
#                 return redirect('cart_view')

#         total_listed_price = Decimal('0.00')
#         total_offer_price = Decimal('0.00')
#         for item in cart_items:
#             product = item.product_variant.product
#             product_offer = ProductOffer.objects.filter(product=product, is_active=True).first()
#             category_offer = CategoryOffer.objects.filter(category=product.category, is_active=True).first()

#             if product_offer and category_offer:
#                 final_price = min(
#                     product.price * (1 - product_offer.discount_percentage / 100),
#                     product.price * (1 - category_offer.discount_percentage / 100)
#                 )
#             elif product_offer:
#                 final_price = product.price * (1 - product_offer.discount_percentage / 100)
#             elif category_offer:
#                 final_price = product.price * (1 - category_offer.discount_percentage / 100)
#             else:
#                 final_price = product.price

#             quantity = Decimal(str(item.quantity))
#             item.subtotal = final_price * quantity
#             item.subtotal_listed_price = product.price * quantity
#             item.subtotal_offer_price = final_price * quantity
#             total_listed_price += item.subtotal_listed_price
#             total_offer_price += item.subtotal_offer_price

#         discounted_amount = total_listed_price - total_offer_price
#         delivery_charge = Decimal('40.00') if total_offer_price < Decimal('1000.00') else Decimal('0.00')
#         grand_total = total_offer_price + delivery_charge

#         request.session['cart_total'] = str(total_offer_price)

#         coupon_discount = Decimal('0.00')
#         coupon_code = request.session.get('coupon_code', None)
#         coupon = None
#         if coupon_code:
#             try:
#                 coupon = Coupon.objects.get(coupon_code=coupon_code, is_active=True)
#                 if coupon.is_valid() and total_offer_price >= coupon.minimum_purchase_amount:
#                     if not CouponUsage.objects.filter(user=user, coupon=coupon).exists():
#                         coupon_discount = (coupon.discount_percentage / Decimal('100.00')) * total_offer_price
#                         if coupon_discount > coupon.max_discount_amount:
#                             coupon_discount = coupon.max_discount_amount
#                         grand_total -= coupon_discount
#                         discounted_amount += coupon_discount
#             except Coupon.DoesNotExist:
#                 pass

#     except Cart.DoesNotExist:
#         return JsonResponse({"error": "Cart not found"}, status=400)

#     if request.method == "POST":
#         try:
#             address_id = request.POST.get("address_id")
#             payment_method = request.POST.get("payment_method")

#             if not address_id or not payment_method:
#                 return JsonResponse({"error": "Address or payment method not provided."}, status=400)

#             address = Address.objects.get(id=address_id, user=user) if address_id else default_address
#             if not address:
#                 return JsonResponse({"error": "No valid address found."}, status=400)

#             shipping_address = ShippingAddress.objects.create(
#                 user=user,
#                 name=address.name,
#                 address=address.address,
#                 city=address.city,
#                 state=address.state,
#                 country=address.country,
#                 postcode=address.postcode,
#                 phone=address.phone,
#             )

#             if payment_method == "COD":
#                 payment_status = 'Pending'
#                 order_status = 'pending'
#                 order_item_status = 'order_placed'
#             elif payment_method == "wallet":
#                 payment_status = 'Paid'
#                 order_status = 'pending'
#                 order_item_status = 'order_placed'
#             elif payment_method == "razorpay":
#                 payment_status = 'Pending'
#                 order_status = 'processing'
#                 order_item_status = 'processing'
#             else:
#                 return JsonResponse({"error": "Invalid payment method"}, status=400)

#             order = Order.objects.create(
#                 user=user,
#                 shipping_address=shipping_address,
#                 payment_method=payment_method,
#                 payment_status=payment_status,
#                 status=order_status,
#                 total_price=grand_total,
#                 coupon=coupon,
#                 discount_coupon_amount=coupon_discount
#             )

#             for item in cart_items:
#                 if item.product_variant.stock < item.quantity:
#                     order.delete()
#                     return JsonResponse({"error": f"Not enough stock for {item.product_variant.product.name}."}, status=400)

#                 item.product_variant.stock -= item.quantity
#                 item.product_variant.save()

#                 product = item.product_variant.product
#                 product_offer = ProductOffer.objects.filter(product=product, is_active=True).first()
#                 category_offer = CategoryOffer.objects.filter(category=product.category, is_active=True).first()
#                 final_price = product.price
#                 if product_offer and category_offer:
#                     final_price = min(
#                         product.price * (1 - product_offer.discount_percentage / 100),
#                         product.price * (1 - category_offer.discount_percentage / 100)
#                     )
#                 elif product_offer:
#                     final_price = product.price * (1 - product_offer.discount_percentage / 100)
#                 elif category_offer:
#                     final_price = product.price * (1 - category_offer.discount_percentage / 100)

#                 OrderItem.objects.create(
#                     order=order,
#                     product=item.product_variant.product,
#                     product_variant=item.product_variant,
#                     quantity=item.quantity,
#                     status=order_item_status,
#                     price=final_price,
#                     final_offer_price=final_price
#                 )

#             if coupon:
#                 CouponUsage.objects.create(user=user, coupon=coupon)

#             request.session['cart_details'] = {'order_id': order.id}

#             if payment_method in ["COD", "wallet"]:
#                 if payment_method == "wallet":
#                     wallet = Wallet.objects.get(user=user)
#                     if wallet.balance < grand_total:
#                         order.delete()
#                         return JsonResponse({"error": "Insufficient funds in wallet."}, status=400)
#                     wallet.balance -= grand_total
#                     wallet.save()

#                 cart_items.delete()
#                 del request.session['cart_details']
#                 del request.session['coupon_code']  # Clear coupon after use
#                 return JsonResponse({"redirect": reverse('order_success', args=[order.id])})
#             elif payment_method == "razorpay":
#                 return JsonResponse({"redirect": reverse('payments:initiate_payment')})

#         except Exception as e:
#             return JsonResponse({"error": str(e)}, status=400)

#     context = {
#         'addresses': addresses,
#         'default_address': default_address,
#         'cart_items': cart_items,
#         'total_listed_price': total_listed_price,
#         'total_offer_price': total_offer_price,
#         'discounted_amount': discounted_amount,
#         'delivery_charge': delivery_charge,
#         'grand_total': grand_total,
#         'coupon_discount': coupon_discount
#     }
#     return render(request, 'user/checkout.html', context)








"""
ORDER SUCCESS
"""
@login_required
def order_success(request,order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)
    order_items = order.items.all()

    total_listed_price = Decimal('0.00')
    total_offer_price = Decimal('0.00')
    for item in order_items:
        product = item.product
        product_offer = ProductOffer.objects.filter(product=product, is_active=True).first()
        category_offer = CategoryOffer.objects.filter(category=product.category, is_active=True).first()

        # Calculate the final price based on the best offer
        if product_offer and category_offer:
            final_price = min(
                product.price * (1 - product_offer.discount_percentage / 100),
                product.price * (1 - category_offer.discount_percentage / 100)
            )
        elif product_offer:
            final_price = product.price * (1 - product_offer.discount_percentage / 100)
        elif category_offer:
            final_price = product.price * (1 - category_offer.discount_percentage / 100)
        else:
            final_price = product.price
        

        quantity = Decimal(str(item.quantity))
        total_listed_price += product.price * quantity
        total_offer_price += final_price * quantity


        #Use the total_price from the Order model
        grand_total = order.total_price

        # Clear the entered coupon code from the session after the order is successfully placed
    if 'entered_coupon_code' in request.session:
        del request.session['entered_coupon_code']

        # Determine is_success based on payment method and status
    if order.payment_method == 'COD':
        is_success = True  
    elif order.payment_method == 'razorpay':
        is_success = order.payment_status == 'Paid'  
    elif order.payment_method == 'wallet':
        is_success = order.payment_status == 'Paid' 
    else:
        is_success = False  



    context = {
        'order_number':order_id,
        'grand_total': grand_total,
        'payment_status': order.payment_status,
        'show_retry_button': order.payment_status == 'Processing' and order.payment_method == 'razorpay',
        'is_success': is_success
    }    


    return render(request, 'user/order_confirm.html',context)







"""
USER SIDE ORDERS LISTING PAGE
"""
@login_required
def user_orders(request):
    orders = Order.objects.filter(user=request.user).order_by('-created_at')
    
    page = request.GET.get('page', 1)
    paginator = Paginator(orders, 10)

    try:
        orders = paginator.page(page)
    except PageNotAnInteger:
        orders = paginator.page(1)
    except EmptyPage:
        orders = paginator.page(paginator.num_pages)

    return render(request, 'user/orders_list.html', {'orders': orders})






"""
USER SIDE ORDER ITEMS LISTING PAGE
"""
@login_required
def order_items(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)
    order_items = order.items.all()
    
    page = request.GET.get('page', 1)
    paginator = Paginator(order_items, 10)
    try:
        order_items = paginator.page(page)
    except PageNotAnInteger:
        order_items = paginator.page(1)
    except EmptyPage:
        order_items = paginator.page(paginator.num_pages)

    return render(request, 'user/order_items.html', {'order': order, 'order_items': order_items})








@login_required
def user_order_details(request, item_id):
    particular_product = get_object_or_404(OrderItem, id=item_id, order__user=request.user)
    order = particular_product.order
    order_items = order.items.all()

    total_listed_price = Decimal('0.00')
    total_offer_price = Decimal('0.00')
    for item in order_items:
        total_listed_price += item.product.price * Decimal(str(item.quantity))
        total_offer_price += item.final_offer_price * Decimal(str(item.quantity))

    delivery_charge = Decimal('40.00') if total_offer_price < Decimal('1000.00') else Decimal('0.00')
    coupon_discount = order.discount_coupon_amount
    grand_total = total_offer_price + delivery_charge - coupon_discount

    current_time = timezone.now()
    days_since_delivery = (current_time - particular_product.updated_at).days

    return render(request, 'user/order_details.html', {
        'order': order,
        'particular_product': particular_product,
        'other_products_in_order': order_items.exclude(id=particular_product.id),
        'total_listed_price': total_listed_price,
        'total_offer_price': total_offer_price,
        'discounted_amount': total_listed_price - total_offer_price,
        'delivery_charge': delivery_charge,
        'grand_total': grand_total,
        'coupon_discount': coupon_discount,
        'days_since_delivery': days_since_delivery,
    })










# """
# USER SIDE ORDER ITEM DETAILS LISTING PAGE
# """
# @login_required
# def user_order_details(request, item_id):
#     particular_product = get_object_or_404(OrderItem, id=item_id, order__user=request.user)
#     order = particular_product.order
#     order_items = order.items.all()

#     total_listed_price = Decimal('0.00')
#     total_offer_price = Decimal('0.00')
#     for item in order_items:
#         product = item.product
#         product_offer = ProductOffer.objects.filter(product=product, is_active=True).first()
#         category_offer = CategoryOffer.objects.filter(category=product.category, is_active=True).first()

#         # # Calculate the final price based on the best offer
#         if product_offer and category_offer:
#             final_price = min(
#                 product.price * (1 - product_offer.discount_percentage / 100),
#                 product.price * (1 - category_offer.discount_percentage / 100)
#             )
#         elif product_offer:
#             final_price = product.price * (1 - product_offer.discount_percentage / 100)
#         elif category_offer:
#             final_price = product.price * (1 - category_offer.discount_percentage / 100)
#         else:
#             final_price = product.price


#         quantity = Decimal(str(item.quantity))
#         item.subtotal_listed_price = product.price * quantity
#         item.subtotal_offer_price = final_price * quantity
#         total_listed_price += item.subtotal_listed_price
#         total_offer_price += item.subtotal_offer_price

#     discounted_amount = total_listed_price - total_offer_price
#     delivery_charge = Decimal('40.00') if total_offer_price < Decimal('1000.00') else Decimal('0.00')
#     grand_total = total_offer_price + delivery_charge

#     # Calculate coupon discount
#     coupon_discount = Decimal('0.00')
#     if order.coupon:
#         coupon_discount = order.discount_coupon_amount
#         grand_total -= coupon_discount
#         discounted_amount += coupon_discount

#     other_products_in_order = order_items.exclude(id=particular_product.id)

#     current_time = timezone.now()
#     days_since_delivery = (current_time - particular_product.updated_at).days

#     return render(request, 'user/order_details.html', {
#         'order': order,
#         'particular_product': particular_product,
#         'other_products_in_order': other_products_in_order,
#         'total_listed_price': total_listed_price,
#         'total_offer_price': total_offer_price,
#         'discounted_amount': discounted_amount,
#         'delivery_charge': delivery_charge,
#         'grand_total': grand_total,
#         'coupon_discount': coupon_discount,
#         'days_since_delivery': days_since_delivery,
#     })








"""
CANCEL OPTION FOR USER
"""
@login_required
def cancel_order_item(request, item_id):
    order_item = get_object_or_404(OrderItem, id=item_id, order__user=request.user)

    if order_item.status in ['out_for_delivery', 'delivered', 'canceled']:
        return JsonResponse({
            "error": "This item cannot be canceled as it is already out for delivery, delivered, or canceled."
        }, status=400)

    if request.method == "POST":
        cancel_reason = request.POST.get("cancel_reason")
        if cancel_reason:
            product_variant = order_item.product_variant
            product_variant.stock += order_item.quantity
            product_variant.save()

            # Filter desired statuses
            desired_statuses = [
                'order_placed',
                'shipped',
                'out_for_delivery',
                'delivered',
                'return_requested',
                'return_denied'
            ]

            # Get all items in the order (including all status items)
            original_order_items = order_item.order.items.all()

            # Filter full_order_items and remaining_order_items
            full_order_items = OrderItem.objects.filter(
                order=order_item.order,
                status__in=desired_statuses
            )
            full_total_price = sum(item.price * item.quantity for item in full_order_items)

            remaining_order_items = OrderItem.objects.filter(
                order=order_item.order,
                status__in=desired_statuses
            ).exclude(id=order_item.id)

            remaining_total_price = sum(item.price * item.quantity for item in remaining_order_items)

            coupon = order_item.order.coupon
            refund_amount = Decimal('0.00')

            if coupon:
                total_discount = (coupon.discount_percentage / Decimal('100.00')) * full_total_price

                order_total_coupon_discount = order_item.order.discount_coupon_amount

                # Distribute the discount evenly across all items in the original order
                discount_per_item = order_total_coupon_discount / len(original_order_items)

                if order_total_coupon_discount == coupon.max_discount_amount:
                    if remaining_total_price < coupon.minimum_purchase_amount:
                        balance_refund_amount = order_item.order.balance_refund
                        if balance_refund_amount == 0:
                            refund_amount = order_item.price * order_item.quantity
                        else:
                            refund_amount = (order_item.price * order_item.quantity) - balance_refund_amount
                            order_item.order.balance_refund -= balance_refund_amount
                    else:
                        refund_amount = (order_item.price * order_item.quantity) - discount_per_item
                        order_item.order.balance_refund -= discount_per_item
                else:
                    if remaining_total_price < coupon.minimum_purchase_amount:
                        if not order_item.order.discount_applied:
                            refund_amount = (order_item.price * order_item.quantity) - total_discount
                            order_item.order.discount_applied = True
                        else:
                            refund_amount = order_item.price * order_item.quantity
                    else:
                        refund_amount = (order_item.price * order_item.quantity) - (
                            (coupon.discount_percentage / Decimal('100.00')) * order_item.price * order_item.quantity
                        )
                order_item.order.save()
            else:
                refund_amount = order_item.price * order_item.quantity
            

            order_item.status = 'canceled'
            order_item.cancel_reason = cancel_reason
            order_item.save()

            # Update the order status
            order_item.order.update_order()

            refund_amount = max(refund_amount, Decimal('0.00'))

            # Credit wallet for non COD payments
            if order_item.order.payment_method != 'COD':
                wallet, created = Wallet.objects.get_or_create(user=request.user)
                wallet.balance += refund_amount
                wallet.save()

                WalletTransaction.objects.create(
                    wallet=wallet,
                    order=order_item.order,
                    amount=refund_amount,
                    transaction_type='credit'
                )

            return JsonResponse({
                "success": True,
                "message": "Order item canceled successfully.",
                "redirect_url": reverse('user_order_details', args=[order_item.id])
            })
        else:
            return JsonResponse({"error": "Please provide a reason for cancellation."}, status=400)

    return render(request, 'user/cancel_reason.html', {'order_item': order_item})







"""
RETURN REQUEST - USER
"""
@login_required
def request_return(request, item_id):
    order_item = get_object_or_404(OrderItem, id=item_id, order__user=request.user)

    # Check if the item is eligible for return delivered within 7 days
    if order_item.status != 'delivered' or (timezone.now() - order_item.updated_at).days > 7:
        messages.error(request, "This item is not eligible for return.")
        return redirect('user_order_details', item_id=item_id)

    if request.method == "POST":
        return_reason = request.POST.get("return_reason")
        if return_reason:
            order_item.status = 'return_requested'
            order_item.return_reason = return_reason
            order_item.return_requested_at = timezone.now()
            order_item.save()

            messages.success(request, "Return request submitted successfully.")
            return redirect('user_order_details', item_id=item_id)
        else:
            messages.error(request, "Please provide a reason for return.")
            return redirect('request_return', item_id=item_id)

    return render(request, 'user/return_reason.html', {'order_item': order_item})








"""
DOWNLOAD INVOICE
"""
def download_invoice(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    order_items = order.items.all()
    
    # Check if invoice is allowed for this order
    allowed_statuses = ['delivered', 'return_requested', 'return_denied', 'returned']
    if not order_items.filter(status__in=allowed_statuses).exists():
        return redirect('user_order_details')

    # Calculate values for the invoice
    total_listed_price = Decimal('0.00')
    total_offer_price = Decimal('0.00')
    for item in order_items:
        product = item.product
        product_offer = ProductOffer.objects.filter(product=product, is_active=True).first()
        category_offer = CategoryOffer.objects.filter(category=product.category, is_active=True).first()

        # Calculate the final price based on the best offer
        if product_offer and category_offer:
            final_price = min(
                product.price * (1 - product_offer.discount_percentage / 100),
                product.price * (1 - category_offer.discount_percentage / 100)
            )
        elif product_offer:
            final_price = product.price * (1 - product_offer.discount_percentage / 100)
        elif category_offer:
            final_price = product.price * (1 - category_offer.discount_percentage / 100)
        else:
            final_price = product.price
        

        quantity = Decimal(str(item.quantity))
        total_listed_price += product.price * quantity
        total_offer_price += final_price * quantity

    delivery_charge = Decimal('40.00') if total_offer_price < Decimal('1000.00') else Decimal('0.00')
    coupon_discount = order.discount_coupon_amount
    
    grand_total = (total_offer_price - coupon_discount) + delivery_charge

    # Prepare order items with calculated values
    processed_items = []
    for item in order_items:
        product = item.product
        product_offer = ProductOffer.objects.filter(product=product, is_active=True).first()
        category_offer = CategoryOffer.objects.filter(category=product.category, is_active=True).first()

        # Calculate the final price based on the best offer
        if product_offer and category_offer:
            final_price = min(
                product.price * (1 - product_offer.discount_percentage / 100),
                product.price * (1 - category_offer.discount_percentage / 100)
            )
        elif product_offer:
            final_price = product.price * (1 - product_offer.discount_percentage / 100)
        elif category_offer:
            final_price = product.price * (1 - category_offer.discount_percentage / 100)
        else:
            final_price = product.price
        

        quantity = item.quantity
        item_offer_total = final_price * quantity
        
        # Calculate coupon discount for this item proportionally
        item_coupon_discount = Decimal('0.00')
        if total_offer_price > 0 and coupon_discount > 0:
            item_coupon_discount = (item_offer_total / total_offer_price) * coupon_discount
        
        discounted_price = final_price - (item_coupon_discount / quantity)
        
        processed_items.append({
            'name': item.product.name,
            'quantity': quantity,
            'listed_price': product.price,
            'offer_price': final_price,
            'coupon_discount': item_coupon_discount.quantize(Decimal('0.00')),
            'discount': discounted_price,
            'subtotal': (final_price * quantity) - item_coupon_discount,
        })

    context = {
        'order': order,
        'order_items': processed_items,
        'delivery_charge': delivery_charge,
        'coupon_discount': coupon_discount.quantize(Decimal('0.00')),
        'grand_total': grand_total.quantize(Decimal('0.00')),
        'total_offer_price': total_offer_price.quantize(Decimal('0.00')),
        'total_listed_price': total_listed_price.quantize(Decimal('0.00')),
    }

    # Generate PDF
    html_string = render_to_string('user/invoice_template.html', context)
    html = HTML(string=html_string)
    pdf = html.write_pdf()

    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="invoice_{order.id}.pdf"'
    return response






###############################################USER SIDE END###############################################



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
ORDERS LIST
"""
@admin_required
@never_cache
@user_passes_test(is_admin)
def order_management(request):
    orders = Order.objects.all().order_by('-created_at')

    page = request.GET.get('page', 1) 
    paginator = Paginator(orders, 10) 

    try:
        orders = paginator.page(page)
    except PageNotAnInteger:
        orders = paginator.page(1)
    except EmptyPage:
        orders = paginator.page(paginator.num_pages)

    return render(request, 'admin/order_admin.html', {'orders': orders})


"""
ORDER DETAILS
"""
@admin_required
@never_cache
@user_passes_test(is_admin)
def admin_order_details(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    order_items = order.items.all()

    for item in order_items:
        product = item.product
        product_offer = ProductOffer.objects.filter(product=product, is_active=True).first()
        category_offer = CategoryOffer.objects.filter(category=product.category, is_active=True).first()

        #Calculate the final price based on the best offer
        if product_offer and category_offer:
            final_price = min(
                product.price * (1 - product_offer.discount_percentage / 100),
                product.price * (1 - category_offer.discount_percentage / 100)
            )
        elif product_offer:
            final_price = product.price * (1 - product_offer.discount_percentage / 100)
        elif category_offer:
            final_price = product.price * (1 - category_offer.discount_percentage / 100)
        else:
            final_price = product.price
        

        item.final_price = final_price
        item.subtotal = item.quantity * final_price

    status_choices = OrderItem.ORDER_ITEM_STATUS_CHOICES

    page = request.GET.get('page', 1)
    paginator = Paginator(order_items, 10)

    try:
        order_items = paginator.page(page)
    except PageNotAnInteger:
        order_items = paginator.page(1)
    except EmptyPage:
        order_items = paginator.page(paginator.num_pages)

    return render(request, 'admin/order_details_admin.html', {
        'order': order,
        'order_items': order_items,
        'status_choices': status_choices,
    })







"""
STATUS UPDATE
"""
@admin_required
@never_cache
@user_passes_test(is_admin)
@require_POST
def update_order_status(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    item_id = request.POST.get('item_id')
    new_status = request.POST.get('status')

    if not item_id or not new_status:
        return JsonResponse({"error": "Invalid request."}, status=400)

    order_item = get_object_or_404(OrderItem, id=item_id, order=order)

    # Check if the new status is allowed using the can_update_status method
    if not order_item.can_update_status(new_status):
        return JsonResponse({"error": f"Cannot update status from {order_item.status} to {new_status}."}, status=400)

    if new_status == 'return_requested':
        return JsonResponse({"error": "Admins cannot directly request returns. Only users can request returns."}, status=400)

    # Update the item status
    order_item.status = new_status
    order_item.save()

    # If the order is delivered and payment method is COD, update payment status to Paid
    if new_status == 'delivered' and order.payment_method == 'COD':
        order.payment_status = 'Paid'
        order.save()

    if new_status == 'return':
        # Refill stock and credit amount to wallet if the status is updated to return
        product_variant = order_item.product_variant
        product_variant.stock += order_item.quantity
        product_variant.save()
        order_item.returned_at = timezone.now()

        # Filter desired statuses
        desired_statuses = [
            'order_placed',
            'shipped',
            'out_for_delivery',
            'delivered',
            'return_requested',
            'return',
            'return_denied'
        ]

        # Get all items in the order (including all status items)
        original_order_items = order_item.order.items.all()

        # Filter full_order_items and remaining_order_items
        full_order_items = OrderItem.objects.filter(
            order=order_item.order,
            status__in=desired_statuses
        )
        full_total_price = sum(item.price * item.quantity for item in full_order_items)

        remaining_order_items = OrderItem.objects.filter(
            order=order_item.order,
            status__in=desired_statuses
        ).exclude(id=order_item.id)

        remaining_total_price = sum(item.price * item.quantity for item in remaining_order_items)

        coupon = order_item.order.coupon
        refund_amount = Decimal('0.00')

        if coupon:
            total_discount = (coupon.discount_percentage / Decimal('100.00')) * full_total_price

            order_total_coupon_discount = order_item.order.discount_coupon_amount

            discount_per_item = order_total_coupon_discount / len(original_order_items)
            if order_total_coupon_discount == coupon.max_discount_amount:
                    if remaining_total_price < coupon.minimum_purchase_amount:
                        balance_refund_amount = order_item.order.balance_refund
                        if balance_refund_amount == 0:
                            refund_amount = order_item.price * order_item.quantity
                        else:
                            refund_amount = (order_item.price * order_item.quantity) - balance_refund_amount
                            order_item.order.balance_refund -= balance_refund_amount
                    else:
                        refund_amount = (order_item.price * order_item.quantity) - discount_per_item
                        order_item.order.balance_refund -= discount_per_item
            else:
                if remaining_total_price < coupon.minimum_purchase_amount:
                    if not order_item.order.discount_applied:
                        refund_amount = (order_item.price * order_item.quantity) - total_discount
                        order_item.order.discount_applied = True
                        order_item.order.save(update_fields=['discount_applied'])  
                        order_item.order.refresh_from_db()
                    else:
                        refund_amount = order_item.price * order_item.quantity
                else:
                    refund_amount = (order_item.price * order_item.quantity) - (
                        (coupon.discount_percentage / Decimal('100.00')) *
                        order_item.price *
                        order_item.quantity
                    )
            order_item.order.save()
        else:
            refund_amount = order_item.price * order_item.quantity
        

        order_item.status = 'returned'
        order_item.save()
        refund_amount = max(refund_amount, Decimal('0.00'))

        # Credit amount to wallet for online, COD, and wallet payment methods
        wallet, created = Wallet.objects.get_or_create(user=order.user)
        wallet.balance += refund_amount
        wallet.save()

        WalletTransaction.objects.create(
            wallet=wallet,
            order=order_item.order,
            amount=refund_amount,
            transaction_type='credit'
        )
    else:
        pass

    # Update the order status
    order.update_order()
    order.refresh_from_db()

    return JsonResponse({
        "success": True,
        "message": "Order item status updated successfully.",
        "redirect_url": reverse('admin_order_details', args=[order.id])
    })


###############################################ADMIN SIDE END###############################################
