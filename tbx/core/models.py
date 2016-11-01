from __future__ import unicode_literals

from django import forms
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.db import models
from django.db.models.signals import pre_delete
from django.dispatch import receiver
from django.shortcuts import render
from django.utils.functional import cached_property
from django.utils.translation import ugettext_lazy as _

from modelcluster.fields import ParentalKey
from wagtail.contrib.settings.models import BaseSetting, register_setting
from wagtail.wagtailadmin.edit_handlers import (FieldPanel, InlinePanel,
                                                MultiFieldPanel,
                                                PageChooserPanel,
                                                StreamFieldPanel)
from wagtail.wagtailcore.blocks import (CharBlock, FieldBlock, ListBlock,
                                        PageChooserBlock, RawHTMLBlock,
                                        RichTextBlock, StreamBlock,
                                        StructBlock)
from wagtail.wagtailcore.fields import RichTextField, StreamField
from wagtail.wagtailcore.models import Orderable, Page
from wagtail.wagtaildocs.edit_handlers import DocumentChooserPanel
from wagtail.wagtailembeds.blocks import EmbedBlock
from wagtail.wagtailimages.blocks import ImageChooserBlock
from wagtail.wagtailimages.edit_handlers import ImageChooserPanel
from wagtail.wagtailimages.models import (AbstractImage, AbstractRendition,
                                          Image)
from wagtail.wagtailsearch import index
# from django.core.mail import EmailMessage
# from wagtail.wagtailadmin.utils import send_mail
# from wagtail.wagtailforms.models import AbstractEmailForm, AbstractFormField
# from wagtail.wagtailsnippets.models import register_snippet


# Streamfield blocks and config

class ImageFormatChoiceBlock(FieldBlock):
    field = forms.ChoiceField(choices=(
        ('left', 'Wrap left'),
        ('right', 'Wrap right'),
        ('half', 'Half width'),
        ('full', 'Full width'),
    ))


class ImageBlock(StructBlock):
    image = ImageChooserBlock()
    alignment = ImageFormatChoiceBlock()
    caption = CharBlock()
    attribution = CharBlock(required=False)

    class Meta:
        icon = "image"


class PhotoGridBlock(StructBlock):
    images = ListBlock(ImageChooserBlock())

    class Meta:
        icon = "grip"


class PullQuoteBlock(StructBlock):
    quote = CharBlock(classname="quote title")
    attribution = CharBlock()

    class Meta:
        icon = "openquote"


class PullQuoteImageBlock(StructBlock):
    quote = CharBlock()
    attribution = CharBlock()
    image = ImageChooserBlock(required=False)


class BustoutBlock(StructBlock):
    image = ImageChooserBlock()
    text = RichTextBlock()

    class Meta:
        icon = "pick"


class WideImage(StructBlock):
    image = ImageChooserBlock()

    class Meta:
        icon = "image"


class StatsBlock(StructBlock):
    pass

    class Meta:
        icon = "order"


class StoryBlock(StreamBlock):
    h2 = CharBlock(icon="title", classname="title")
    h3 = CharBlock(icon="title", classname="title")
    h4 = CharBlock(icon="title", classname="title")
    intro = RichTextBlock(icon="pilcrow")
    paragraph = RichTextBlock(icon="pilcrow")
    aligned_image = ImageBlock(label="Aligned image")
    wide_image = WideImage(label="Wide image")
    bustout = BustoutBlock()
    pullquote = PullQuoteBlock()
    raw_html = RawHTMLBlock(label='Raw HTML', icon="code")
    embed = EmbedBlock(icon="code")
    # photogrid = PhotoGridBlock()
    # testimonial = PullQuoteImageBlock(label="Testimonial", icon="group")
    # stats = StatsBlock()


# A couple of abstract classes that contain commonly used fields
class ContentBlock(models.Model):
    title = models.CharField(max_length=255, verbose_name=_('title'))
    content = RichTextField(verbose_name=_('content'))

    panels = [
        FieldPanel('title'),
        FieldPanel('content'),
    ]

    class Meta:
        abstract = True


