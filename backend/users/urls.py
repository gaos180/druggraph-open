from django.urls import path
from . import views

urlpatterns = [
    # ── Autenticación pública ─────────────────────────────────────────────────
    path('register/',       views.register,       name='auth-register'),
    path('login/',          views.login,           name='auth-login'),
    path('logout/',         views.logout,          name='auth-logout'),

    # ── Perfil propio ──────────────────────────────────────────────────────────
    path('me/',             views.me,              name='auth-me'),
    path('me/update/',      views.update_me,       name='auth-me-update'),
    path('me/password/',    views.change_password, name='auth-me-password'),

    # ── CRUD de usuarios (solo admin) ──────────────────────────────────────────
    path('users/',                              views.admin_users_list,        name='admin-users-list'),
    path('users/<str:user_id>/',               views.admin_user_detail,        name='admin-user-detail'),
    path('users/<str:user_id>/reset-password/', views.admin_reset_password_view, name='admin-reset-password'),
]
