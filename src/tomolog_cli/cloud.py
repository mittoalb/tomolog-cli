# #########################################################################
# Copyright (c) 2022, UChicago Argonne, LLC. All rights reserved.         #
#                                                                         #
# Copyright 2022. UChicago Argonne, LLC. This software was produced       #
# under U.S. Government contract DE-AC02-06CH11357 for Argonne National   #
# Laboratory (ANL), which is operated by UChicago Argonne, LLC for the    #
# U.S. Department of Energy. The U.S. Government has rights to use,       #
# reproduce, and distribute this software.  NEITHER THE GOVERNMENT NOR    #
# UChicago Argonne, LLC MAKES ANY WARRANTY, EXPRESS OR IMPLIED, OR        #
# ASSUMES ANY LIABILITY FOR THE USE OF THIS SOFTWARE.  If software is     #
# modified to produce derivative works, such modified software should     #
# be clearly marked, so as not to confuse it with the version available   #
# from ANL.                                                               #
#                                                                         #
# Additionally, redistribution and use in source and binary forms, with   #
# or without modification, are permitted provided that the following      #
# conditions are met:                                                     #
#                                                                         #
#     * Redistributions of source code must retain the above copyright    #
#       notice, this list of conditions and the following disclaimer.     #
#                                                                         #
#     * Redistributions in binary form must reproduce the above copyright #
#       notice, this list of conditions and the following disclaimer in   #
#       the documentation and/or other materials provided with the        #
#       distribution.                                                     #
#                                                                         #
#     * Neither the name of UChicago Argonne, LLC, Argonne National       #
#       Laboratory, ANL, the U.S. Government, nor the names of its        #
#       contributors may be used to endorse or promote products derived   #
#       from this software without specific prior written permission.     #
#                                                                         #
# THIS SOFTWARE IS PROVIDED BY UChicago Argonne, LLC AND CONTRIBUTORS     #
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT       #
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS       #
# FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL UChicago     #
# Argonne, LLC OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT,        #
# INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING,    #
# BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;        #
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER        #
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT      #
# LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN       #
# ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE         #
# POSSIBILITY OF SUCH DAMAGE.                                             #
# #########################################################################

import socks
import socket
import requests
import subprocess
import os
import json
import shutil

from time import sleep
from tomolog_cli import log
from tomolog_cli import globus as globus_uploader

def upload(args, filename):

    if not args.public:
        log.info("Running from a private network computer, using SOCKS5 proxy ...")
        # Monkey-patch socket to route through SOCKS5
        socks.set_default_proxy(socks.SOCKS5, "127.0.0.1", args.port)
        # Upload the file through the SOCKS5 proxy
        socket.socket = socks.socksocket
    else:
        log.info("Running from a public network computer ...")

    if args.cloud_service == 'imgur':
        cloud_url = 'https://uploadimgur.com/api/upload'
        log.info('Uploading image to %s' % cloud_url)
        with open(filename, "rb") as f:
            response = requests.post(
                cloud_url,
                files={"image": f}
            )
        headers = {
            "User-Agent": "curl/7.79.1"
        }

        if (response.status_code == 200):
            url = response.text.replace('{"link":"', '').replace('"}', '')
            log.info('*** Image url created %s' % url)
        else:
            log.error('*** An error occurred creating the image url. Error %s' % response.status_code)
            exit()
        response.close()  # prevent downloading the content
    elif args.cloud_service == 'aps':
        log.info('Uploading image to aps web service')
        cloud_url = 'https://www3.xray.aps.anl.gov/tomolog'
        dest_dir = '/net/joulefs/coulomb_Public/docroot/tomolog/'
        log.info('Uploading image to %s' % cloud_url)
        try:
            dest_path = shutil.copy(filename, dest_dir)
            log.info('Image copied to web server directory at %s' % dest_path)
            url = cloud_url + '/' + os.path.basename(filename)
            log.info('*** Image url created %s' % url)
        except FileNotFoundError:
            log.error('Source file %s or destination directory %s not found.' % (filename, dest_dir))
            exit(1)
        except PermissionError:
            log.error('Permission denied writing to %s. Check that your user has write access to the APS tomolog web directory.' % dest_dir)
            exit(1)
        except shutil.SameFileError:
            log.error('Source and destination represent the same file: %s' % filename)
            exit(1)
        except Exception as e:
            log.error('Unexpected error uploading to APS web service: %s' % e)
            exit(1)
    elif args.cloud_service == 'globus':
        log.info('Uploading image to globus')
        url = globus_uploader.upload_file(filename)
        if not url:
            log.error('Globus upload failed for %s' % filename)
            exit(1)
        log.info('*** Image url created %s' % url)
    else:
        log.error('Unknown cloud service: %s' % args.cloud_service)
        exit(1)

    args.count = args.count + 1
    return url
