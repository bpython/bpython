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


import pdb
import bpython

class BPdb(pdb.Pdb):
    """ PDB with BPython support. """
    
    def __init__(self):
        pdb.Pdb.__init__(self)
        self.rcLines = []
        self.prompt = '(BPdb) '


    ### cmd.Cmd commands


    def do_BPython(self, arg):
        bpython.embed(self.curframe.f_locals, ['-i'])


    def help_BPython(self):
        print >>self.stdout, "B(Python)"                                                                                                                                                   
        print >>self.stdout, """Invoke the BPython interpreter for this 
stack frame. To exit BPython and return to BPdb type in CTRL+D
(CTRL+Z on Windows)."""


    ### shortcuts
    
    do_B = do_BPython
    help_B = help_BPython
