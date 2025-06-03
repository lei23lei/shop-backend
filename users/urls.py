from django.urls import path
from .views import UserView, RegisterView, LoginView, VerifyTokenView
from rest_framework_simplejwt.views import TokenRefreshView

urlpatterns = [
    path('register/', RegisterView.as_view(), name='register'),
    path('login/', LoginView.as_view(), name='login'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('users/', UserView.as_view(), name='users'),
    path('verify/', VerifyTokenView.as_view(), name='verify'),
]