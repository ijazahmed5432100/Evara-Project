

from django.contrib import admin
from django.urls import path
from . import views









urlpatterns = [
    
    path("", views.wallet_view, name='wallet_view')
    
 
      

]