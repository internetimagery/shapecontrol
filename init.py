# Create a controller as part of the mesh!

import maya.cmds as cmds
import control
import skin

def create_control(joint):
    """ Create a controller out of a mesh and joint """
    for sk in skin.get_skins(joint):
        for mesh in skin.get_geos(sk):
            xform, mesh = control.create_control(mesh, joint)

            vert_influence = []
            inf_index = list(skin.get_influence(sk)).index(joint)
            for vert, weights in skin.get_weights(sk):
                for i in skin.trim_weights(weights):
                    if inf_index != i:
                        name = "%s.vtx[%s]" % (mesh, vert)
                        vert_influence.append(name)
            face_influence = skin.convert_to_faces(vert_influence)
            cmds.delete(face_influence)


def test():
    print "testing"
    cmds.file(new=True, force=True) # New blank scene for testing
    sphere = cmds.polySphere()[0] # Test Sphere
    jnt1, jnt2 = ((cmds.select(cl=True), cmds.joint(p=a))[1] for a in ((0,-1,0), (0,1,0))) # Add Joints
    skin = cmds.skinCluster(sphere, jnt1, jnt2)[0] # Add skin to sphere

    control = create_control(jnt2)
    cmds.parent(jnt2, control)
    cmds.setAttr("%s.overrideEnabled" % sphere, 1)
    cmds.setAttr("%s.overrideDisplayType" % sphere, 2)
