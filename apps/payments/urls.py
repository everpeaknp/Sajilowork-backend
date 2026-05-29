from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    PaymentViewSet, PaymentMethodViewSet, RefundViewSet,
    PayoutViewSet, TransactionViewSet,
)
from .escrow_views import (
    EscrowInitiateAPIView,
    EscrowVerifyAPIView,
    EscrowReleaseAPIView,
    EscrowRefundAPIView,
    EscrowStatusAPIView,
)

app_name = 'payments'

router = DefaultRouter()
router.register(r'payments', PaymentViewSet, basename='payment')
router.register(r'payment-methods', PaymentMethodViewSet, basename='payment-method')
router.register(r'refunds', RefundViewSet, basename='refund')
router.register(r'payouts', PayoutViewSet, basename='payout')
router.register(r'transactions', TransactionViewSet, basename='transaction')

urlpatterns = [
    path('initiate/', EscrowInitiateAPIView.as_view(), name='escrow-initiate'),
    path('verify/', EscrowVerifyAPIView.as_view(), name='escrow-verify'),
    path('escrow/release/', EscrowReleaseAPIView.as_view(), name='escrow-release'),
    path('escrow/refund/', EscrowRefundAPIView.as_view(), name='escrow-refund'),
    path('escrow/status/<uuid:task_id>/', EscrowStatusAPIView.as_view(), name='escrow-status'),
    path('', include(router.urls)),
]
