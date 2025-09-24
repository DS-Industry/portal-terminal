from django.urls import path

from rest_framework.routers import DefaultRouter

from .views import (
    CreateWashOrderView,
    ProgramListView,
    ProgramViewSet,
    WashOrderPaymentView,
    LtyCheckView,
    WashOrderCancellationView,
    WashOrderDetailView,
    UcnCheckView
)

router = DefaultRouter()
router.register(r'programs', ProgramViewSet, basename='program')

urlpatterns = router.urls + [
    path('wash-programs/', ProgramListView.as_view(), name='program-list'),
    path('pay/', WashOrderPaymentView.as_view(), name='washorder-pay'),
    path('lty-check/', LtyCheckView.as_view(), name='lty-check'),
    path('ucn-check/', UcnCheckView.as_view(), name='ucn-check'),
    path('cancellation/', WashOrderCancellationView.as_view(), name='washorder-cancellation'),
    path('order-detail/', WashOrderDetailView.as_view(), name='washorder-detail'),
]
