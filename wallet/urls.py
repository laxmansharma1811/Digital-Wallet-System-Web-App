from django.urls import path
from . import views


urlpatterns = [
    path('register/', views.register_view, name='register'),
    path('login/', views.login_view, name='login'),
    path('', views.home, name='home'),
    path('logout/', views.logout_view, name='logout'),

    path('wallet/', views.wallet_view, name='wallet'),
    path('wallet/deposit/', views.deposit_view, name='deposit'),
    path('wallet/withdraw/', views.withdraw_view, name='withdraw'),
    path('wallet/transfer/', views.transfer_view, name='transfer'),
    path('transaction/<int:transaction_id>/', views.transaction_detail_view, name='transaction_detail'),

    path('wallet/export/csv/', views.export_transactions_csv, name='export_csv'),
    path('wallet/export/pdf/', views.export_transactions_pdf, name='export_pdf'),

    path('wallet/categories/', views.manage_categories, name='manage_categories'),
    path('wallet/tags/', views.manage_tags, name='manage_tags'),
]