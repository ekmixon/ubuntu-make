#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (C) 2014 Canonical
#
# Authors:
#  Didier Roche
#
# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation; version 3.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA

from distutils import cmd
from distutils.command.install_data import install_data as _install_data
from distutils.command.build import build as _build
import gettext
from glob import glob
import os
from setuptools import setup, find_packages
import subprocess
import umake  # that initializes the gettext domain
from umake.settings import get_version

I18N_DOMAIN = gettext.textdomain()
PO_DIR = os.path.join(os.path.dirname(os.curdir), 'po')


def get_requirements(tag_to_detect=""):
    """Gather a list of requirements line per line from tag_to_detect to next tag.

    if tag_to_detect is empty, it will gather every requirement"""
    requirements = []
    tag_detected = False
    with open("requirements.txt") as f:
        for line in f.read().splitlines():
            if line.startswith("#") or line == "":
                tag_detected = bool(line.startswith(tag_to_detect))
                continue
            if tag_detected:
                requirements.append(line)
    print(requirements)
    return requirements


#
# add translation support
#
class build(_build):
    sub_commands = _build.sub_commands + [('build_trans', None)]

    def run(self):
        _build.run(self)


class build_trans(cmd.Command):
    description = "Compile .po files into .mo files"
    user_options = []

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run(self):
        for filename in os.listdir(PO_DIR):
            if not filename.endswith('.po'):
                continue
            lang = filename[:-3]
            src = os.path.join(PO_DIR, filename)
            dest_path = os.path.join('build', 'locale', lang, 'LC_MESSAGES')
            dest = os.path.join(dest_path, f'{I18N_DOMAIN}.mo')
            if not os.path.exists(dest_path):
                os.makedirs(dest_path)
            if not os.path.exists(dest):
                print(f'Compiling {src}')
                subprocess.call(["msgfmt", src, "--output-file", dest])
            else:
                src_mtime = os.stat(src)[8]
                dest_mtime = os.stat(dest)[8]
                if src_mtime > dest_mtime:
                    print(f'Compiling {src}')
                    subprocess.call(["msgfmt", src, "--output-file", dest])


class install_data(_install_data):

    def run(self):
        for filename in os.listdir(PO_DIR):
            if not filename.endswith('.po'):
                continue
            lang = filename[:-3]
            lang_dir = os.path.join('share', 'locale', lang, 'LC_MESSAGES')
            lang_file = os.path.join(
                'build', 'locale', lang, 'LC_MESSAGES', f'{I18N_DOMAIN}.mo'
            )

            self.data_files.append((lang_dir, [lang_file]))
        _install_data.run(self)


class update_pot(cmd.Command):
    description = 'Update template for translators'
    user_options = []

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run(self):
        cmd = [
            'xgettext',
            '--language=Python',
            '--keyword=_',
            '--package-name',
            I18N_DOMAIN,
            '--output',
            f'po/{I18N_DOMAIN}.pot',
        ]

        for path, names, filenames in os.walk(os.path.join(os.curdir, 'umake')):
            for f in filenames:
                if f.endswith('.py'):
                    cmd.append(os.path.join(path, f))
        subprocess.call(cmd)


class update_po(cmd.Command):
    description = 'Update po from pot file'
    user_options = []

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run(self):
        source_pot = os.path.join(os.curdir, 'po', f'{I18N_DOMAIN}.pot')
        for po_file in glob(os.path.join(os.curdir, 'po', '*.po')):
            subprocess.check_call(["msgmerge", "-U", po_file, source_pot])


setup(
    name="Ubuntu Make",
    version=get_version(),
    packages=find_packages(exclude=["tests*"]),
    package_data={},
    entry_points={
        'console_scripts': [
            'umake = umake:main',
            'udtc = umake:main'
        ],
    },

    data_files=[
        ('lib/python3/dist-packages/umake', ['umake/version']),
        ("share/ubuntu-make/log-confs", glob('log-confs/*.yaml')),
        ('share/zsh/vendor-completions', ['confs/completions/_umake']),
    ],

    cmdclass={
        'build': build,
        'build_trans': build_trans,
        'install_data': install_data,
        'update_pot': update_pot,
        'update_po': update_po
    }
)