class LinkFields(models.Model):
    link_external = models.URLField(verbose_name=_("External link"), blank=True)
    link_page = models.ForeignKey(
        'wagtailcore.Page',
        null=True,
        blank=True,
        related_name='+',
        verbose_name=_('link page')
    )
    link_document = models.ForeignKey(
        'wagtaildocs.Document',
        null=True,
        blank=True,
        related_name='+',
        verbose_name=_('link document')
    )

    @property
    def link(self):
        if self.link_page:
            return self.link_page.url
        elif self.link_document:
            return self.link_document.url
        else:
            return self.link_external

    panels = [
        FieldPanel('link_external'),
        PageChooserPanel('link_page'),
        DocumentChooserPanel('link_document'),
    ]

    class Meta:
        abstract = True


class ContactFields(models.Model):
    telephone = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    address_1 = models.CharField(max_length=255, blank=True)
    address_2 = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=255, blank=True)
    country = models.CharField(max_length=255, blank=True)
    post_code = models.CharField(max_length=10, blank=True)

    panels = [
        FieldPanel('telephone'),
        FieldPanel('email'),
        FieldPanel('address_1'),
        FieldPanel('address_2'),
        FieldPanel('city'),
        FieldPanel('country'),
        FieldPanel('post_code'),
    ]

    class Meta:
        abstract = True


# Carousel items
class CarouselItem(LinkFields):
    image = models.ForeignKey(
        'torchbox.TorchboxImage',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='+'
    )
    embed_url = models.URLField("Embed URL", blank=True)
    caption = models.CharField(max_length=255, blank=True)

    panels = [
        ImageChooserPanel('image'),
        FieldPanel('embed_url'),
        FieldPanel('caption'),
        MultiFieldPanel(LinkFields.panels, "Link"),
    ]

    class Meta:
        abstract = True


# Related links
class RelatedLink(LinkFields):
    title = models.CharField(max_length=255, verbose_name=_('title'),
                             help_text=_("Link title"))

    panels = [
        FieldPanel('title'),
        MultiFieldPanel(LinkFields.panels, "Link"),
    ]

    class Meta:
        abstract = True


# Advert Snippet
class AdvertPlacement(models.Model):
    page = ParentalKey('wagtailcore.Page', related_name='advert_placements')
    advert = models.ForeignKey('torchbox.Advert', related_name='+')


class Advert(models.Model):
    page = models.ForeignKey(
        'wagtailcore.Page',
        related_name='adverts',
        null=True,
        blank=True
    )
    url = models.URLField(null=True, blank=True)
    text = models.CharField(max_length=255)

    panels = [
        PageChooserPanel('page'),
        FieldPanel('url'),
        FieldPanel('text'),
    ]

    def __unicode__(self):
        return self.text

# register_snippet(Advert)


# Custom image
class TorchboxImage(AbstractImage):
    credit = models.CharField(max_length=255, blank=True)

    admin_form_fields = Image.admin_form_fields + (
        'credit',
    )

    @property
    def credit_text(self):
        return self.credit


# Receive the pre_delete signal and delete the file associated with the model instance.
@receiver(pre_delete, sender=TorchboxImage)
def image_delete(sender, instance, **kwargs):
    # Pass false so FileField doesn't save the model.
    instance.file.delete(False)


class TorchboxRendition(AbstractRendition):
    image = models.ForeignKey('TorchboxImage', related_name='renditions')

    class Meta:
        unique_together = (
            ('image', 'filter', 'focal_point_key'),
        )


# Receive the pre_delete signal and delete the file associated with the model instance.
@receiver(pre_delete, sender=TorchboxRendition)
def rendition_delete(sender, instance, **kwargs):
    # Pass false so FileField doesn't save the model.
    instance.file.delete(False)


# Home Page

class HomePageHero(Orderable, RelatedLink):
    page = ParentalKey('torchbox.HomePage', related_name='hero')
    colour = models.CharField(max_length=255, verbose_name=_("colour"),
                              help_text=_("Hex ref colour of link and background gradient, use #23b0b0 for default blue"))
    background = models.ForeignKey(
        'torchbox.TorchboxImage',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='+',
        verbose_name=_("background")
    )
    logo = models.ForeignKey(
        'torchbox.TorchboxImage',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='+',
        verbose_name=_("logo")
    )
    text = models.CharField(
        max_length=255,
        verbose_name=_("text")
    )

    panels = RelatedLink.panels + [
        ImageChooserPanel('background'),
        ImageChooserPanel('logo'),
        FieldPanel('colour'),
        FieldPanel('text'),
    ]


