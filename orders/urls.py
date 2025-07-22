from rest_framework.routers import DefaultRouter
from .views import OrderViewSet, TerminalViewSet, RobotViewSet, ProgramViewSet

# маршруты REST API
router = DefaultRouter()
router.register(r'orders', OrderViewSet, basename='order')
router.register(r'terminals', TerminalViewSet, basename='terminal')
router.register(r'robots', RobotViewSet, basename='robot')
router.register(r'programs', ProgramViewSet, basename='program')

urlpatterns = router.urls
