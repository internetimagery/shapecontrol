# Create controller

import collections
import maya.cmds as cmds

tree = lambda: collections.defaultdict(tree)

def warning(text):
    cmds.confirmDialog(t="Oh no!", m=text)

def ask(question):
    return "Yes" == cmds.confirmDialog(t="Quick Question...", m=question, button=["Yes","No"], defaultButton="Yes", cancelButton="No", dismissString="No" )

def create_control(geo, target, force=False):
    name = "ctrl_%s" % target
    if cmds.objExists(name) and not force:
        return cmds.warning("Control exists. Use Force to delete.")
    xform = cmds.group(empty=True, n="ctrl_%s" % target)
    cmds.xform(xform, ws=True, m=cmds.xform(target, q=True, ws=True, m=True))
    return xform, create_shape(geo, xform)

skinCache = collections.defaultdict(list)
def get_skins(joint):
    """ Yields skin names """
    if joint in skinCache:
        for skin in skinCache[joint]:
            yield skin
    else:
        for skin in set(cmds.listConnections(joint, s=False, type="skinCluster") or []):
            skinCache[joint].append(skin)
            yield skin

geoCache = collections.defaultdict(list)
def get_geos(skin):
    """ Yields geomrety names """
    if skin in geoCache:
        for geo in geoCache[skin]:
            yield geo
    else:
        for geo in cmds.skinCluster(skin, q=True, g=True) or []:
            geoCache[skin].append(geo)
            yield geo

infCache = collections.defaultdict(list)
def get_influence(skin):
    """ Yields joints """
    if skin in infCache:
        for inf in infCache[skin]:
            yield inf
    else:
        for inf in cmds.skinCluster(skin, q=True, inf=True) or []:
            infCache[skin].append(inf)
            yield inf

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

def convert_to_faces(selection):
    """ Turn a selection into a conservative face selection """
    return cmds.polyListComponentConversion(selection, tf=True, internal=True)

def create_shape(geo, xform):
    """ Create a Control that mimics the base geo """
    mesh = cmds.createNode("mesh", n="picker_%s" % xform, p=xform, ss=True)
    xform_compensate = cmds.createNode("transformGeometry", n="inverse_%s" % xform, ss=True)

    # Connect it all up!
    cmds.connectAttr("%s.worldInverseMatrix[0]" % xform, "%s.transform" % xform_compensate, f=True)
    cmds.connectAttr("%s.outMesh" % geo, "%s.inputGeometry" % xform_compensate)
    cmds.connectAttr("%s.outputGeometry" % xform_compensate, "%s.inMesh" % mesh)

    # Turn off rendering
    cmds.setAttr("%s.castsShadows", 0)
    cmds.setAttr("%s.receiveShadows", 0)
    cmds.setAttr("%s.motionBlur", 0)
    cmds.setAttr("%s.primaryVisibility", 0)
    cmds.setAttr("%s.smoothShading", 0)
    cmds.setAttr("%s.visibleInReflections", 0)
    cmds.setAttr("%s.visibleInRefractions", 0)
    cmds.setAttr("%s.doubleSided", 0)
    return mesh

def create_base(target, name):
    """ Create a base transform on the target """
    name = cmds.group(em=True, n=name)
    cmds.xform(name, ws=True, m=cmds.xform(target, q=True, ws=True, m=True))
    return name

def add_control_mesh(xform, joint):
    """ Add a control mesh to the xform. Based on the joint """
    to_remove = []
    for skin in get_skins(joint):
        for geo in get_geos(skin):
            mesh = create_shape(geo, xform) # Add instance of geo to xform
            inf_index = list(get_influence(skin)).index(influence)
            for vert, weights in get_weights(skin):
                for index in trim_weights(weights):
                    if inf_index != index:
                        to_remove.append("%s.vtx[%s]" % (mesh, vert))
    if to_remove:
        faces = convert_to_faces(to_remove)
        cmds.delete(faces)

def main():
    joints = cmds.ls(sl=True, type="joint")
    if not joints: return warning("Please select some joints")
    todo = []
    exists = []
    for jnt in joints:
        name = "ctrl_%s" % jnt
        if cmds.objExists(name):
            exists.append((name, jnt))
        else:
            todo.append((name, jnt))

    err = cmds.undoInfo(openChunk=True)
    try:
        if exists and ask("Some existing controls found. Do you wish to update them?"): # Replace existing controls
            for control, jnt in exists:
                # Clean out and refresh existing controls
                shapes = cmds.listRelatives(control, c=True, s=True)
                cmds.delete(shapes)
                # Add new control mesh
                add_control_mesh(control, jnt)
        for control, jnt in todo:
            control = create_base(jnt, control) # Create a new control
            add_control_mesh(control, jnt)

        if todo and ask("Do you wish to parent the joints to their respective controls?"):
            for control, jnt in todo:
                cmds.parent(jnt, control)
    except Exception as err:
        raise
    finally:
        cmds.undoInfo(closeChunk=True)
        if err:
            cmds.undo()


if __name__ == '__main__':
    cmds.file(new=True, force=True) # New blank scene for testing
    sphere = cmds.polySphere()[0] # Test Sphere
    jnt1, jnt2 = ((cmds.select(cl=True), cmds.joint(p=a))[1] for a in ((0,-1,0), (0,1,0))) # Add Joints
    skin = cmds.skinCluster(sphere, jnt1, jnt2)[0] # Add skin to sphere

    cmds.group(em=True, n="ctrl_%s" % jnt2)
    cmds.select(jnt2, r=True)
    main()

    # xform, mesh = create_control(sphere, jnt2)
    # create_control(sphere, jnt2)
    # cmds.parent(jnt2, xform)
