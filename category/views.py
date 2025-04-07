from django.shortcuts import render,redirect,get_object_or_404
from .models import Category
from django.utils import timezone
from django.contrib import messages
from admin_side.views import is_admin
from django.contrib.auth.decorators import user_passes_test
from django.core.paginator import Paginator,EmptyPage,PageNotAnInteger
from django.views.decorators.cache import never_cache



# Create your views here.






"""
CATEGORY MANAGEMENT
"""
@never_cache
@user_passes_test(is_admin)
def category_management(request):
    search_query = request.GET.get('search', '')  

    if request.method == 'POST':
        category_name = request.POST.get('category_name')
        category_image = request.FILES.get('image')

        if not category_name:
            error_message = "Category name is required!"
        elif Category.objects.filter(category_name__iexact=category_name).exists():
            error_message = "Category already exists!"
        else:
            Category.objects.create(
                category_name=category_name,
                created_at=timezone.now(),
                image=category_image
            )
            messages.success(request, "Category created successfully!")
            return redirect('category_management')

        categories = Category.objects.all()

    # Search categories based on the search query
    if search_query:
        categories = Category.objects.filter(category_name__icontains=search_query)  
    else:
        categories = Category.objects.all() 

    page = request.GET.get('page', 1)
    paginator = Paginator(categories, 10)

    try:
        categories = paginator.page(page)
    except PageNotAnInteger:
        categories = paginator.page(1)
    except EmptyPage:
        categories = paginator.page(paginator.num_pages)

    return render(request, 'admin/category.html', {
        'categories': categories,
        'search_query': search_query,
    })




"""
EDIT CATEGORY
"""
@never_cache
@user_passes_test(is_admin)
def edit_category(request, category_id):
    category = get_object_or_404(Category, id=category_id)

    if request.method == 'POST':
        category_name = request.POST.get('category_name')
        category_image = request.FILES.get('image')

        if not category_name:
            messages.error(request, 'Category name is required!')
        elif Category.objects.filter(category_name__iexact=category_name).exclude(id=category_id).exists():
            messages.error(request, 'Category with this name already exists!')
        else:
            category.category_name = category_name
            if category_image:
                category_image = category_image 
            category.save()
            messages.success(request, 'Category updated successfully')
            return redirect('category_management')       


    return render(request, 'admin/edit_category.html',{'category':category})





"""
CATEGORY ACTIVATE/DEACTIVATE
"""
@never_cache
def toggle_listing(request, category_id):
    category = get_object_or_404(Category, id=category_id)
    category.is_listed = not category.is_listed
    category.save()
    messages.success(request, f"Category {'unlisted' if not category.is_listed else 'relisted'} successfully!")
    return redirect('category_management')

    

