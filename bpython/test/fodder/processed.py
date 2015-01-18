#careful! Whitespace is very important in this file

class BlankLineBetweenMethods(object):
    def method1(self):
        pass
    
    def method2(self):
        pass

def BlankLineInFunction(self):
    return 7
    
    pass

#StartTest-blank_lines_in_for_loop
for i in range(2):
    pass
    
    pass
#EndTest
