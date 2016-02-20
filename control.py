# Create controller

import collections
import maya.cmds as cmds

TREE = lambda: collections.defaultdict(TREE)
INF_LINK = "controllers"
CTRL_LINK = "influence"

# Utility

def warning(text):
    """ Pop up a message """
    cmds.confirmDialog(t="Oh no!", m=text)

def ask(question):
    """ Ask user a question """
    return "Yes" == cmds.confirmDialog(t="Quick Question...", m=question, button=["Yes","No"], defaultButton="Yes", cancelButton="No", dismissString="No" )

def get_attr(node, attr, create=False):
    """ Get attribute. Creating one if it doesn't exist """
    if not cmds.attributeQuery(attr, n=node, ex=True) and create:
        cmds.addAttr(node, ln=attr, s=True)
    return node + "." + attr

def connections(*args, **kwargs):
    """ Grab connections """
    try:
        return cmds.listConnections(*args, **kwargs) or []
    except ValueError:
        return []

skinCache = collections.defaultdict(list)
def get_skins(joint):
    """ Yields skin names """
    if joint in skinCache:
        for skin in skinCache[joint]:
            yield skin
    else:
        for skin in set(connections(joint, s=False, type="skinCluster")):
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
def get_influences(skin):
    """ Yields joints """
    if skin in infCache:
        for inf in infCache[skin]:
            yield inf
    else:
        for inf in cmds.skinCluster(skin, q=True, inf=True) or []:
            infCache[skin].append(inf)
            yield inf

weightCache = TREE()
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

def get_influence_include_exclude(joint):
    """ Get verts included and excluded from influence """
    geos = set()
    inclusion = collections.defaultdict(list)
    exclusion = collections.defaultdict(list)
    for skin in get_skins(joint):
        for geo in get_geos(skin):
            geos.add(geo)
            influences = list(get_influences(skin))
            if joint in influences:
                inf_index = influences.index(joint)
                for vert, weights in get_weights(skin):
                    for index in trim_weights(weights):
                        if inf_index == index:
                            inclusion[geo].append(vert)
                        else:
                            exclusion[geo].append(vert)
    return geos, inclusion, exclusion

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
    cmds.setAttr("%s.castsShadows" % mesh, 0)
    cmds.setAttr("%s.receiveShadows" % mesh, 0)
    cmds.setAttr("%s.motionBlur" % mesh, 0)
    cmds.setAttr("%s.primaryVisibility" % mesh, 0)
    cmds.setAttr("%s.smoothShading" % mesh, 0)
    cmds.setAttr("%s.visibleInReflections" % mesh, 0)
    cmds.setAttr("%s.visibleInRefractions" % mesh, 0)
    cmds.setAttr("%s.doubleSided" % mesh, 0)
    return mesh

def create_base(target, name):
    """ Create a base transform on the target """
    name = cmds.group(em=True, n=name)
    cmds.xform(name, ws=True, m=cmds.xform(target, q=True, ws=True, m=True))
    return name

def set_connected_controller(influence, controller):
    """ Forge a link to a controller """
    out_attr = get_attr(influence, INF_LINK, True)
    in_attr = get_attr(controller, CTRL_LINK, True)
    cmds.connectAttr(out_attr, in_attr)

def get_connected_controllers(influence):
    """ Get all linked controllers """
    attr = get_attr(influence, INF_LINK)
    return connections(attr, s=False)

def get_connected_influence(controller):
    """ Get all linked controllers """
    attr = get_attr(controller, CTRL_LINK)
    return connections(attr, d=False)

def create_invis_material():
    """ Make material to hide object """
    name = "invsible_material"
    if not cmds.objExists(name):
        name = cmds.shadingNode("surfaceShader", asShader=True, n=name)
        set_ = cmds.sets(r=True, nss=True, em=True, n="%sSG" % name)
        cmds.connectAttr("%s.outColor" % name, "%s.surfaceShader" % set_)
        cmds.setAttr("%s.outTransparency" % name, 1, 1, 1, type="double3")
    return name

def apply_material(obj, material):
    """ Apply material to an object """
    for set_ in connections("%s.outColor" % material):
        cmds.sets(obj, e=True, fe=set_)

def get_selected_joints():
    """ Get all joints in selection """
    return cmds.ls(sl=True, type="joint")

def update_controller(joint):
    """ Update controllers given a joint """
    controllers = get_connected_controllers(joint)
    for controller in controllers:
        shapes = cmds.listRelatives(controller, c=True, s=True) # Grab old shapes
        cmds.delete(shapes) # Remove old shapes
        geos, include, exclude = get_influence_include_exclude(joint) # find out what affects joint
        for geo in geos: # Run through meshes
            shape = create_shape(geo, controller) # Add mesh
            try:
                verts = ["%s.vtx[%s]" % (shape, a) for a in exclude[geo]]
                faces = convert_to_faces(verts)
                cmds.delete(faces)
            except ValueError: # Nothing to exclude? Moving on!
                pass

def build_controller(joint):
    """ Create a new controller give a joint """
    geos, include, exclude = get_influence_include_exclude(joint) # find out what affects joint
    if geos: # Check this joint actually has something to connect to
        base = create_base(joint, "ctrl_%s" % joint) # make base to hold control mesh
        set_connected_controller(joint, base) # Link up control to joint
        for geo in geos: # Run through meshes
            shape = create_shape(geo, base) # Add mesh
            try:
                verts = ["%s.vtx[%s]" % (shape, a) for a in exclude[geo]]
                faces = convert_to_faces(verts)
                cmds.delete(faces)
            except ValueError: # Nothing to exclude? Moving on!
                pass
        return base

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
        if todo:
            material = create_invis_material()
            for control, jnt in todo:
                control = create_base(jnt, control) # Create a new control
                add_control_mesh(control, jnt)
                apply_material(control, material)

            if ask("Do you wish to parent the joints to their respective controls?"):
                for control, jnt in todo:
                    cmds.parent(jnt, control)
    except Exception as err:
        raise
    finally:
        cmds.undoInfo(closeChunk=True)
        if err:
            cmds.undo()

def prep_test():
    cmds.file(new=True, force=True) # New blank scene for testing
    sphere = cmds.polySphere()[0] # Test Sphere
    jnt1, jnt2 = ((cmds.select(cl=True), cmds.joint(p=a))[1] for a in ((0,-1,0), (0,1,0))) # Add Joints
    skin = cmds.skinCluster(sphere, jnt1, jnt2)[0] # Add skin to sphere
    cmds.select(jnt1, jnt2, r=True)

    build_controller(jnt2)

if __name__ == '__main__':
    # prep_test()

    jnt = cmds.ls(sl=True, type="joint")
    update_controller(jnt[0])

    # main()


    # TODO
    #
    # pick one Joint option
    # walk the skeleton to the base
    # build a replica skeleton of dummy ctrl nodes, skipping joints without a skin
    # attach control shape to dummies
    # constrain joint to control
    #
    # OR pick specific Joints
    # validate joint has a skin
    # attach control shape to dummy
