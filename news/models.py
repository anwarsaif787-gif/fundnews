from django.db import models
from django.utils.text import slugify


class Source(models.Model):
    name = models.CharField(max_length=100)
    feed_url = models.URLField(max_length=500)

    def __str__(self):
        return self.name


class Category(models.Model):
    """A topic such as Fundraising, Deals or People."""
    name = models.CharField(max_length=50)
    keywords = models.TextField(blank=True, help_text="Comma separated, e.g. final close, first close, raises")

    class Meta:
        verbose_name_plural = "categories"

    def __str__(self):
        return self.name


class Market(models.Model):
    """An asset class such as Private equity or Venture capital."""
    name = models.CharField(max_length=60)
    slug = models.SlugField(max_length=70, unique=True, blank=True)
    keywords = models.TextField(blank=True, help_text="Comma separated")
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ['order', 'name']

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Firm(models.Model):
    """An investment firm that stories can mention (Blackstone, KKR...)."""
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=110, unique=True, blank=True)
    aliases = models.CharField(max_length=300, blank=True, help_text="Other names, comma separated")

    class Meta:
        ordering = ['name']

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Story(models.Model):
    """One event. Several publishers' articles about it are grouped here."""
    title = models.CharField(max_length=300)
    link = models.URLField(max_length=1000)
    publisher = models.CharField(max_length=100)
    category = models.ForeignKey(Category, null=True, blank=True, on_delete=models.SET_NULL)
    market = models.ForeignKey(Market, null=True, blank=True, on_delete=models.SET_NULL)
    firms = models.ManyToManyField(Firm, blank=True)
    amount_usd = models.FloatField(null=True, blank=True)
    article_count = models.PositiveIntegerField(default=1)
    published = models.DateTimeField(db_index=True)

    class Meta:
        ordering = ['-published']
        verbose_name_plural = "stories"

    def __str__(self):
        return self.title


class Article(models.Model):
    source = models.ForeignKey(Source, on_delete=models.CASCADE)
    category = models.ForeignKey(Category, null=True, blank=True, on_delete=models.SET_NULL)
    story = models.ForeignKey(Story, null=True, blank=True, on_delete=models.SET_NULL, related_name='articles')
    title = models.CharField(max_length=300)
    link = models.URLField(max_length=1000, unique=True)
    summary = models.TextField(blank=True)
    published = models.DateTimeField()

    class Meta:
        ordering = ['-published']

    def __str__(self):
        return self.title


class Event(models.Model):
    title = models.CharField(max_length=200)
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    city = models.CharField(max_length=80, blank=True)
    organizer = models.CharField(max_length=120, blank=True)
    url = models.URLField(max_length=500, blank=True)
    is_webinar = models.BooleanField(default=False)

    class Meta:
        ordering = ['start_date']

    def __str__(self):
        return f"{self.title} ({self.start_date})"


class Subscriber(models.Model):
    email = models.EmailField(unique=True)
    created = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.email
