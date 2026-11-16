from django.contrib import admin
from .models import Article, Category, Event, Firm, Market, Source, Story, Subscriber


@admin.register(Source)
class SourceAdmin(admin.ModelAdmin):
    list_display = ('name', 'feed_url')


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'keywords')


@admin.register(Market)
class MarketAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'order')


@admin.register(Firm)
class FirmAdmin(admin.ModelAdmin):
    list_display = ('name', 'aliases')
    search_fields = ('name', 'aliases')


@admin.register(Story)
class StoryAdmin(admin.ModelAdmin):
    list_display = ('title', 'publisher', 'category', 'market', 'amount_usd', 'article_count', 'published')
    list_filter = ('category', 'market')
    search_fields = ('title',)


@admin.register(Article)
class ArticleAdmin(admin.ModelAdmin):
    list_display = ('title', 'source', 'category', 'published')
    list_filter = ('category', 'source')
    search_fields = ('title',)


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ('title', 'start_date', 'city', 'organizer', 'is_webinar')
    list_filter = ('is_webinar',)


@admin.register(Subscriber)
class SubscriberAdmin(admin.ModelAdmin):
    list_display = ('email', 'created')
