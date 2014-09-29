.. _bpdb:

bpdb
====

To enable bpython support within pdb, start pdb with the following code:

.. code-block:: python

    import bpdb
    bpdb.set_trace()

This will drop you into bpdb instead of pdb, which works exactly like pdb except
that you can additionally start bpython at the current stack frame by issuing
the command `Bpython` or `B`.

You can exit bpython with `^d` to return to bpdb.
