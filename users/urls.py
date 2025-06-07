from django.urls import path
from .views import UserView, RegisterView, LoginView, VerifyTokenView, ForgotPasswordView, ResetPasswordView, CartView, CartCountView, OrderView
from rest_framework_simplejwt.views import TokenRefreshView

urlpatterns = [
    path('register/', RegisterView.as_view(), name='register'),
    path('login/', LoginView.as_view(), name='login'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('users/', UserView.as_view(), name='users'),
    path('verify/', VerifyTokenView.as_view(), name='verify'),
    path('forgot-password/', ForgotPasswordView.as_view(), name='forgot_password'),
    path('reset-password/', ResetPasswordView.as_view(), name='reset_password'),
    path('cart/', CartView.as_view(), name='cart'),
    path('cart-count/', CartCountView.as_view(), name='cart_count'),
    path('orders/', OrderView.as_view(), name='create-order'),
]