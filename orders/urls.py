from rest_framework.routers import DefaultRouter
from .views import ProgramViewSet, CreateWashOrderView
from django.urls import path

router = DefaultRouter()
router.register(r'programs', ProgramViewSet, basename='program')

urlpatterns = router.urls + [
    path('create-order/', CreateWashOrderView.as_view(), name='create-order'),
]
