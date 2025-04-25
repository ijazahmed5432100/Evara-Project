import razorpay
from django.shortcuts import render, redirect,get_object_or_404
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse, HttpResponseBadRequest
from orders.models import Order, OrderItem
from cart.models import Cart, CartItem
from django.contrib import messages
from django.urls import reverse
import logging

logger = logging.getLogger(__name__)

# Initialize Razorpay client
razorpay_client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))

@csrf_exempt
def initiate_payment(request):
    """Initiate Razorpay payment for an existing order."""
    if request.method != "POST":
        return JsonResponse({"error": "Invalid request method"}, status=405)

    try:
        user = request.user
        cart_details = request.session.get('cart_details', {})
        order_id = cart_details.get('order_id')
        if not order_id:
            return JsonResponse({"error": "Order not found in session"}, status=400)

        order = Order.objects.get(id=order_id, user=user)
        if order.payment_method != "razorpay":
            return JsonResponse({"error": "Invalid payment method for this order"}, status=400)

        amount = int(order.total_price * 100)  # Convert to paise
        razorpay_order = razorpay_client.order.create({
            "amount": amount,
            "currency": "INR",
            "receipt": f"order_{order.id}",
            "notes": {"django_order_id": order.id, "user_id": user.id},
            "payment_capture": "1"  # Auto-capture payment
        })

        order.razorpay_order_id = razorpay_order['id']
        order.retry_payment_attempts += 1
        order.save()

        callback_url = request.build_absolute_uri(reverse('payments:verify_payment', args=[order.id]))
        return JsonResponse({
            "razorpay_order_id": razorpay_order["id"],
            "django_order_id": order.id,
            "razorpay_merchant_key": settings.RAZORPAY_KEY_ID,
            "razorpay_amount": amount,
            "currency": "INR",
            "callback_url": callback_url,
        })
    except Order.DoesNotExist:
        logger.error("Order not found for payment initiation")
        return JsonResponse({"error": "Order not found"}, status=404)
    except Exception as e:
        logger.error(f"Error in initiate_payment: {str(e)}")
        return JsonResponse({"error": str(e)}, status=500)








@csrf_exempt
def verify_payment(request, order_id):
    """Verify Razorpay payment and finalize order."""
    if request.method != "POST":
        return HttpResponseBadRequest("Invalid request method")

    try:
        payment_id = request.POST.get('razorpay_payment_id', '')
        razorpay_order_id = request.POST.get('razorpay_order_id', '')
        signature = request.POST.get('razorpay_signature', '')

        if not all([payment_id, razorpay_order_id, signature]):
            messages.error(request, "Missing payment data")
            return redirect('payments:payment_failure', order_id=order_id)

        params_dict = {
            'razorpay_order_id': razorpay_order_id,
            'razorpay_payment_id': payment_id,
            'razorpay_signature': signature
        }

        razorpay_client.utility.verify_payment_signature(params_dict)
        order = Order.objects.get(id=order_id, user=request.user)
        payment = razorpay_client.payment.fetch(payment_id)

        if payment['status'] == 'captured':
            order.payment_status = 'Paid'
            order.status = 'pending'  # Or 'completed' based on your workflow
            order.save()

            for item in order.items.all():
                item.status = 'order_placed'  # Update item status
                item.save()

            # Clear cart only if this is the initial payment (not a retry)
            if order.retry_payment_attempts == 1:
                cart = Cart.objects.get(user=order.user)
                CartItem.objects.filter(cart=cart).delete()
                if 'cart_details' in request.session:
                    del request.session['cart_details']

            return redirect(reverse('payments:retry_order_confirm', args=[order.id]))
        else:
            order.payment_status = 'Pending'
            order.save()
            messages.error(request, "Payment not captured")
            return redirect('payments:payment_failure', order_id=order_id)
    except razorpay.errors.SignatureVerificationError:
        messages.error(request, "Payment verification failed")
        return redirect('payments:payment_failure', order_id=order_id)
    except Exception as e:
        logger.error(f"Error in verify_payment: {str(e)}")
        order = Order.objects.get(id=order_id, user=request.user)
        order.payment_status = 'Pending'
        order.save()
        messages.error(request, "Payment failed")
        return redirect('payments:payment_failure', order_id=order_id)









# @csrf_exempt
# def verify_payment(request, order_id):
#     """Verify Razorpay payment and finalize order."""
#     if request.method != "POST":
#         return HttpResponseBadRequest("Invalid request method")

