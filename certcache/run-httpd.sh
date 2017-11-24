#!/bin/bash

# Make sure we're not confused by old, incompletely-shutdown httpd
# context after restarting the container.  httpd won't start correctly
# if it thinks it is already running.
rm -rf /run/httpd/* /tmp/httpd*

exec /usr/bin/python /var/www/cgi-bin/get_proxy
exec /usr/sbin/apachectl -DFOREGROUND

# ONLY APACHE
# exec /usr/sbin/apachectl -DFOREGROUND