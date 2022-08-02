# -*- coding: utf-8 -*-
# Copyright (C) 2014 Canonical
#
# Authors:
#  Galileo Sartor
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


"""Java module"""

from contextlib import suppress
from gettext import gettext as _
import logging
import os
import re
import umake.frameworks.baseinstaller
from umake.interactions import DisplayMessage
from umake.network.download_center import DownloadCenter, DownloadItem
from umake.tools import add_env_to_user, MainLoop, ChecksumType
from umake.ui import UI

logger = logging.getLogger(__name__)


class JavaCategory(umake.frameworks.BaseCategory):

    def __init__(self):
        super().__init__(name="Java", description=_("The Java Programming Language"), logo_path=None)


class AdoptOpenJDK(umake.frameworks.baseinstaller.BaseInstaller):

    def __init__(self, **kwargs):
        super().__init__(name="AdoptOpenJDK",
                         description=_("Prebuilt OpenJDK binaries from a fully open " +
                                       "source set of build scripts and infrastructure"),
                         is_category_default=True,
                         download_page="https://api.adoptopenjdk.net/v3/info/available_releases",
                         dir_to_decompress_in_tarball="jdk-*",
                         required_files_path=["bin/java"],
                         only_on_archs=['amd64'],
                         json=True, **kwargs)

        self.lts = False
        self.jvm_impl = "hotspot"

    def download_provider_page(self):
        logger.debug("Download application provider page")
        DownloadCenter([DownloadItem(self.download_page)], self.complete_download_url, download=False)

    def complete_download_url(self, result):
        """Parse the download page and get the SHASUMS256.txt page"""
        version = None

        logger.debug("Set the version in the download url")

        if error_msg := result[self.download_page].error:
            logger.error(
                f"An error occurred while downloading {self.download_page}: {error_msg}"
            )

            UI.return_main_screen(status_code=1)

        for line in result[self.download_page].buffer:
            line_content = line.decode()
            with suppress(AttributeError):
                if self.lts and "most_recent_lts" in line_content:
                    version = re.search(r': (.*),', line_content)[1]
                elif not self.lts and "most_recent_feature_release" in line_content:
                    version = re.search(r': (.*),', line_content)[1]

        if not result:
            logger.error("Download page changed its syntax or is not parsable")
            UI.return_main_screen(status_code=1)

        self.download_page = (
            (
                f"https://api.adoptopenjdk.net/v3/assets/latest/{version}/"
                + f"{self.jvm_impl}?release=latest&"
            )
            + f"jvm_impl={self.jvm_impl}"
        ) + "&vendor=adoptopenjdk&="

        DownloadCenter([DownloadItem(self.download_page)], self.get_metadata_and_check_license, download=False)

    def parse_download_link(self, line, in_download):
        """Parse Java download link, expect to find a url"""
        url = None
        for asset in line:
            if "jdk_x64_linux" in asset["binary"]["package"]["link"]:
                in_download = True
                url = asset["binary"]["package"]["link"]
        return (url, in_download)

    def post_install(self):
        """Add the necessary Java environment variables"""
        add_env_to_user(self.name, {"JAVA_HOME": {"value": self.install_path, "keep": False},
                                    "PATH": {"value": os.path.join(self.install_path, "bin")}})
        UI.delayed_display(DisplayMessage(self.RELOGIN_REQUIRE_MSG.format(self.name)))

    def install_framework_parser(self, parser):
        this_framework_parser = super().install_framework_parser(parser)
        this_framework_parser.add_argument('--lts', action="store_true",
                                           help=_("Install LTS version"))
        this_framework_parser.add_argument('--openj9', action="store_true",
                                           help=_("Install OpenJ9 Implementation"))
        return this_framework_parser

    def run_for(self, args):
        if args.openj9:
            self.name += " OpenJ9"
            self.description += " OpenJ9"
            self.install_path += "-openj9"
            self.jvm_impl = "openj9"
        if args.lts:
            self.name += " LTS"
            self.description += " LTS"
            self.install_path += "-lts"
            self.lts = True
        super().run_for(args)


class OpenJFX(umake.frameworks.baseinstaller.BaseInstaller):

    def __init__(self, **kwargs):
        super().__init__(name="OpenJFX",
                         description=_("Client application platform for desktop, " +
                                       "mobile and embedded systems built on Java"),
                         is_category_default=False,
                         download_page="https://gluonhq.com/products/javafx/",
                         dir_to_decompress_in_tarball="javafx-*",
                         only_on_archs=['amd64'], checksum_type=ChecksumType.sha256,
                         **kwargs)

        self.lts = False

    def parse_download_link(self, line, in_download):
        """Parse OpenJFX download link, expect to find a url"""
        if (not self.lts and 'Latest Release' in line) or self.lts:
            in_download = True
        if in_download and 'linux-x64_bin-sdk.zip.sha256' in line:
            p = re.search(r'href="(https.*)"', line)
            with suppress(AttributeError):
                self.new_download_url = p[1]
        return (None, in_download)

    @MainLoop.in_mainloop_thread
    def get_sha_and_start_download(self, download_result):
        res = download_result[self.new_download_url]
        checksum = res.buffer.getvalue().decode('utf-8').split()[0]
        url = self.new_download_url.replace('.sha256', '')
        self.check_data_and_start_download(url, checksum)

    def post_install(self):
        """Add the necessary OpenJFX environment variables"""
        add_env_to_user(self.name, {"PATH_TO_FX": {"value": os.path.join(self.install_path, "lib"), "keep": False}})
        UI.delayed_display(DisplayMessage(self.RELOGIN_REQUIRE_MSG.format(self.name)))

    def install_framework_parser(self, parser):
        this_framework_parser = super().install_framework_parser(parser)
        this_framework_parser.add_argument('--lts', action="store_true",
                                           help=_("Install LTS version"))
        return this_framework_parser

    def run_for(self, args):
        if args.lts:
            self.name += " LTS"
            self.description += " LTS"
            self.install_path += "-lts"
            self.lts = True
        super().run_for(args)
