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

"""Module for loading the command line interface"""

import argcomplete
import logging
import sys
from udtc.frameworks import BaseCategory

logger = logging.getLogger(__name__)


def run_command_for_args(args):
    """Run correct command for args"""
    # args.category can be a category or a framework in main
    try:
        BaseCategory.categories[args.category].run_for(args)
    except AttributeError:
        BaseCategory.main_category.frameworks[args.category].run_for(args)


def main(parser):
    """Main entry point of the cli command"""
    categories_parser = parser.add_subparsers(help='Developer environment', dest="category")
    for category in BaseCategory.categories.values():
        category.install_category_parser(categories_parser)

    argcomplete.autocomplete(parser)
    args = parser.parse_args()

    if not args.category:
        parser.print_help()
        sys.exit(0)

    run_command_for_args(args)
