from rest_framework.routers import DefaultRouter
from django.urls import path
from .views import (
    ProgramViewSet,
    CreateWashOrderView,
    ProgramListView,
    WashOrderPaymentView
)

router = DefaultRouter()
router.register(r'programs', ProgramViewSet, basename='program')

urlpatterns = router.urls + [
    path('create-order/', CreateWashOrderView.as_view(), name='create-order'),
    path('wash-programs/', ProgramListView.as_view(), name='program-list'),
    path('pay/', WashOrderPaymentView.as_view(), name='washorder-pay'),  
]
