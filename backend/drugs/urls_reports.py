from django.urls import path

from .views.reports import (
    report_generate_view,
    report_list_view,
    report_detail_view,
)

urlpatterns = [
    path('generate/',            report_generate_view, name='reports-generate'),
    path('',                     report_list_view,     name='reports-list'),
    path('<str:report_id>/',     report_detail_view,   name='reports-detail'),
]
