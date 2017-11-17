FROM centos:7
LABEL maintainer="mirco.tracolli@pg.infn.it"
LABEL Version=0.1

# wn metapackage: https://twiki.cern.ch/twiki/bin/view/LCG/EL7WNMiddleware 

# UPDATE SYSTEM AND INSTALL WGET
RUN yum --setopt=tsflags=nodocs -y update
RUN yum --setopt=tsflags=nodocs -y install wget

WORKDIR /etc/yum.repos.d
RUN wget http://repository.egi.eu/community/software/preview.repository/2.0/releases/repofiles/centos-7-x86_64.repo && \
    wget http://repository.egi.eu/sw/production/cas/1/current/repo-files/EGI-trustanchors.repo 

WORKDIR /root
# ADD EXTRA SYSTEM STUFF
RUN yum --setopt=tsflags=nodocs -y install epel-release \
    yum-plugin-ovl && \
    yum --setopt=tsflags=nodocs -y install fetch-crl \
    singularity \
    wn && \
    yum clean all

# APACHE + CGI + SCRIPT DEPENDENCIES
RUN yum --setopt=tsflags=nodocs -y install python \
    python-pip \
    httpd && \
    pip install --upgrade pip && \
    pip install requests && \
    pip install kazoo
# GET_PROXY SCRIPT
COPY ./get_proxy ./cache.py /var/www/cgi-bin/
RUN chmod -v +x /var/www/cgi-bin/get_proxy
# SCRIPT LOG DIR AND FILE
RUN mkdir -p /var/log/ttscache/ && \
    touch /var/log/ttscache/certcache.log && \
    chown -R apache:apache /var/log/ttscache
# APACHE FOREGROUND SCRIPT
WORKDIR /usr/local/bin
COPY ./run-httpd.sh /usr/local/bin
RUN chmod -v +x /usr/local/bin/run-httpd.sh

WORKDIR /root

EXPOSE 80

CMD ["run-httpd.sh"]
