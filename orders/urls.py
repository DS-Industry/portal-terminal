from django.urls import path

from rest_framework.routers import DefaultRouter

from .views import (
    ProgramListView,
    ProgramViewSet,
    WashOrderPaymentView,
    LtyCheckView,
    WashOrderCancellationView,
    WashOrderDetailView,
    UcnCheckView,
    OpenReaderView,
    MobileQrView,
    WashOrderStartView,
    TerminalDataView
)

router = DefaultRouter()
router.register(r'programs', ProgramViewSet, basename='program')

urlpatterns = router.urls + [
    path('wash-programs/', ProgramListView.as_view(), name='program-list'),
    path('pay/', WashOrderPaymentView.as_view(), name='washorder-pay'),
    path('terminal-data/', TerminalDataView.as_view(), name='terminal-data'),
    path('lty-check/', LtyCheckView.as_view(), name='lty-check'),
    path('ucn-check/', UcnCheckView.as_view(), name='ucn-check'),
    path('mobile-qr/', MobileQrView.as_view(), name='ucn-check'),
    path('cancellation/<int:order_id>/', WashOrderCancellationView.as_view(), name='washorder-cancellation'),
    path('start/<int:order_id>/', WashOrderStartView.as_view(), name='washorder-start'),
    path('order-detail/<int:order_id>/', WashOrderDetailView.as_view(), name='washorder-detail'),
    path('open-reader/', OpenReaderView.as_view(), name='open-reader'),
]
