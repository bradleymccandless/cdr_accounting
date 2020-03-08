from django.urls import path
from . import views
urlpatterns = [
    path('kapi/', views.kapi, name='kapi'),
 #   path('bill-all/', views.bill_all_accounts, name='bill_all_accounts'),
]
