from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    WalletViewSet, WalletTransactionViewSet, WithdrawalRequestViewSet,
    WalletFreezeViewSet, WalletLimitViewSet
)

router = DefaultRouter()
router.register(r'wallets', WalletViewSet, basename='wallet')
router.register(r'transactions', WalletTransactionViewSet, basename='wallet-transaction')
router.register(r'withdrawals', WithdrawalRequestViewSet, basename='withdrawal')
router.register(r'freezes', WalletFreezeViewSet, basename='wallet-freeze')
router.register(r'limits', WalletLimitViewSet, basename='wallet-limit')

urlpatterns = [
    path('', include(router.urls)),
]
