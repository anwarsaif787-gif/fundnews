from django.contrib import admin
from django.urls import path
from news import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.home, name='home'),
    path('category/<str:category>/', views.category_page, name='category'),
    path('markets/<slug:slug>/', views.market_page, name='market'),
    path('firms/', views.firm_list, name='firms'),
    path('firms/<slug:slug>/', views.firm_page, name='firm'),
    path('events/', views.events, name='events'),
    path('closes/', views.closes, name='closes'),
    path('about/', views.about, name='about'),
    path('subscribe/', views.subscribe, name='subscribe'),
    path('refresh/<path:token>/', views.refresh, name='refresh'),
    path('unsubscribe/<path:token>/', views.unsubscribe, name='unsubscribe'),
    path('send-digest/<path:token>/', views.send_digest_hook, name='send_digest'),
    path('test-email/', views.test_email, name='test_email'),
    path('feed.xml', views.LatestStories(), name='feed'),
]