class HomePageClient(Orderable, RelatedLink):
    page = ParentalKey('torchbox.HomePage', related_name='clients')
    image = models.ForeignKey(
        'torchbox.TorchboxImage',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='+',
        verbose_name=_('image')
    )

    panels = RelatedLink.panels + [
        ImageChooserPanel('image')
    ]


class HomePage(Page):
    hero_intro = models.TextField(blank=True, verbose_name=_('hero intro'))
    hero_video_id = models.IntegerField(blank=True, null=True, help_text=_("Optional. The numeric ID of a Vimeo video to replace the background image."))
    hero_video_poster_image = models.ForeignKey(
        'torchbox.TorchboxImage',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='+'
    )
    # intro_title = models.TextField(blank=True, verbose_name=_('intro title'))
    # intro_body = RichTextField(blank=True, verbose_name=_('intro body'))
    # work_title = models.TextField(blank=True, verbose_name=_('work title'))
    blog_title = models.TextField(blank=True, verbose_name=_('blog title'))
    clients_title = models.TextField(blank=True, verbose_name=_('clients title'))

    class Meta:
        verbose_name = _("Homepage")

    content_panels = [
        FieldPanel('title', classname="full title"),
        FieldPanel('hero_intro'),
        InlinePanel('hero', label=_("Hero")),
        # FieldPanel('intro_title'),
        # FieldPanel('intro_body'),
        # FieldPanel('work_title'),
        FieldPanel('blog_title'),
        FieldPanel('clients_title'),
        InlinePanel('clients', label=_("Clients")),
    ]

    @property
    def blog_posts(self):
        # Get list of blog pages.
        blog_posts = BlogPage.objects.filter(
            live=True
        )

        # Order by most recent date first
        blog_posts = blog_posts.order_by('-date')

        return blog_posts


# Standard page

class StandardPageContentBlock(Orderable, ContentBlock):
    page = ParentalKey('torchbox.StandardPage', related_name='content_block',
                       verbose_name=_('page'))


class StandardPageRelatedLink(Orderable, RelatedLink):
    page = ParentalKey('torchbox.StandardPage', related_name='related_links',
                       verbose_name=_('page'))


class StandardPageClient(Orderable, RelatedLink):
    page = ParentalKey('torchbox.StandardPage', related_name='clients',
                       verbose_name=_('page'))
    image = models.ForeignKey(
        'torchbox.TorchboxImage',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='+',
        verbose_name=_('image')
    )

    panels = RelatedLink.panels + [
        ImageChooserPanel('image')
    ]


class StandardPage(Page):
    main_image = models.ForeignKey(
        'torchbox.TorchboxImage',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='+',
        verbose_name=_('main image')
    )
    heading = RichTextField(blank=True, verbose_name=_('heading'))
    quote = models.CharField(max_length=255, blank=True, verbose_name=_('quote'))
    streamfield = StreamField(StoryBlock(), verbose_name=_('stream field'))
    email = models.EmailField(blank=True, verbose_name=_('email'))

    feed_image = models.ForeignKey(
        'torchbox.TorchboxImage',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='+',
        verbose_name=_('feed image')
    )

    show_in_play_menu = models.BooleanField(default=False,
                                            verbose_name=_('show in play menu'))

    content_panels = [
        FieldPanel('title', classname="full title"),
        ImageChooserPanel('main_image'),
        FieldPanel('heading', classname="full"),
        FieldPanel('quote', classname="full"),
        StreamFieldPanel('streamfield'),
        FieldPanel('email', classname="full"),
        InlinePanel('content_block', label=_("Content block")),
        # InlinePanel('related_links', label=_("Related links")),
        # InlinePanel('clients', label=_("Clients")),
    ]

    promote_panels = [
        MultiFieldPanel(Page.promote_panels, _("Common page configuration")),
        FieldPanel('show_in_play_menu'),
        ImageChooserPanel('feed_image'),
    ]

    class Meta:
        verbose_name = _("StandardPage")


# About page
class AboutPageRelatedLinkButton(Orderable, RelatedLink):
    page = ParentalKey('torchbox.AboutPage', related_name='related_link_buttons',
                       verbose_name=_('page'))


