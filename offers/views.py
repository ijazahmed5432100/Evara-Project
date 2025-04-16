from django.shortcuts import render,redirect,get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from .models import ProductOffer,CategoryOffer
from django.core.paginator import Paginator
from django.contrib import messages
from products.models import Product
from category.models import Category



# Create your views here.






"""
ADMIN CHECK
"""
def is_admin(user):
    return user.is_authenticated and user.is_superuser





"""
OFFER MANAGEMENT 
"""
@user_passes_test(is_admin)
def offer_management(request):
    return render(request, 'admin/offer_management.html')




"""
PRODUCT OFFER LISTING 
"""
@user_passes_test(lambda u: u.is_superuser)
def product_offer_list(request):
    query = request.GET.get('q')
    product_offers_list = ProductOffer.objects.all()
    if query:
        product_offers_list = product_offers_list.filter(product__name__icontains=query)
    paginator = Paginator(product_offers_list, 10)
    page_number = request.GET.get('page')
    product_offers = paginator.get_page(page_number)
    return render(request, 'admin/product_offer_list.html', {'product_offers': product_offers})




"""
ADD PRODUCT OFFER
"""
@user_passes_test(lambda u: u.is_superuser)
def add_product_offer(request, product_id=None):
    products = Product.objects.all()
    if request.method == 'POST':
        product_id = request.POST.get('product')
        discount_percentage = request.POST.get('discount_percentage')
        
        # Validation
        if not product_id or not discount_percentage:
            messages.error(request, 'Product and discount percentage are required.')
            return render(request, 'admin/add_product_offer.html', {
                'products': products,
                'selected_product': product_id,
                'discount_percentage': discount_percentage
            })
        
        try:
            discount_percentage = float(discount_percentage)
            if discount_percentage < 0 or discount_percentage > 100:
                messages.error(request, 'Discount percentage must be between 0 and 100.')
                return render(request, 'admin/add_product_offer.html', {
                    'products': products,
                    'selected_product': product_id,
                    'discount_percentage': discount_percentage
                })
        except ValueError:
            messages.error(request, 'Invalid discount percentage.')
            return render(request, 'admin/add_product_offer.html', {
                'products': products,
                'selected_product': product_id,
                'discount_percentage': discount_percentage
            })
        
        product = get_object_or_404(Product, id=product_id)
        if ProductOffer.objects.filter(product=product).exists():
            messages.error(request, 'An offer already exists for this product.')
            return render(request, 'admin/add_product_offer.html', {
                'products': products,
                'selected_product': product_id,
                'discount_percentage': discount_percentage
            })
        
        ProductOffer.objects.create(
            product=product,
            discount_percentage=discount_percentage,
            is_active=True
        )
        messages.success(request, 'Product offer added successfully.')
        return redirect('product_offer_list')
    
    return render(request, 'admin/add_product_offer.html', {'products': products})


