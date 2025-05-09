from django.shortcuts import render,redirect
from django.views.decorators.cache import never_cache
from category.models import Category
from products.models import Product
import random
from django.core.mail import EmailMessage
from django.conf import settings
from .forms import ContactForm
from django.middleware.csrf import get_token

# Create your views here.




@never_cache
def HomePage(request):
    categories = Category.objects.filter(is_listed=True)

    # Fetch the latest 4 products 
    latest_products = list(Product.objects.filter(is_listed=True).order_by('-created_at')[:4])

    # Randomly shuffle the products to show them in random order
    random_products = random.sample(latest_products, min(len(latest_products), 4))




    # Fetch the latest 4 products 
    popular_products = list(Product.objects.filter(is_listed=True).order_by('created_at')[:4])

    # Randomly shuffle the products to show them in random order
    random_popular_products = random.sample(popular_products, min(len(popular_products), 4))





    # Fetch the latest 4 products 
    bestseller_products = list(Product.objects.filter(is_listed=True).order_by('created_at')[:9])

    # Randomly shuffle the products to show them in random order
    random_bestseller_products = random.sample(bestseller_products, min(len(bestseller_products), 9))





    # Fetch the latest 4 products 
    newarrival_products = list(Product.objects.filter(is_listed=True).order_by('created_at')[:4])

    # Randomly shuffle the products to show them in random order
    random_newarrival_products = random.sample(newarrival_products, min(len(newarrival_products), 4))

    context = {
        'categories': categories,
        'random_products': random_products,
        'random_popular_products': random_popular_products,
        'random_bestseller_products': random_bestseller_products,
        'random_newarrival_products': random_newarrival_products,
        'csrf_token': get_token(request),
    }



    return render(request, 'user/index.html', context)






"""
ABOUT PAGE
"""
@never_cache
def about(request):
    return render(request, 'user/about.html')






"""
CONTACT US PAGE
"""
@never_cache
def contact(request):
    if request.method == 'POST':
        form = ContactForm(request.POST)
        if form.is_valid():
            name = form.cleaned_data['name']
            email = form.cleaned_data['email']
            subject = form.cleaned_data['subject']
            message = form.cleaned_data['message']

            email_message = EmailMessage(
                subject=f"Contact Form: {subject}",
                body=f"Message from {name} ({email}):\n\n{message}",
                from_email=email, 
                to=[settings.CONTACT_EMAIL],
                reply_to=[email],
            )

            email_message.send()

            return redirect('contact_success')
    else:
        form = ContactForm()

    return render(request, 'user/contact.html', {'form': form})


"""
CONTACT SUCCESS PAGE
"""
def contact_success(request):
    return render(request, 'user/contact_success.html')