class AboutPageOffice(Orderable):
    page = ParentalKey('torchbox.AboutPage', related_name='offices',
                       verbose_name=_('page'))
    title = models.TextField(verbose_name=_('title'))
    svg = models.TextField(null=True, verbose_name=_('svg'))
    description = models.TextField(verbose_name=_('description'))

    panels = [
        FieldPanel('title'),
        FieldPanel('description'),
        FieldPanel('svg')
    ]


class AboutPageContentBlock(Orderable):
    page = ParentalKey('torchbox.AboutPage', related_name='content_blocks',
                       verbose_name=_('page'))
    year = models.IntegerField(verbose_name=_('year'))
    title = models.TextField(verbose_name=_('title'))
    description = models.TextField(verbose_name=_('description'))
    image = models.ForeignKey(
        'torchbox.TorchboxImage',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='+',
        verbose_name=_('image')
    )

    panels = [
        FieldPanel('year'),
        FieldPanel('title'),
        FieldPanel('description'),
        ImageChooserPanel('image')
    ]


class AboutPage(Page):
    main_image = models.ForeignKey(
        'torchbox.TorchboxImage',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='+',
        verbose_name=_('main image')
    )
    heading = models.TextField(blank=True, verbose_name=_('heading'))
    intro = models.TextField(blank=True, verbose_name=_('intro'))
    involvement_title = models.TextField(blank=True,
                                         verbose_name=_('involvement title'))

    content_panels = [
        FieldPanel('title', classname='full title'),
        ImageChooserPanel('main_image'),
        FieldPanel('heading', classname='full'),
        FieldPanel('intro', classname='full'),
        InlinePanel('related_link_buttons', label=_('Header buttons')),
        InlinePanel('content_blocks', label=_('Content blocks')),
        InlinePanel('offices', label=_('Offices')),
        FieldPanel('involvement_title'),
    ]

    class Meta:
        verbose_name = _("AboutPage")


# Services page
class ServicesPageService(Orderable):
    page = ParentalKey('torchbox.ServicesPage', related_name='services')
    title = models.TextField(verbose_name=_('title'))
    svg = models.TextField(null=True, verbose_name=_('svg'))
    description = models.TextField(verbose_name=_('description'))

    panels = [
        FieldPanel('title'),
        FieldPanel('description'),
        FieldPanel('svg')
    ]

    class Meta:
        verbose_name = _("Service Item")


class ServicesPage(Page):
    main_image = models.ForeignKey(
        'torchbox.TorchboxImage',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='+',
        verbose_name=_('main image')
    )
    heading = models.TextField(blank=True, verbose_name=_('heading'))
    intro = models.TextField(blank=True, verbose_name=_('intro'))

    search_fields = Page.search_fields + [
        index.SearchField('intro'),
    ]

    content_panels = [
        FieldPanel('title', classname='full title'),
        ImageChooserPanel('main_image'),
        FieldPanel('heading'),
        FieldPanel('intro', classname='full'),
        InlinePanel('services', label='Services'),
    ]

    class Meta:
        verbose_name = _("Service Page")


