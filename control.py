# Create controller

import maya.cmds as cmds

def create_shape(geo, xform):
    """ Create a Control that mimics the base geo """
    mesh = cmds.createNode("mesh", n="picker_%s" % xform, p=xform, ss=True)
    xform_compensate = cmds.createNode("transformGeometry", n="inverse_%s" % xform, ss=True)

    # Connect it all up!
    cmds.connectAttr("%s.worldInverseMatrix[0]" % xform, "%s.transform" % xform_compensate, f=True)
    cmds.connectAttr("%s.outMesh" % geo, "%s.inputGeometry" % xform_compensate)
    cmds.connectAttr("%s.outputGeometry" % xform_compensate, "%s.inMesh" % mesh)
    return mesh

def create_control(geo, target, force=False):
    name = "ctrl_%s" % target
    if cmds.objExists(name) and not force:
        return cmds.warning("Control exists. Use Force to delete.")
    xform = cmds.group(empty=True, n="ctrl_%s" % target)
    cmds.xform(xform, ws=True, m=cmds.xform(target, q=True, ws=True, m=True))
    return xform, create_shape(geo, xform)


if __name__ == '__main__':
    cmds.file(new=True, force=True) # New blank scene for testing
    sphere = cmds.polySphere()[0] # Test Sphere
    jnt1, jnt2 = ((cmds.select(cl=True), cmds.joint(p=a))[1] for a in ((0,-1,0), (0,1,0))) # Add Joints
    skin = cmds.skinCluster(sphere, jnt1, jnt2)[0] # Add skin to sphere

    xform, mesh = create_control(sphere, jnt2)
    create_control(sphere, jnt2)
    cmds.parent(jnt2, xform)
