from django.contrib import admin
from django.urls import path,include
from . import views




urlpatterns = [
    
    path('all/', views.all_products, name='all_products'),
   
    
]