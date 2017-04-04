#!/bin/bash
yum -y install ca-policy-egi-core
yum -y install ca-policy-lcg
/etc/init.d/fetch-crl-boot restart 


#curl... url-spiga
mkdir /root/INDIGO_certs

cd /root/INDIGO_certs

wget http://cmsdoc.cern.ch/~spiga/INDIGO_certs/INDIGOCA.namespaces
wget http://cmsdoc.cern.ch/~spiga/INDIGO_certs/INDIGOCA.pem
wget http://cmsdoc.cern.ch/~spiga/INDIGO_certs/INDIGOCA.signing_policy

cp /root/INDIGO_certs/* /etc/grid-security/certificates/

cd /etc/grid-security/certificates/
ln -s INDIGOCA.pem `openssl x509 -subject_hash -noout -in INDIGOCA.pem`.0 
ln -s INDIGOCA.namespaces `openssl x509 -subject_hash -noout -in INDIGOCA.pem`.namespaces 
ln -s INDIGOCA.signing_policy `openssl x509 -subject_hash -noout -in INDIGOCA.pem`.signing_policy
cd

rm -rf /root/INDIGO_certs/*

####### commenti
#resp=0
#until [  $resp -eq 200 ]; do
#    resp=$(curl -s \
#        -w%{http_code} \
#        $PROXY_CACHE/cgi-bin/get_proxy -o /root/gwms_proxy)
#done
#echo $resp
##############

#wget spiga-url-cert
curl -L http://cmsdoc.cern.ch/~spiga/.x509up_u16858 -o /root/gwms_proxy

chmod 600 /root/gwms_proxy

export X509_USER_PROXY=/root/gwms_proxy
voms-proxy-info -all
export X509_CERT_DIR="/etc/grid-security/certificates"


### configurazione di condor
# prende la cms_local_site
# configura

str1=$(grep "GLIDEIN_Site =" /etc/condor/config.d/99_glidein)

sed -i -e "s/$str1/GLIDEIN_Site = \"$CMS_LOCAL_SITE\"/g" /etc/condor/config.d/99_glidein

str2=$(grep "GLIDEIN_CMSSite =" /etc/condor/config.d/99_glidein)

sed -i -e "s/$str2/GLIDEIN_CMSSite = \"$CMS_LOCAL_SITE\"/g" /etc/condor/config.d/99_glidein


export PATH=$PATH:/usr/libexec/condor


#etc/condor/config.d/99_local_tweaks
#/etc/condor/config.d/99_local_tweaks
#GSI_DAEMON_NAME=$(GSI_DAEMON_NAME),/DC=ch/DC=cern/OU=Organic Units/OU=Users/CN=spiga/CN=606831/CN=Daniele Spiga

#to be removed once added in the global conf
export WN_TIMEOUT=30

condor_master

sleep 100

while true; do
    filedate=$(date -r /var/log/condor/StartLog +"%s")
    curdate=$(date +"%s")
    diffdate=$(date -u -d "0 $curdate seconds - $filedate seconds" +"%M")

    if [ $diffdate > $WN_TIMEOUT ]
    then
        break
    fi
    
    sleep 60
    
done
