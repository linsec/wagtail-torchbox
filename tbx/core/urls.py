from django.conf.urls import url

from tbx.core.feeds import BlogFeed, PlanetDrupalFeed

urlpatterns = [
    url(r'^blog/feed/$', BlogFeed(), name='blog_feed'),
    url(
        r'^blog/feed/planet_drupal/$',
        PlanetDrupalFeed(),
        name='planet_drupal_feed'
    ),
]