# Blog index page
#
# class BlogIndexPageRelatedLink(Orderable, RelatedLink):
#     page = ParentalKey('torchbox.BlogIndexPage', related_name='related_links',
#                        verbose_name=_('related links'))
#
#
# class BlogIndexPage(Page):
#     intro = models.TextField(blank=True, verbose_name=_('intro'))
#
#     search_fields = Page.search_fields + [
#         index.SearchField('intro'),
#     ]
#
#     show_in_play_menu = models.BooleanField(default=False)
#
#     def get_popular_tags(self):
#         # Get a ValuesQuerySet of tags ordered by most popular (exclude 'planet-drupal' as this is effectively
#         # the same as Drupal and only needed for the rss feed)
#         popular_tags = BlogPageTagSelect.objects.all().exclude(tag__name='planet-drupal').values('tag').annotate(item_count=models.Count('tag')).order_by('-item_count')
#
#         # Return first 10 popular tags as tag objects
#         # Getting them individually to preserve the order
#         return [BlogPageTagList.objects.get(id=tag['tag']) for tag in popular_tags[:10]]
#
#     @property
#     def blog_posts(self):
#         # Get list of blog pages that are descendants of this page
#         # and are not marketing_only
#         blog_posts = BlogPage.objects.filter(
#             live=True,
#             path__startswith=self.path
#         )#.exclude(marketing_only=True)
#
#         # Order by most recent date first
#         blog_posts = blog_posts.order_by('-date', 'pk')
#
#         return blog_posts
#
#     def serve(self, request):
#         # Get blog_posts
#         blog_posts = self.blog_posts
#
#         # Filter by tag
#         tag = request.GET.get('tag')
#         if tag:
#             blog_posts = blog_posts.filter(tags__tag__slug=tag)
#
#         # Pagination
#         per_page = 12
#         page = request.GET.get('page')
#         paginator = Paginator(blog_posts, per_page)  # Show 10 blog_posts per page
#         try:
#             blog_posts = paginator.page(page)
#         except PageNotAnInteger:
#             blog_posts = paginator.page(1)
#         except EmptyPage:
#             blog_posts = paginator.page(paginator.num_pages)
#
#         if request.is_ajax():
#             return render(request, "torchbox/includes/blog_listing.html", {
#                 'self': self,
#                 'blog_posts': blog_posts,
#                 'per_page': per_page,
#             })
#         else:
#             return render(request, self.template, {
#                 'self': self,
#                 'blog_posts': blog_posts,
#                 'per_page': per_page,
#             })
#
#     content_panels = [
#         FieldPanel('title', classname="full title"),
#         FieldPanel('intro', classname="full"),
#         InlinePanel('related_links', label="Related links"),
#     ]
#
#     promote_panels = [
#         MultiFieldPanel(Page.promote_panels, _("Common page configuration")),
#         FieldPanel('show_in_play_menu'),
#     ]
#
#     class Meta:
#         verbose_name = _("Blog Index Page")
#

# Blog page
class BlogPageRelatedLink(Orderable, RelatedLink):
    page = ParentalKey('torchbox.BlogPage', related_name='related_links')


class BlogPageTagList(models.Model):
    name = models.CharField(max_length=255)
    slug = models.CharField(max_length=255)

    def __unicode__(self):
        return self.name

# register_snippet(BlogPageTagList)


class BlogPageTagSelect(Orderable):
    page = ParentalKey('torchbox.BlogPage', related_name='tags')
    tag = models.ForeignKey(
        'torchbox.BlogPageTagList',
        related_name='blog_page_tag_select'
    )


class BlogPageAuthor(Orderable):
    page = ParentalKey('torchbox.BlogPage', related_name='related_author')
    author = models.ForeignKey(
        'torchbox.PersonPage',
        null=True,
        blank=True,
        related_name='+',
        verbose_name=_('author')
    )

    panels = [
        PageChooserPanel('author'),
    ]


class BlogPage(Page):
    # intro = RichTextField("Intro (used for blog index and Planet Drupal listings)", blank=True)
    # body = RichTextField("body (deprecated. Use streamfield instead)", blank=True)
    # colour = models.CharField(
    #     _("Listing card colour if left blank will display image"),
    #     choices=(
    #         ('orange', "Orange"),
    #         ('blue', "Blue"),
    #         ('white', "White")
    #     ),
    #     max_length=255,
    #     blank=True
    # )
    streamfield = StreamField(StoryBlock(), verbose_name=_('body'))
    # author_left = models.CharField(max_length=255, blank=True, help_text=_('author who has left Torchbox'))
    date = models.DateField(_("Post date"))
    feed_image = models.ForeignKey(
        'torchbox.TorchboxImage',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='+',
        verbose_name=_('feed image')
    )
    # marketing_only = models.BooleanField(default=False, help_text='Display this blog post only on marketing landing page')

    canonical_url = models.URLField(blank=True, max_length=255)

    search_fields = Page.search_fields + [
        # index.SearchField('body'),
    ]

    class Meta:
        verbose_name = _("Blog Page")

    @property
    def blog_index(self):
        # Find blog index in ancestors
        for ancestor in reversed(self.get_ancestors()):
            if isinstance(ancestor.specific, BlogIndexPage):
                return ancestor

        # No ancestors are blog indexes,
        # just return first blog index in database
        return BlogIndexPage.objects.first()

    @property
    def has_authors(self):
        for author in self.related_author.all():
            if author.author:
                return True

    content_panels = [
        FieldPanel('title', classname="full title"),
        InlinePanel('related_author', label=_("Author")),
        FieldPanel('date'),
        StreamFieldPanel('streamfield'),
        InlinePanel('related_links', label=_("Related links")),
        InlinePanel('tags', label=_("Tags"))
    ]

    promote_panels = [
        MultiFieldPanel(Page.promote_panels, _("Common page configuration")),
        ImageChooserPanel('feed_image'),
        FieldPanel('canonical_url'),
    ]