"""
EDIT PRODUCT OFFER
"""
@user_passes_test(lambda u: u.is_superuser)
def edit_product_offer(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    product_offer = get_object_or_404(ProductOffer, product=product)
    products = Product.objects.all()
    
    if request.method == 'POST':
        new_product_id = request.POST.get('product')
        discount_percentage = request.POST.get('discount_percentage')
        
        # Validation
        if not new_product_id or not discount_percentage:
            messages.error(request, 'Product and discount percentage are required.')
            return render(request, 'admin/edit_product_offer.html', {
                'product_offer': product_offer,
                'product': product,
                'products': products
            })
        
        try:
            discount_percentage = float(discount_percentage)
            if discount_percentage < 0 or discount_percentage > 100:
                messages.error(request, 'Discount percentage must be between 0 and 100.')
                return render(request, 'admin/edit_product_offer.html', {
                    'product_offer': product_offer,
                    'product': product,
                    'products': products
                })
        except ValueError:
            messages.error(request, 'Invalid discount percentage.')
            return render(request, 'admin/edit_product_offer.html', {
                'product_offer': product_offer,
                'product': product,
                'products': products
            })
        
        new_product = get_object_or_404(Product, id=new_product_id)
        if new_product != product and ProductOffer.objects.filter(product=new_product).exists():
            messages.error(request, 'An offer already exists for the selected product.')
            return render(request, 'admin/edit_product_offer.html', {
                'product_offer': product_offer,
                'product': product,
                'products': products
            })
        
        product_offer.product = new_product
        product_offer.discount_percentage = discount_percentage
        product_offer.save()
        messages.success(request, 'Product offer updated successfully.')
        return redirect('product_offer_list')
    
    return render(request, 'admin/edit_product_offer.html', {
        'product_offer': product_offer,
        'product': product,
        'products': products
    })





"""
PRODUCT OFFER ACTIVATIOIN/DEACTIVATION
"""
@user_passes_test(lambda u: u.is_superuser)
def toggle_product_offer(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    product_offer = get_object_or_404(ProductOffer, product=product)
    product_offer.is_active = not product_offer.is_active
    product_offer.save()
    messages.success(request, f'Product offer {"activated" if product_offer.is_active else "deactivated"} successfully.')
    return redirect('product_offer_list')






"""
ADD CATEGORY OFFER
"""
@user_passes_test(lambda u: u.is_superuser)
def add_category_offer(request, category_id=None):
    categories = Category.objects.all()
    if request.method == 'POST':
        category_id = request.POST.get('category')
        discount_percentage = request.POST.get('discount_percentage')
        
        # Validation
        if not category_id or not discount_percentage:
            messages.error(request, 'Category and discount percentage are required.')
            return render(request, 'admin/add_category_offer.html', {
                'categories': categories,
                'selected_category': category_id,
                'discount_percentage': discount_percentage
            })
        
        try:
            discount_percentage = float(discount_percentage)
            if discount_percentage < 0 or discount_percentage > 100:
                messages.error(request, 'Discount percentage must be between 0 and 100.')
                return render(request, 'admin/add_category_offer.html', {
                    'categories': categories,
                    'selected_category': category_id,
                    'discount_percentage': discount_percentage
                })
        except ValueError:
            messages.error(request, 'Invalid discount percentage.')
            return render(request, 'admin/add_category_offer.html', {
                'categories': categories,
                'selected_category': category_id,
                'discount_percentage': discount_percentage
            })
        
        category = get_object_or_404(Category, id=category_id)
        if CategoryOffer.objects.filter(category=category).exists():
            messages.error(request, 'An offer already exists for this category.')
            return render(request, 'admin/add_category_offer.html', {
                'categories': categories,
                'selected_category': category_id,
                'discount_percentage': discount_percentage
            })
        
        CategoryOffer.objects.create(
            category=category,
            discount_percentage=discount_percentage,
            is_active=True
        )
        messages.success(request, 'Category offer added successfully.')
        return redirect('category_offer_list')
    
    return render(request, 'admin/add_category_offer.html', {'categories': categories})




















"""
CATEGORY OFFER LISTING
"""
@user_passes_test(lambda u: u.is_superuser)
def category_offer_list(request):
    query = request.GET.get('q')
    category_offers_list = CategoryOffer.objects.all()
    if query:
        category_offers_list = category_offers_list.filter(category__category_name__icontains=query)
    paginator = Paginator(category_offers_list, 10)
    page_number = request.GET.get('page')
    category_offers = paginator.get_page(page_number)
    return render(request, 'admin/category_offer_list.html', {'category_offers': category_offers})







"""
EDIT CATEGORY OFFER
"""
@user_passes_test(lambda u: u.is_superuser)
def edit_category_offer(request, category_id):
    category = get_object_or_404(Category, id=category_id)
    category_offer = get_object_or_404(CategoryOffer, category=category)
    categories = Category.objects.all() 
    
    if request.method == 'POST':
        new_category_id = request.POST.get('category')
        discount_percentage = request.POST.get('discount_percentage')
        
        # Validation
        if not new_category_id or not discount_percentage:
            messages.error(request, 'Category and discount percentage are required.')
            return render(request, 'admin/edit_category_offer.html', {
                'category_offer': category_offer,
                'category': category,
                'categories': categories
            })
        
        try:
            discount_percentage = float(discount_percentage)
            if discount_percentage < 0 or discount_percentage > 100:
                messages.error(request, 'Discount percentage must be between 0 and 100.')
                return render(request, 'admin/edit_category_offer.html', {
                    'category_offer': category_offer,
                    'category': category,
                    'categories': categories
                })
        except ValueError:
            messages.error(request, 'Invalid discount percentage.')
            return render(request, 'admin/edit_category_offer.html', {
                'category_offer': category_offer,
                'category': category,
                'categories': categories
            })
        
        new_category = get_object_or_404(Category, id=new_category_id)
        if new_category != category and CategoryOffer.objects.filter(category=new_category).exists():
            messages.error(request, 'An offer already exists for the selected category.')
            return render(request, 'admin/edit_category_offer.html', {
                'category_offer': category_offer,
                'category': category,
                'categories': categories
            })
        
        category_offer.category = new_category
        category_offer.discount_percentage = discount_percentage
        category_offer.save()
        messages.success(request, 'Category offer updated successfully.')
        return redirect('category_offer_list')
    
    return render(request, 'admin/edit_category_offer.html', {
        'category_offer': category_offer,
        'category': category,
        'categories': categories
    })




"""
CATEGORY OFFER ACTIVATE/DEACTIVATE
"""
@user_passes_test(lambda u: u.is_superuser)
def toggle_category_offer(request, category_id):
    category = get_object_or_404(Category, id=category_id)
    category_offer = get_object_or_404(CategoryOffer, category=category)
    category_offer.is_active = not category_offer.is_active
    category_offer.save()
    messages.success(request, f'Category offer {"activated" if category_offer.is_active else "deactivated"} successfully.')
    return redirect('category_offer_list')