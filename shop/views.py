from django.shortcuts import render
from products.models import Product, ProductImage
from category.models import Category
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.views.decorators.cache import never_cache

# Create your views here.




"""
SHOP OR ALL PRODUCT LISTING PAGE
"""
@never_cache
def all_products(request):
    categories = Category.objects.filter(is_listed=True)
    products = Product.objects.filter(is_listed=True, category__in=categories).prefetch_related('images') # Take all the products
    

    # Search
    search_query = request.GET.get('search', '')
    if search_query:
        products = products.filter(name__icontains=search_query)

    # Filtering
    selected_categories = request.GET.getlist('categories')  # Retrieve list of selected category IDs
    selected_categories = [int(cat) for cat in selected_categories if cat.isdigit()]  # Convert to int safely
    if selected_categories:
        products = products.filter(category__id__in=selected_categories)


    

    min_price = request.GET.get('min_price', '')
    max_price = request.GET.get('max_price', '')

    if min_price.isdigit():
        products = products.filter(price__gte=int(min_price))
    if max_price.isdigit():
        products = products.filter(price__lte=int(max_price))




    # Sortingy
    sort_option = request.GET.get('sort', '')
    if sort_option == 'name-asc':
        products = products.order_by('name')
    elif sort_option == 'name-desc':
        products = products.order_by('-name')
    elif sort_option == 'price-asc':
        products = products.order_by('price')
    elif sort_option == 'price-desc':
        products = products.order_by('-price')

    paginator = Paginator(products, 12)
    page = request.GET.get('page')
    try:
        products = paginator.page(page)
    except PageNotAnInteger:
        products = paginator.page(1)
    except EmptyPage:
        products = paginator.page(paginator.num_pages)

    context = {
        'products': [{
            'product': product,
            'first_image': product.images.first()  # Fetch the first image
        } for product in products],
        'categories': categories,
        'selected_categories': [int(cat) for cat in selected_categories],
        'search_query': search_query,
        'sort_option': sort_option,
        'page_obj': products,  # pagination object to context
        'min_price':min_price,
        'max_price':max_price,
    }

    return render(request, 'user/shop.html', context)

