from django.conf.urls.defaults import patterns, url
from go.conversation import views

urlpatterns = patterns('',
    url(r'^$', views.index, name='index'),
    url(r'^new/', views.new, name='new'),
    url(r'^(?P<conversation_pk>\d+)/people/', views.people, name='people'),
    url(r'^(?P<conversation_pk>\d+)/upload/', views.upload, name='upload'),
    url(r'^(?P<conversation_pk>\d+)/send/', views.send, name='send'),
    url(r'^(?P<conversation_pk>\d+)/start/', views.start, name='start'),
    url(r'^(?P<conversation_pk>\d+)/end/', views.end, name='end'),
    url(r'^(?P<conversation_pk>\d+)/', views.show, name='show'),
)