# Jobs index page
class ReasonToJoin(Orderable):
    page = ParentalKey('torchbox.JobIndexPage', related_name='reasons_to_join')
    image = models.ForeignKey(
        'torchbox.TorchboxImage',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='+',
        verbose_name=_('image')
    )
    title = models.CharField(max_length=255, verbose_name=_('title'))
    body = models.CharField(max_length=511, verbose_name=_('body'))

    panels = [
        ImageChooserPanel('image'),
        FieldPanel('title'),
        FieldPanel('body')
    ]

    class Meta:
        verbose_name = _('Reason To Join')

class JobIndexPageJob(Orderable):
    page = ParentalKey('torchbox.JobIndexPage', related_name='job')
    job_title = models.CharField(max_length=255, verbose_name=_('job title'))
    job_intro = models.CharField(max_length=255, verbose_name=_('job intro'))
    url = models.URLField(null=True, verbose_name=_('url'))
    location = models.CharField(max_length=255, blank=True, verbose_name=_('location'))

    panels = [
        FieldPanel('job_title'),
        FieldPanel('job_intro'),
        FieldPanel("url"),
        FieldPanel("location"),
    ]

    class Meta:
        verbose_name = _('Job Item')

class JobIndexPage(Page):
    intro = models.TextField(blank=True, verbose_name=_('intro'))
    listing_intro = models.TextField(
        blank=True,
        verbose_name=_('listing_intro'),
        help_text=_("Shown instead of the intro when job listings are included "
        "on other pages"))
    no_jobs_that_fit = RichTextField(blank=True, verbose_name=_('no jobs that fit'))
    terms_and_conditions = models.URLField(null=True, verbose_name=_('terms and conditions'))
    refer_a_friend = models.URLField(null=True, verbose_name=_('refer a friend'))
    reasons_intro = models.TextField(blank=True, verbose_name=_('reasons intro'))

    search_fields = Page.search_fields + [
        index.SearchField('intro'),
    ]

    def get_context(self, request, *args, **kwargs):
        context = super(
            JobIndexPage, self
        ).get_context(request, *args, **kwargs)
        context['jobs'] = self.job.all()
        context['blogs'] = BlogPage.objects.live().order_by('-date')[:4]
        return context

    content_panels = [
        FieldPanel('title', classname="full title"),
        FieldPanel('intro', classname="full"),
        FieldPanel('listing_intro', classname="full"),
        FieldPanel('no_jobs_that_fit', classname="full"),
        FieldPanel('terms_and_conditions', classname="full"),
        FieldPanel('refer_a_friend', classname="full"),
        InlinePanel('job', label="Job"),
        FieldPanel('reasons_intro', classname="full"),
        InlinePanel('reasons_to_join', label="Reasons To Join"),
    ]

    promote_panels = [
        MultiFieldPanel(Page.promote_panels, _("Common page configuration")),
    ]

    class Meta:
        verbose_name = _('Job Index Page')


# Person page
class PersonPageRelatedLink(Orderable, RelatedLink):
    page = ParentalKey('torchbox.PersonPage', related_name='related_links')


