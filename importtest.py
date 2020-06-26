from bpython.importcompletion import find_modules
import os

foo = find_modules(os.path.abspath("./importtestfolder"))

for thing in foo:
    pass

#bpython import_completion yield name       |       #bpython import yield name subname and yield name
#bpdb                                       |       #bpdb
#__pycache__                                |       #__pycache__
#                                           |       #bpython __pycache__
#__pycache__                                |       #__pycache__
#                                           |       #curtsiesfrontend __pycache__
#                                           |       #bpython curtsiesfrontend.__pycache__
#curtsiesfrontend                           |       #curtsiesfrontend
#                                           |       #bpython curtsiesfrontend
#fodder                                     |       #fodder
#                                           |       #test fodder
#                                           |       #bpython test.fodder
#test                                       |       #test
#                                           |       #bpython test
#__pycache__                                |       #__pycache__
#                                           |       #translations __pycache__
#                                           |       #bpython translations.__pycache__
#LC_MESSAGES                                |       #LC_MESSAGES
#                                           |       #de LC_MESSAGES
#                                           |       #translations de.LC_MESSAGES
#                                           |       #bpython translations.de.LC_MESSAGES
#de                                         |       #de
#LC_MESSAGES                                |       #LC_MESSAGES
#                                           |       #es_ES LC_MESSAGES
#                                           |       #translations es_ES.LC_MESSAGES
#                                           |       #bpython translations.es_ES.LC_MESSAGES
#es_ES                                      |       #es_ES
#LC_MESSAGES                                |       #LC_MESSAGES
#                                           |       #fr_FR LC_MESSAGES
#                                           |       #translations fr_FR.LC_MESSAGES
#                                           |       #bpython translations.fr_FR.LC_MESSAGES
#fr_FR                                      |       #fr_FR
#LC_MESSAGES                                |       #LC_MESSAGES
#                                           |       #it_IT LC_MESSAGES
#                                           |       #translations it_IT.LC_MESSAGES
#                                           |       #bpython translations.it_IT.LC_MESSAGES
#it_IT                                      |       #it_IT
#LC_MESSAGES                                |       #LC_MESSAGES
#                                           |       #nl_NL LC_MESSAGES
#                                           |       #translations nl_NL.LC_MESSAGES
#                                           |       #bpython translations.nl_NL.LC_MESSAGES
#nl_NL                                      |       #nl_NL
#translations                               |       #translations
#                                           |       #bpython translations
#bpython                                    |       #bpython
#data                                       |       #data
#source                                     |       #source
#                                           |       #sphinx source
#                                           |       #doc sphinx.source
#sphinx                                     |       #sphinx
#                                           |       #doc sphinx
#doc                                        |       #doc
#Level2                                     |       #Level2
#                                           |       #Level1 Level2
#                                           |       #Level0 Level1.Level2
#                                           |       #importtestfolder Level0.Level1.Level2
#Level1                                     |       #Level1
#Level0                                     |       #Level0
#                                           |       #importtestfolder Level0
#importtestfolder                           |       #importtestfolder
#pip-wheel-metadata                         |       #pip-wheel-metadata