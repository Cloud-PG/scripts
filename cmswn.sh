#!/bin/bash

# let's avoid black holes
if [ ! -f /cvmfs/cms.cern.ch/cmsset_default.sh ];then
    echo "CVMFS Must run to allow job execution"
    exit
fi

yum -y install ca-policy-egi-core
yum -y install ca-policy-lcg
/etc/init.d/fetch-crl-boot restart

cd /etc/yum.repos.d
wget https://ci.cloud.cnaf.infn.it/job/cnaf-mw-devel-jobs/job/ca_CMS-TTS-CA/job/master/lastSuccessfulBuild/artifact/ca_CMS-TTS-CA.repo
cd -
yum -y install ca_CMS-TTS-CA

resp=0
until [  $resp -eq 200 ]; do
    resp=$(curl -s \
        -w%{http_code} \
        $PROXY_CACHE/cgi-bin/get_proxy -o /root/gwms_proxy)
done
echo $resp
#############

chmod 600 /root/gwms_proxy

export X509_USER_PROXY=/root/gwms_proxy
export X509_CERT_DIR=/etc/grid-security/certificates
grid-proxy-info
if [ $? -eq 0 ]; then
    echo "proxy certificate is OK"

    ### Configure condor
    str1=$(grep "GLIDEIN_Site =" /etc/condor/config.d/99_glidein)
    sed -i -e "s/$str1/GLIDEIN_Site = \"$CMS_LOCAL_SITE\"/g" /etc/condor/config.d/99_glidein
    str2=$(grep "GLIDEIN_CMSSite =" /etc/condor/config.d/99_glidein)
    sed -i -e "s/$str2/GLIDEIN_CMSSite = \"$CMS_LOCAL_SITE\"/g" /etc/condor/config.d/99_glidein

    export PATH=$PATH:/usr/libexec/condor

    condor_master
    export WN_TIMEOUT=60
    while true; do
        sleep 600
        cmd=$(find /var/log/condor -type f -name StartLog -mmin -$WN_TIMEOUT)
        if [ -z $cmd ]; then
            break
        fi
    done
else
    echo "proxy certificate is Failure"
fi
