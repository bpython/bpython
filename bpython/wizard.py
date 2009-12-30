#!/usr/bin/env python
#
# The MIT License
#
# Copyright (c) 2008 Bob Farrell
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
#

import os
import sys
from ConfigParser import ConfigParser

# questions asked by the wizard (keys are the config values, followed by text
# and answers and defaults
positive_answers = ('Y', 'y', 'yes', 'ja',)
negative_answers = ('N', 'n', 'no', 'nein',)

# Create default answer
positive_negative = {positive_answers: 'True',
                     negative_answers: 'False'}

# Create dict for storing everythin
questions = {}

# Create sections
questions['general'] = {}
questions['keyboard'] = {}

questions['general']['auto_display_list'] = {'question': 'Do you want to show the autocomplete list as you type (y/n):',
                                             'answers': positive_negative}

questions['general']['arg_spec'] = {'question': 'Do you want to show the argspec (y/n):',
                                    'answers': positive_negative} 

questions['general']['syntax'] = {'question': 'Do you want syntax highlighting as you type (y/n):',
                                  'answers': positive_negative}

filename = os.path.expanduser('~/.bpython/config')

def is_first_run():
    return not os.path.isfile(filename)

def create_empty_file():
    f = open(filename, 'w')
    f.write('')
    f.close()

def run_wizard():
    """Run an interactive wizard asking a few questions about the users'
    enviroment and write the answers to the configuration file."""


    print """Hi there. It seems this is the first time you run bpython. I can
tell because you do not have a configuration file yet. There are a few
options I am going to give you.

I am ready to run the wizard for you now. If you do not want to run the
wizard and just have me create an empty configuration file for you you can
answer no to the following question.
"""

    answer = raw_input('Do you want to run the wizard: ')

    if answer.lower() in negative_answers:
        create_empty_file()
    else:
        config = ConfigParser()

        for section_name, section in questions.iteritems():
            config.add_section(section_name)

            print
            for config_value, q in section.iteritems():
                while 1:
                    print q['question'],
                    answer = raw_input()

                    if answer in positive_answers:
                        config.set(section_name, config_value, q['answers'][positive_answers])
                        break
                    elif answer in negative_answers:
                        config.set(section_name, config_value, q['answers'][negative_answers])
                        break
                    else:
                        print
                        print "I couldn't understand the answer you provided, please try again"

        config.write(open(filename, 'w'))

def main():
    if is_first_run():
        run_wizard()
