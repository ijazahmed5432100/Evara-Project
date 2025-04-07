from django.shortcuts import render
from django.views.decorators.cache import never_cache
from category.models import Category
from products.models import Product
import random

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
    }



    return render(request, 'user/index.html', context)







