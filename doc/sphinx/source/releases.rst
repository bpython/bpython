.. _releases:

Releases
========

Release schedule
----------------
bpython does not have a set release cycle. The developers will decide together when the time is ripe to release a version.
For information what happens after the decision is made to make a release you should read the 'Release Path' section.

Release Path
------------
After it is decided to release a new version of bpython the following checklist is followed:

* The repository is frozen, nobody pushes until the version is built.
* Bob (:ref:`authors`) makes a tarball of the new version and sends it to Simon (:ref:`authors`) who will host it on the  bpython website.
* The package is then downloaded by all of the people who like to test it.
* Everybody checks if there are no great problems:

  * Version numbers correct?
  * CHANGELOG is correct?
  * AUTHORS?

* After everybody says 'yes' the website and pypi are updated to point to this new version.

  * Simon (:ref:`authors`) also checks if all numbers on the website have been updated.

* 24 hours later package maintainers could update their stuff.
