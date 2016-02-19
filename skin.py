# Skin and joint related functionality

import maya.cmds as cmds

def get_skin(joint):
    for skin in cmds.listConnections(joint, s=False, type="skinCluster") or []:
        return skin

if __name__ == '__main__':
    cmds.file(new=True, force=True) # New blank scene for testing
    sphere = cmds.polySphere()[0] # Test Sphere
    jnt1, jnt2 = ((cmds.select(cl=True), cmds.joint(p=a))[1] for a in ((0,-1,0), (0,1,0))) # Add Joints
    skin = cmds.skinCluster(sphere, jnt1, jnt2)[0] # Add skin to sphere
    # Testing
    assert get_skin(jnt1) == skin
