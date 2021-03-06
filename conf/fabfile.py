#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os.path

from fabric.api import cd, settings, run, sudo
from fabric.utils import abort
from fabric.contrib import project


def deploy_all():
    deploy_dev()


def deploy_dev():
    ndm_root = '/software/env/ndm'
    local_dirs = [
        'ckanext-stcndm',
        'ckanext-repeating',
        'ckanext-scheming',
        'ckanext-fluent',
        'ckanext-wet-boew',
        'ckan',
        'ckanapi'
    ]

    with settings(user='ndmusr', hosts=['ndmckand1']):
        project.rsync_project(
            remote_dir=ndm_root,
            local_dir=' '.join(local_dirs)
        )

        for local_dir in local_dirs:
            remote_path = os.path.join(ndm_root, local_dir)
            with cd(remote_path):
                run('python setup.py develop')

        with cd('/software/solr/solr-5.1.0'):
            result = run('bin/solr restart -p 8000')
            if result.failed or 'happy searching' not in result.lower():
                abort('Solr failed to restart!')

        result = sudo('/etc/init.d/httpd restart')
        if result.failed or 'error' in result.lower():
            abort('Apache failed to restart!')
