from django.conf.urls import patterns, url

from mssim import views

prefix = r'fcgi-bin/sysite/'
#prefix = r'sy/'

urlpatterns = patterns('',
    url(r'^' + prefix + r'mssim', views.mssim, name='mssim'),
    url(r'^' + prefix + r'datum', views.datum, name='datum'),
    url(r'^' + prefix + r'wahlsim', views.wahlsim, name='wahlsim'),
    url(r'^' + prefix + r'slwahl', views.slwahl, name='slwahl'),
)
