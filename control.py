# Create controller

import maya.cmds as cmds

def create_shape(geo, target):
    """ Create a Control that mimics the base geo """
    xform = cmds.group(empty=True, n="ctrl_%s" % target)
    cmds.xform(xform, ws=True, m=cmds.xform(target, q=True, ws=True, m=True))
    mesh = cmds.createNode("mesh", n="picker_%s" % target, p=xform, ss=True)

    xform_compensate = cmds.createNode("transformGeometry", n="inverse_%s" % target, ss=True)

    # Connect it all up!
    cmds.connectAttr("%s.worldInverseMatrix[0]" % xform, "%s.transform" % xform_compensate, f=True)
    cmds.connectAttr("%s.outMesh" % geo, "%s.inputGeometry" % xform_compensate)
    cmds.connectAttr("%s.outputGeometry" % xform_compensate, "%s.inMesh" % mesh)


if __name__ == '__main__':
    cmds.file(new=True, force=True) # New blank scene for testing
    sphere = cmds.polySphere()[0] # Test Sphere
    jnt1, jnt2 = ((cmds.select(cl=True), cmds.joint(p=a))[1] for a in ((0,-1,0), (0,1,0))) # Add Joints
    skin = cmds.skinCluster(sphere, jnt1, jnt2)[0] # Add skin to sphere

    create_shape(sphere, jnt2)

    # print cmds.createNode("mesh")
