#! /usr/bin/python

from bpython import line
from bpython.autocomplete import ArrayItemMembersCompletion

foo = ["1"]

# matches = line.current_array_item_member_name(0, 'foo[0].')
# 
# for m in matches:
#     obj = m.group(1)
#     print obj
#     me = eval(obj)
#     print me
#     attrs = dir('')
#     print m.group(2)
#     attr_matches = set(att for att in attrs if att.startswith(m.group(2)))
#     for m in attr_matches:
#         print m


# matches = line.current_array_item_member_name(7, 'foo[0].')
# print matches

completion = ArrayItemMembersCompletion()
print completion.matches(7, 'foo[0].')
