import os
from glob import glob
from nose.tools import eq_

from Orgnode import Orgnode, makelist

TESTDIR = os.path.dirname(__file__)

def check_data(dataname):
    """Helper function for test_data"""
    oname = os.path.join(TESTDIR, dataname + '.org')
    data = __import__(dataname).data
    nodelist = makelist(oname)

    for (i, (node, kwds)) in enumerate(zip(nodelist, data)):
        for key in kwds:
            val = node.__getattribute__(key.title())()
            eq_(kwds[key], val,
                msg=('check value of %d-th node of key "%s" from "%s". '
                     'Orgnode.%s() = %s != %s.'
                     ) % (i, key, oname, key.title(), val, kwds[key]))

def test_data():
    """
    Compare parsed data from 'data_*.org' using Orgnode and desired data
    which is described in 'data_*.py'.
    """
    for oname in glob(os.path.join(TESTDIR, 'data_*.org')):
        dataname = os.path.basename(oname)[:-4]
        yield (check_data, dataname)
