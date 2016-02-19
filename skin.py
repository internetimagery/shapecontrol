# Skin and joint related functionality

import maya.cmds as cmds
import maya.mel as mel
import collections

tree = lambda: collections.defaultdict(tree)

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

weightCache = tree()
def get_weights(skin):
    """ Yields (vert ID, weights) """
    # Cache operation for multiple calls
    if skin not in weightCache:
        skin_attr = "%s.weightList" % skin
        for vert in cmds.getAttr(skin_attr, mi=True) or []:
            vert_attr = "%s[%s].weights" % (skin_attr, vert)
            weights = dict((a, cmds.getAttr("%s[%s]" % (vert_attr, a))) for a in cmds.getAttr(vert_attr, mi=True) or [])
            weightCache[skin][vert] = weights
    for vert, weights in weightCache[skin].iteritems():
        yield vert, weights

def trim_weights(weights):
    """ Yields index(s) of winning weight(s) """
    highest = max(weights.values())
    for i, weight in weights.iteritems():
        if weight == highest: # Tie breaker, keep both!
            yield i

def selection_influence(skin, influence):
    """ Build a selection of verices that hold the majority of influence """
    for skin in get_skins(influence):
        for geo in get_geos(skin):
            inf_index = list(get_influence(skin)).index(influence)
            for vert, weights in get_weights(skin):
                for index in trim_weights(weights):
                    vert_name = "%s.vtx[%s]" % (geo, vert)
                    if inf_index == index:
                        yield "%s.vtx[%s]" % (geo, vert)

def convert_to_faces(selection):
    return cmds.polyListComponentConversion(selection, tf=True, internal=True)


if __name__ == '__main__':
    cmds.file(new=True, force=True) # New blank scene for testing
    sphere = cmds.polySphere()[0] # Test Sphere
    jnt1, jnt2 = ((cmds.select(cl=True), cmds.joint(p=a))[1] for a in ((0,-1,0), (0,1,0))) # Add Joints
    skin = cmds.skinCluster(sphere, jnt1, jnt2)[0] # Add skin to sphere

    sel = convert_to_faces(list(selection_influence(skin, jnt2)))
    cmds.select(sel, r=True)
