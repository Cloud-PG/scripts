FROM centos:7
LABEL maintainer="mirco.tracolli@pg.infn.it"
LABEL Version=0.2

# wn metapackage: https://twiki.cern.ch/twiki/bin/view/LCG/EL7WNMiddleware 

# UPDATE SYSTEM AND INSTALL WGET
RUN yum --setopt=tsflags=nodocs -y update \
    && yum --setopt=tsflags=nodocs -y install wget

WORKDIR /etc/yum.repos.d
RUN wget http://repository.egi.eu/community/software/preview.repository/2.0/releases/repofiles/centos-7-x86_64.repo \
    && wget http://repository.egi.eu/sw/production/cas/1/current/repo-files/EGI-trustanchors.repo 

WORKDIR /root
# ADD EXTRA SYSTEM STUFF
RUN yum --setopt=tsflags=nodocs -y install epel-release yum-plugin-ovl \
    && yum --setopt=tsflags=nodocs -y install fetch-crl wn \
    && yum clean all

# GET_PROXY STUFF
RUN yum --setopt=tsflags=nodocs -y install python python-pip \
    && yum clean all \
    && pip install --upgrade pip \
    && pip install requests kazoo flask \
    && mkdir -p /opt/certcache/ \
    && mkdir -p /var/log/certcache/ \
    && touch /var/log/certcache/app.log
COPY ./proxy.py ./cache.py ./app_certcache.py /opt/certcache/

EXPOSE 80

CMD ["/usr/bin/python", "/opt/certcache/app_certcache.py"]
