Mount your Trac with Fuse
=========================

Install
-------
Trac_ with the xmlrpc plugin

Fuse_ or MacFuse_

Fusepy_ module for python. Just put it in the same folder.

Usage
-----

  mkdir toto
  
  ./fuseTrack.py toto --host=http://localhost/trac --user=bob --password=sponge

Your Trac is mounted, you can see every wiki page and their attached document.

Features
--------
- For now, it's read only.
- Only basic auth, no digest
- http or https

.. _Trac: http://trac.edgewall.org/
.. _Fuse: http://fuse.sourceforge.net/
.. _MacFuse: http://code.google.com/p/macfuse/
.. _Fusepy: http://code.google.com/p/fusepy/