#     try:
#         payment_id = request.POST.get('razorpay_payment_id', '')
#         razorpay_order_id = request.POST.get('razorpay_order_id', '')
#         signature = request.POST.get('razorpay_signature', '')

#         if not all([payment_id, razorpay_order_id, signature]):
#             messages.error(request, "Missing payment data")
#             return redirect('payments:payment_failure', order_id=order_id)

#         params_dict = {
#             'razorpay_order_id': razorpay_order_id,
#             'razorpay_payment_id': payment_id,
#             'razorpay_signature': signature
#         }

#         razorpay_client.utility.verify_payment_signature(params_dict)
#         order = Order.objects.get(id=order_id, user=request.user)
#         payment = razorpay_client.payment.fetch(payment_id)

#         if payment['status'] == 'captured':
#             order.payment_status = 'Paid'
#             order.status = 'pending'
#             order.save()

#             for item in order.items.all():
#                 item.status = 'order_placed'
#                 item.save()

#             cart = Cart.objects.get(user=order.user)
#             CartItem.objects.filter(cart=cart).delete()

#             if 'cart_details' in request.session:
#                 del request.session['cart_details']

#             return redirect('payments:payment_success', order_id=order.id)
#         else:
#             order.payment_status = 'Pending'
#             order.save()
#             messages.error(request, "Payment not captured")
#             return redirect('payments:payment_failure', order_id=order_id)
#     except razorpay.errors.SignatureVerificationError:
#         messages.error(request, "Payment verification failed")
#         return redirect('payments:payment_failure', order_id=order_id)
#     except Exception as e:
#         logger.error(f"Error in verify_payment: {str(e)}")
#         order = Order.objects.get(id=order_id, user=request.user)
#         order.payment_status = 'Pending'
#         order.save()
#         messages.error(request, "Payment failed")
#         return redirect('payments:payment_failure', order_id=order_id)




def payment_success(request, order_id):
    """Display payment success page."""
    order = Order.objects.get(id=order_id, user=request.user)
    context = {
        'order_number': order.id,
        'grand_total': order.total_price,
        'payment_status': order.payment_status,
        'show_retry_button': False,  # No retry needed on success
        'is_success': True  # Add this to indicate success
    }
    return render(request, 'user/order_confirm.html',context)







def payment_failure(request, order_id):
    """Display payment failure page."""
    order = Order.objects.get(id=order_id, user=request.user)
    context = {
        'order_number': order.id,
        'grand_total': order.total_price,
        'payment_status': order.payment_status,
        'show_retry_button': order.payment_method == 'razorpay' and order.payment_status != 'Paid',
        'is_success': False  # Add this to indicate failure
    }
    return render(request, 'user/order_confirm.html',context)









def retry_payment(request, order_id):
    """Initiate a retry for a Razorpay payment."""
    order = get_object_or_404(Order, id=order_id, user=request.user)
    if request.method == "POST":
        if order.payment_method != "razorpay" or order.payment_status != "Pending":
            messages.error(request, "Retry is not available for this order.")
            return redirect('user_orders')

        amount = int(order.total_price * 100)  # Convert to paise
        try:
            razorpay_order = razorpay_client.order.create({
                "amount": amount,
                "currency": "INR",
                "receipt": f"retry_order_{order.id}",
                "notes": {"django_order_id": order.id, "user_id": request.user.id},
                "payment_capture": "1"  # Auto-capture payment
            })

            order.razorpay_order_id = razorpay_order['id']
            order.retry_payment_attempts += 1
            order.save()

            callback_url = request.build_absolute_uri(reverse('payments:verify_payment', args=[order.id]))
            return JsonResponse({
                "razorpay_order_id": razorpay_order["id"],
                "razorpay_merchant_key": settings.RAZORPAY_KEY_ID,
                "razorpay_amount": amount,
                "currency": "INR",
                "callback_url": callback_url,
                "order_id": order.id
            })
        except Exception as e:
            logger.error(f"Error in retry_payment: {str(e)}")
            return JsonResponse({"error": "Failed to initiate retry payment."}, status=500)
    else:
        return render(request, 'user/retry_payment_confirmation.html', {'order': order})
    





def retry_order_confirm(request, order_id):
    """Display retry payment success page."""
    order = Order.objects.get(id=order_id, user=request.user)
    context = {
        'order_number': order.id,
        'grand_total': order.total_price,
        'payment_status': order.payment_status,
    }
    return render(request, 'user/retry_order_confirm.html', context)


