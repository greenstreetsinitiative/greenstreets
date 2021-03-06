from django.conf import settings
from django.conf.urls import patterns, include, url
from django.conf.urls.static import static
from django.views.generic import TemplateView

from django.contrib import admin
admin.autodiscover()

urlpatterns = patterns('',

    # Home
    url(r'^$', TemplateView.as_view(template_name='survey/index.html'), name='home'),

    # Commuterform
    # url(r'^commuterform/$', 'survey.views.commuter', name='commuterform'),
    url(r'^commuterform/$', 'survey.views.add_checkin', name='commuterform'),
    url(r'^commuterform/complete/$', TemplateView.as_view(template_name='survey/thanks.html'), name='complete'),

    # Leaderboard
    url(r'^legacy-leaderboard/$', 'leaderboard.views.new_leaderboard'),
    url(r'^leaderboard/$', 'leaderboard.views.latest_leaderboard', name="all"),
    url(r'^leaderboard/small/$', 'leaderboard.views.latest_leaderboard_small', name="small"),
    url(r'^leaderboard/medium/$', 'leaderboard.views.latest_leaderboard_medium', name="medium"),
    url(r'^leaderboard/large/$', 'leaderboard.views.latest_leaderboard_large', name="large"),
    url(r'^leaderboard/largest/$', 'leaderboard.views.latest_leaderboard_largest', name="largest"),


    # data api
    url(r'^api/survey/$', 'survey.views.api', name='survey_api'),

    # Retail Partners
    url(r'^retail/$', include('retail.urls', namespace='retail')),
    url(r'^register/', include('register.urls', namespace='register')),

    # Examples:
    # url(r'^$', 'django_test.views.home', name='home'),
    # url(r'^$', TemplateView.as_view(template_name='index.html'), name='index'),
    # url(r'^blog/', include('blog.urls')),

    url(r'^grappelli/', include('grappelli.urls')),
    url(r'^admin/', include(admin.site.urls)),
    url(r'^legacy-leaderboard/redirect', 'leaderboard.views.lb_redirect'),

    url(r'^legacy-leaderboard/(\d+)/$', 'leaderboard.views.new_leaderboard'),
    url(r'^legacy-leaderboard/(?P<empid>\d+)/(?P<sort>[^/]+)/$', 'leaderboard.views.new_leaderboard'),
    url(r'^legacy-leaderboard/(\d+)/([^/]+)/(\d+)/$', 'leaderboard.views.new_leaderboard'),
    url(r'^legacy-leaderboard/(\d+)/([^/]+)/(\d+)/([^/]+)/$', 'leaderboard.views.new_leaderboard'),
    url(r'^legacy-leaderboard/month_(?P<selmonth>[^/]+)$', 'leaderboard.views.new_leaderboard'),

    url(r'^legacy-leaderboard/(\d+)/month_(?P<selmonth>[^/]+)$', 'leaderboard.views.new_leaderboard'),
    url(r'^legacy-leaderboard/(?P<empid>\d+)/(?P<sort>[^/]+)/month_(?P<selmonth>[^/]+)$', 'leaderboard.views.new_leaderboard'),
    url(r'^legacy-leaderboard/(\d+)/([^/]+)/(\d+)/month_(?P<selmonth>[^/]+)$', 'leaderboard.views.new_leaderboard'),
    url(r'^legacy-leaderboard/(?P<empid>\d+)/(?P<filter_by>[^/]+)/(?P<_filter>\d+)/(?P<sort>[^/]+)/month_(?P<selmonth>[^/]+)$', 'leaderboard.views.new_leaderboard'),

    url(r'^legacy-leaderboard/(?P<sort>[^/]+)/$', 'leaderboard.views.new_leaderboard'),
    url(r'^legacy-leaderboard/(?P<filter_by>[^/]+)/(?P<_filter>\d+)/(?P<sort>[^/]+)/$', 'leaderboard.views.new_leaderboard'),
    url(r'^legacy-leaderboard/(?P<filter_by>[^/]+)/(?P<_filter>\d+)/$', 'leaderboard.views.new_leaderboard'),

    url(r'^legacy-leaderboard/(?P<sort>[^/]+)/month_(?P<selmonth>[^/]+)$', 'leaderboard.views.new_leaderboard'),
    url(r'^legacy-leaderboard/(?P<filter_by>[^/]+)/(?P<_filter>\d+)/(?P<sort>[^/]+)/month_(?P<selmonth>[^/]+)$', 'leaderboard.views.new_leaderboard'),
    url(r'^legacy-leaderboard/(?P<filter_by>[^/]+)/(?P<_filter>\d+)/month_(?P<selmonth>[^/]+)$', 'leaderboard.views.new_leaderboard'),


) + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
