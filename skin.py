# Skin and joint related functionality

import maya.cmds as cmds
import collections

def get_skins(joint):
    """ Yields skin names """
    for skin in set(cmds.listConnections(joint, s=False, type="skinCluster") or []):
        yield skin

def get_geos(skin):
    """ Yields geomrety names """
    for geo in cmds.skinCluster(skin, q=True, g=True) or []:
        yield geo

def get_influence(skin):
    """ Yields joints """
    for joint in cmds.skinCluster(skin, q=True, inf=True) or []:
        yield joint

weightCache = collections.defaultdict(list)
def get_weights(skin):
    """ Yields (vert ID, weights) """
    # Cache operation for multiple calls
    if skin not in weightCache:
        for vert in cmds.getAttr("%s.weightList" % skin, mi=True) or []:
            weightCache[skin].append(cmds.getAttr("%s.weightList[%s].weights" % (skin, vert))[0])
    for vert, weights in enumerate(weightCache[skin]):
        yield vert, weights

def trim_weights(weights):
    """ Yields index(s) of winning weight(s) """
    num = len([a for a in weights if a > 0.0001]) # Trim out zero weights
    if num:
        if num == 1: # Only one influence. Only one option...
            yield 0
        else: # Get influence with highest equal weighting
            cutoff = 1.0 / num
            for i, wgt in enumerate(weights):
                if cutoff <= wgt:
                    yield i

if __name__ == '__main__':
    cmds.file(new=True, force=True) # New blank scene for testing
    sphere = cmds.polySphere()[0] # Test Sphere
    sphere1 = cmds.polyCube()[0] # Test Sphere
    jnt1, jnt2 = ((cmds.select(cl=True), cmds.joint(p=a))[1] for a in ((0,-1,0), (0,1,0))) # Add Joints
    skin = cmds.skinCluster(sphere, sphere1, jnt1, jnt2)[0] # Add skin to sphere

    # All joints
    # print cmds.skinCluster(skin, q=True, inf=True)

    for vert, wgt in get_weights(skin):
        print vert, wgt, list(trim_weights(wgt))
