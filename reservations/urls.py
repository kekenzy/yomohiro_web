from django.urls import path
from django.contrib.auth.views import LoginView, LogoutView
from . import views

app_name = 'reservations'

urlpatterns = [
    path('', views.index, name='index'),
    path('locations/', views.location_list, name='location_list'),
    path('reservations/', views.reservation_list, name='reservation_list'),
    path('reservations/create/', views.reservation_create, name='reservation_create'),
    path('reservations/<int:pk>/', views.reservation_detail, name='reservation_detail'),
    path('reservations/<int:pk>/edit/', views.reservation_edit, name='reservation_edit'),
    path('reservations/<int:pk>/delete/', views.reservation_delete, name='reservation_delete'),
    path('check-availability/', views.check_availability, name='check_availability'),
    path('dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('location-management/', views.location_management, name='location_management'),
    path('location-management/add/', views.location_add, name='location_add'),
    path('locations/<int:pk>/edit/', views.location_edit, name='location_edit'),
    path('locations/<int:pk>/delete/', views.location_delete, name='location_delete'),
    path('login/', views.custom_login, name='custom_login'),
    path('logout/', LogoutView.as_view(next_page='reservations:index'), name='logout'),
    path('api/calendar/events/', views.get_calendar_events, name='calendar_events'),
]