class PersonPage(Page, ContactFields):
    first_name = models.CharField(max_length=255, verbose_name=_('first name'))
    last_name = models.CharField(max_length=255, verbose_name=_('last name'))
    role = models.CharField(max_length=255, blank=True, verbose_name=_('role'))
    is_senior = models.BooleanField(default=False, verbose_name=_('is_senior'))
    intro = RichTextField(blank=True, verbose_name=_('intro'))
    biography = RichTextField(blank=True, verbose_name=_('biography'))
    image = models.ForeignKey(
        'torchbox.TorchboxImage',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='+',
        verbose_name=_('image')
    )
    feed_image = models.ForeignKey(
        'torchbox.TorchboxImage',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='+',
        verbose_name=_('feed image')
    )

    search_fields = Page.search_fields + [
        index.SearchField('first_name'),
        index.SearchField('last_name'),
        index.SearchField('intro'),
        index.SearchField('biography'),
    ]

    content_panels = [
        FieldPanel('title', classname="full title"),
        FieldPanel('first_name'),
        FieldPanel('last_name'),
        FieldPanel('role'),
        FieldPanel('is_senior'),
        FieldPanel('intro', classname="full"),
        FieldPanel('biography', classname="full"),
        ImageChooserPanel('image'),
        MultiFieldPanel(ContactFields.panels, "Contact"),
        InlinePanel('related_links', label="Related links"),
    ]

    promote_panels = [
        MultiFieldPanel(Page.promote_panels, _("Common page configuration")),
        ImageChooserPanel('feed_image'),
    ]

    class Meta:
        verbose_name = _("Person Page")


# Person index
class PersonIndexPage(Page):
    intro = models.TextField()
    senior_management_intro = models.TextField()
    team_intro = models.TextField()

    class Meta:
        verbose_name = _("Person Index Page")

    @cached_property
    def people(self):
        return PersonPage.objects.exclude(is_senior=True).live().public()

    @cached_property
    def senior_management(self):
        return PersonPage.objects.exclude(is_senior=False).live().public()

    content_panels = Page.content_panels + [
        FieldPanel('intro', classname="full"),
        FieldPanel('senior_management_intro', classname="full"),
        FieldPanel('team_intro', classname="full"),
    ]


@register_setting
class GlobalSettings(BaseSetting):

    contact_telephone = models.CharField(max_length=255,
                                         verbose_name=_('contact telphone'),
                                         help_text=_('Telephone'))
    contact_email = models.CharField(max_length=255,
                                     verbose_name=_('contact email'),
                                     help_text=_('Email address'))
    contact_twitter = models.CharField(max_length=255,
                                       verbose_name=_('contact twitter'),
                                       help_text=_('Twitter'))
    # email_newsletter_teaser = models.CharField(max_length=255,
    #                                            verbose_name=_('email newsletter teaser'),
    #                                            help_text=_('Text that sits above the email newsletter'))
    # oxford_address_title = models.CharField(max_length=255, help_text=_('Full address'))
    # oxford_address = models.CharField(max_length=255, help_text=_('Full address'))
    # oxford_address_link = models.URLField(max_length=255, help_text=_('Link to google maps'))
    # oxford_address_svg = models.CharField(max_length=9000, help_text=_('Paste SVG code here'))
    # bristol_address_title = models.CharField(max_length=255, help_text=_('Full address'))
    # bristol_address = models.CharField(max_length=255, help_text=_('Full address'))
    # bristol_address_link = models.URLField(max_length=255, help_text=_('Link to google maps'))
    # bristol_address_svg = models.CharField(max_length=9000, help_text=_('Paste SVG code here'))
    # phili_address_title = models.CharField(max_length=255, help_text=_('Full address'))
    # phili_address = models.CharField(max_length=255, help_text=_('Full address'))
    # phili_address_link = models.URLField(max_length=255, help_text=_('Link to google maps'))
    # phili_address_svg = models.CharField(max_length=9000, help_text=_('Paste SVG code here'))

    class Meta:
        verbose_name = _('Global Settings')


class SubMenuItemBlock(StreamBlock):
    subitem = PageChooserBlock(verbose_name=_('subitem'))

    class Meta:
        verbose_name = _('subitem')


class MenuItemBlock(StructBlock):
    page = PageChooserBlock(verbose_name=_('page'))
    subitems = SubMenuItemBlock(verbose_name=_('subitems'))

    class Meta:
        verbose_name = _('Menu Item')
        template = "torchbox/includes/menu_item.html"


class MenuBlock(StreamBlock):
    items = MenuItemBlock()

    class Meta:
        verbose_name = _('Menu')


@register_setting
class MainMenu(BaseSetting):
    menu = StreamField(MenuBlock(), blank=True, verbose_name=_('menu'))

    panels = [
        StreamFieldPanel('menu'),
    ]

    class Meta:
        verbose_name = _('Main Menu')
